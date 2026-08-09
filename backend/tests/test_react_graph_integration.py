"""Task 11 react_graph 工厂 — 整合 4 个自定义 node + 手写 StateGraph。

mock LLMClient 避免真实 API 调用。
"""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

import app.domain.agent.react_graph as rg


@pytest.fixture
def stub_llm(monkeypatch):
    """Stub LLMClient.chat_with_tools 返回简单字符串回复(无 tool_calls)。"""

    async def fake_chat_with_tools(messages, tools):
        return {"content": "stubbed response", "tool_calls": None}

    class _StubLLM:
        last_call_duration_ms = 0
        primary_provider_name = staticmethod(lambda: "stub")

        async def chat_with_tools(self, messages, tools):
            return await fake_chat_with_tools(messages, tools)

    # Patch `LLMClient` import inside react_graph via the runtime lookup
    monkeypatch.setattr(rg, "LLMClient", _StubLLM)
    return _StubLLM()


def test_build_react_graph_returns_compiled_graph():
    g = rg.build_react_graph()
    assert hasattr(g, "astream_events")
    assert hasattr(g, "invoke")
    assert hasattr(g, "ainvoke")


@pytest.mark.asyncio
async def test_react_graph_ainvoke_with_simple_message(monkeypatch, db_session):
    """Stub LLM 返回纯文本,react_graph 单步完成 → output 含至少一条 AIMessage。

    T2:agent 节点落库(assistant),需要在 agent_sessions 表先建 session,
    否则 agent_messages.session_id 外键约束失败。
    """
    from app.repositories.agent_repo import AgentRepository

    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")
    sid = session.id

    import app.domain.agent.react_graph as rg

    class _StubLLM:
        last_call_duration_ms = 0
        primary_provider_name = staticmethod(lambda: "stub")

        async def chat_with_tools(self, messages, tools):
            return {"content": "stubbed response", "tool_calls": None}

    monkeypatch.setattr(rg, "LLMClient", _StubLLM)

    out = await rg.build_react_graph().ainvoke(
        {
            "messages": [HumanMessage(content="hi")],
            "session_id": sid,
            "memory_chunk": None,
            "truncation_result": None,
            "tool_call_log": [],
        },
        config={"configurable": {"thread_id": sid}},
    )
    msgs = out["messages"]
    assert len(msgs) >= 1
    assert any(isinstance(m, AIMessage) for m in msgs)


@pytest.mark.asyncio
async def test_tool_node_hitl_interrupts_on_confirmation_required(
    monkeypatch, db_session
):
    """工具声明需要确认 → tool_node 转 interrupt → 图暂停并持久化 checkpoint。

    HITL 全链路:ToolExecutor 抛 HumanConfirmationRequired → interrupt(payload)
    → 图在 tools 节点内暂停(无 on_chain_end 正常收尾,state 可 resume)。
    """

    from app.repositories.agent_repo import AgentRepository

    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")
    sid = session.id

    import app.domain.agent.react_graph as rg

    class _StubLLM:
        last_call_duration_ms = 0
        call_count = 0
        primary_provider_name = staticmethod(lambda: "stub")

        async def chat_with_tools(self, messages, tools):
            self.call_count += 1
            if self.call_count == 1:
                return {
                    "content": None,
                    "tool_calls": [{
                        "id": "tc-hitl",
                        "name": "generate_article",
                        "args": {"kb_id": "kb-1", "brand": "Acme", "topic": "t"},
                    }],
                }
            return {"content": "done", "tool_calls": None}

    monkeypatch.setattr(rg, "LLMClient", _StubLLM)

    # stub ToolExecutor:声明需要确认 → 抛 HumanConfirmationRequired
    from app.domain.agent.tool_executor import ToolExecutor
    from app.domain.exceptions import HumanConfirmationRequired

    class _HitlTE(ToolExecutor):
        async def execute(self, tool_name, args):
            raise HumanConfirmationRequired(
                message_id="m-hitl", tool_name=tool_name, arguments=args
            )

    monkeypatch.setattr("app.domain.agent.tool_executor.ToolExecutor", _HitlTE)

    graph = rg.build_react_graph()
    cfg = {"configurable": {"thread_id": sid}}
    await graph.ainvoke(
        {
            "messages": [HumanMessage(content="写文章")],
            "session_id": sid,
            "memory_chunk": None,
            "truncation_result": None,
            "tool_call_log": [],
        },
        config=cfg,
    )

    # 图因 interrupt 暂停:state 含 __interrupt__ 且 next 指向 tools 恢复点
    st = graph.get_state(cfg)
    assert st.interrupts, "HITL interrupt 必须产生中断记录"
    payload = st.interrupts[0].value
    assert payload["kind"] == "decision"
    assert payload["tool_name"] == "generate_article"
