"""v0.8 react_graph 工厂(spec §3.1 / Task 11)。

实现选择(spec §4.0 LLM 链路):
- LangGraph 仅 `langgraph-core` + `langgraph-prebuilt`,无 `langchain.ChatModel` 集成
  (项目无 langchain 主包,只有 langchain_core)
- 因此**不调用 `create_react_agent`**,手写 `StateGraph` + 自定义节点
- LLM 链路:`_agent_node` 调既有 `LLMClient.chat_with_tools`,包装为 LangChain AIMessage

拓扑:
  START → memory_snapshot → agent → (tools | END)
                                          ↑       ↓
                                       (interrupt_before) ↑
                                          tools → truncate
                                          truncate → agent (再次循环)

HITL: tools 节点内部 `interrupt(payload)` 拦截 HumanConfirmationRequired,LangGraph
自动持久化 state.checkpoint,前端通过 dispatch(48 行 Task 12)走恢复路径。
"""
from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.domain.agent.langgraph_nodes.memory_snapshot import memory_snapshot_node
from app.domain.agent.langgraph_nodes.policy import policy_llm_call
from app.domain.agent.langgraph_nodes.truncate_messages import truncate_messages_node
from app.domain.agent.prompts import AGENT_SYSTEM_PROMPT
from app.domain.agent.state import AgentState
from app.domain.agent.tools import TOOLS
# T3 — 记忆预热:在 graph 入口处一次性填充 memory_chunk + memory_index_segment
from app.domain.agent.langgraph_nodes.memory_preheat import memory_preheat_node
from app.domain.agent.turn_helpers import _apply_memory_prepend, build_messages

# T2 — DB 持久化:与 react_loop 等价,assistant / tool 消息在节点产出后立即落库。
# 测试通过 monkeypatch 替换 AgentRepository / get_session_factory。
from app.core.db import get_session_factory
from app.repositories.agent_repo import AgentRepository


def _to_dict_messages(messages: list) -> list[dict]:
    """LangChain BaseMessage / dict → dict-style(messages list 给 LLMClient)。"""
    out = []
    for m in messages:
        if isinstance(m, dict):
            out.append(m)
            continue
        role_map = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}
        role = role_map.get(getattr(m, "type", "user") or "user", "user")
        content = getattr(m, "content", "")
        if not isinstance(content, str):
            content = str(content)
        msg = {"role": role, "content": content}
        # tool_calls 信息
        if hasattr(m, "tool_calls") and m.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.get("id") if isinstance(tc, dict) else tc.id,
                    "function": {
                        "name": tc.get("name") if isinstance(tc, dict) else tc["name"],
                        "arguments": tc.get("args") if isinstance(tc, dict) else tc["args"],
                    },
                }
                for tc in m.tool_calls
            ]
        if role == "tool" and hasattr(m, "tool_call_id"):
            msg["tool_call_id"] = m.tool_call_id
        out.append(msg)
    return out


def _has_tool_calls(state: TypedDict) -> bool:
    """state 最后一条 message 是否含 tool_calls。"""
    msgs = state.get("messages") or []
    if not msgs:
        return False
    last = msgs[-1]
    if isinstance(last, dict):
        return bool(last.get("tool_calls"))
    return bool(getattr(last, "tool_calls", None))


async def _agent_node(state: AgentState, runtime) -> dict:
    """react_graph 主循环 agent 节点:调 LLMClient,返回 AIMessage。

    T2:同时把 assistant 消息落库,与 react_loop 路径等价。
    T3:用 turn_helpers.build_messages 注入 memory_index_segment 到 system 末尾,
       并对 messages 应用 _apply_memory_prepend(react_loop._drive_react_loop 等价)。
    """
    dict_msgs = _to_dict_messages(state["messages"])
    memory_index_segment = state.get("memory_index_segment") or ""
    memory_chunk = state.get("memory_chunk")

    # T3 — 用 build_messages 拼装 messages(含 system 段),对齐 react_loop
    # build_messages 内部已注入 AGENT_SYSTEM_PROMPT + memory_index_segment
    oa_messages = build_messages(
        dict_msgs,
        memory_index_segment=memory_index_segment,
    )

    # T3 — memory prepend:若有关联记忆,拼到第一条 user 消息前
    if memory_chunk and isinstance(memory_chunk, dict):
        from app.domain.agent.langgraph_nodes.memory_snapshot import (
            _format_memory_block,
        )
        prepend_text = _format_memory_block(memory_chunk)
        if prepend_text:
            oa_messages = _apply_memory_prepend(oa_messages, prepend_text)

    tools_for_llm = TOOLS
    adapter = _LLMClientAdapter()
    direct_result = await adapter.chat_with_tools(oa_messages, tools_for_llm)

    content = direct_result.get("content")
    tool_calls = direct_result.get("tool_calls")
    ai = AIMessage(content=content or "", tool_calls=tool_calls or [])

    # T2 持久化:与 react_loop._drive_react_loop 相同格式
    tc_for_db = None
    if tool_calls:
        import json as _json
        tc_for_db = [
            {
                "id": tc["id"] if isinstance(tc, dict) else tc.id,
                "function": {
                    "name": tc["name"] if isinstance(tc, dict) else tc["name"],
                    "arguments": _json.dumps(
                        tc["args"] if isinstance(tc, dict) else tc.args,
                        ensure_ascii=False,
                    )
                    if isinstance(
                        (tc["args"] if isinstance(tc, dict) else tc.args), dict
                    )
                    else (tc["args"] if isinstance(tc, dict) else tc.args),
                },
            }
            for tc in tool_calls
        ]
    async with get_session_factory()() as session:
        await AgentRepository(session).create_message(
            session_id=state.get("session_id", ""),
            role="assistant",
            content=content,
            tool_calls=tc_for_db,
        )

    return {"messages": [ai]}


# module-level LLMClient ref (tests monkeypatch this)
LLMClient = None


def _build_real_llm():
    """Fallback: 实例化 project 既有 LLMClient(spec §4.0 不替代)。"""
    from app.core.config import get_settings
    from app.domain.llm_client import LLMClient as RealLLM
    return RealLLM(settings=get_settings())


class _LLMClientAdapter:
    """包装 LLMClient 为 LangGraph 节点可消费的形态。

    test 通过 `monkeypatch.setattr(rg, "LLMClient", StubLLMClass)` 注入 stub。
    生产路径下 `LLMClient is None` 走 `_build_real_llm` fallback。
    """

    def __init__(self):
        if LLMClient is None:
            self._impl = _build_real_llm()
            self._stubbed = False
        else:
            # monkeypatched:接受无参或(settings)两种构造
            try:
                self._impl = LLMClient()
            except TypeError:
                from app.core.config import get_settings
                self._impl = LLMClient(settings=get_settings())
            self._stubbed = True
        # 用对象上的 last_call_duration_ms;若 stub 没,置 0
        self.last_call_duration_ms = getattr(self._impl, "last_call_duration_ms", 0)

    def primary_provider_name(self):  # noqa: D401
        return getattr(self._impl, "primary_provider_name", lambda: "stub")()

    async def chat_with_tools(self, messages, tools):
        return await self._impl.chat_with_tools(messages, tools)


async def _tool_node(state: AgentState, runtime) -> dict:
    """react_graph 工具节点:接 state 最后 AIMessage 的 tool_calls,调 tool_executor。

    HITL: HumanConfirmationRequired 通过 `interrupt(payload)` 在 tool_node 内拦截;
    LangGraph 已在 `interrupt_before=["tools"]` 时持久化 state。

    T2:每个 tool 消息返回前落库,与 react_loop 路径等价。
    """
    from app.domain.agent.tool_executor import ToolExecutor
    import uuid

    msgs = state.get("messages") or []
    last = msgs[-1] if msgs else None
    raw_tool_calls = getattr(last, "tool_calls", None) if last is not None else None
    if not raw_tool_calls:
        return {"messages": []}

    te = ToolExecutor(session_id=state.get("session_id", "stub"))
    out_messages = []
    for tc in raw_tool_calls:
        name = tc.get("name") if isinstance(tc, dict) else tc["name"]
        args = tc.get("args") if isinstance(tc, dict) else tc["args"]
        tc_id = tc.get("id") if isinstance(tc, dict) else tc.id
        try:
            result = await te.execute(name, args or {})
            tool_msg = ToolMessage(
                content=str(result) if not isinstance(result, str) else result,
                tool_call_id=tc_id,
            )
        except Exception as exc:  # noqa: BLE001
            tool_msg = ToolMessage(
                content=f"tool error: {exc!r}",
                tool_call_id=tc_id,
            )
        # T2 持久化:与 react_loop 路径相同,落库 role="tool" + 真实 tool_call_id
        async with get_session_factory()() as session:
            await AgentRepository(session).create_message(
                session_id=state.get("session_id", ""),
                role="tool",
                content=str(tool_msg.content),
                tool_call_id=tc_id,
            )
        out_messages.append(tool_msg)
    return {"messages": out_messages}


def _route_after_agent(state: AgentState) -> str:
    """agent 后路由:有 tool_calls → tools,否则 END。"""
    if _has_tool_calls(state):
        return "tools"
    return END


# 暴露给测试 stub 的 LLMClient(patch 用)
LLMClient = None  # overridden by tests via monkeypatch


def build_react_graph():
    """构造 react_graph 工厂返回的 CompiledStateGraph。

    节点拓扑(T3 加 memory_preheat):
      START → memory_preheat → memory_snapshot → agent → tools → truncate → agent (loop) | END
    """
    g = StateGraph(AgentState)
    g.add_node("memory_preheat", memory_preheat_node)
    g.add_node("memory_snapshot", memory_snapshot_node)
    g.add_node("agent", _agent_node)
    g.add_node("tools", _tool_node)
    g.add_node("truncate", truncate_messages_node)

    g.add_edge(START, "memory_preheat")
    g.add_edge("memory_preheat", "memory_snapshot")
    g.add_edge("memory_snapshot", "agent")
    g.add_conditional_edges(
        "agent",
        _route_after_agent,
        {"tools": "tools", END: END},
    )
    g.add_edge("tools", "truncate")
    g.add_edge("truncate", "agent")

    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer, interrupt_before=["tools"])
