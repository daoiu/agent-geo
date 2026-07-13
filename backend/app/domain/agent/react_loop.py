"""v0.4 ReAct 循环：agent 推理 + 工具执行。

设计要点：
- 自写循环（不引 LangGraph / LangChain）
- MAX_REACT_ITERATIONS = 7 防无限循环
- 流式 yield SSE 事件（assistant_message / tool_call_start / tool_call_result /
  human_confirmation_required / turn_complete / max_iterations_reached）
- 写类工具抛 HumanConfirmationRequired 暂停循环
- 断点续跑：run_agent_turn_from_checkpoint 从上次 pending_confirmation 继续执行

v0.6 P1.6 — L2 跨会话偏好：
- `build_messages` 接受 `memory_index_segment`,拼到 system 末尾
- `_apply_memory_prepend` 在每个 LLM call 前把相关记忆 prepended 到 user 消息
- `_do_extract_after_turn` 在 `turn_complete` 前 fire-and-forget 触发蒸馏
- `_PENDING_EXTRACTS` 持有后台 task 防 GC
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import structlog

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.agent.memory import MemoryService, scope_key
from app.domain.agent.prompts import AGENT_SYSTEM_PROMPT
from app.domain.agent.tool_executor import ToolExecutor
from app.domain.agent.tools import TOOLS
from app.domain.llm_client import LLMClient
from app.models.orm_v04 import AgentMessageORM
from app.repositories.agent_repo import AgentRepository

MAX_REACT_ITERATIONS = 7  # v0.6 P1.4: 5 → 7，留余量给 list → search → create_task
logger = structlog.get_logger()

# Fire-and-forget 持有的后台任务集合,避免被 GC
_PENDING_EXTRACTS: set[asyncio.Task] = set()


# ===========================================================================
# 消息构建
# ===========================================================================


def build_messages(
    history: list[dict],
    memory_index_segment: str = "",
) -> list[dict]:
    """把 DB 风格历史转换为 OpenAI chat completion 协议格式。

    输入 history 元素格式：
      {"role": "user"|"assistant"|"tool"|"system", "content": str|None, ...}

    特殊处理：
    - assistant 消息的 tool_calls.arguments 必须是 JSON **字符串**（OpenAI 协议要求，
      DB 也以字符串存储）；这里原样透传，dict 则序列化回字符串，绝不发对象。
    - tool 消息必须带 tool_call_id（OpenAI 协议要求）
    - **配对保证**：只保留有对应 tool 结果的 tool_call；丢弃 dangling 的
      （HumanConfirmation / 被中断的流会留下无结果的 tool_call），并跳过孤儿 tool
      结果。否则严格 provider 报 'tool call result does not follow tool call' 400。
    - 系统 prompt 总是作为第一条注入
    - v0.6 P1.6:`memory_index_segment`（L2 索引段）拼到系统 prompt 末尾,
      仅常量部分参与 prompt cache,索引内容改变不需要重建整段 system
    """
    # 先扫出「已有结果」的 tool_call_id（存在对应 tool 消息）与「被 assistant 声明」的
    # tool_call_id；只有两者交集(kept_ids)才是可安全重放的配对。
    resolved_ids: set[str] = {
        msg["tool_call_id"]
        for msg in history
        if msg.get("role") == "tool" and msg.get("tool_call_id")
    }
    declared_ids: set[str] = set()
    for msg in history:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tc_raw = msg["tool_calls"]
            if isinstance(tc_raw, str):
                tc_raw = json.loads(tc_raw)
            for tc in tc_raw:
                if tc.get("id"):
                    declared_ids.add(tc["id"])
    kept_ids = resolved_ids & declared_ids

    out: list[dict] = [{
        "role": "system",
        "content": AGENT_SYSTEM_PROMPT + memory_index_segment,
    }]

    for msg in history:
        role = msg["role"]
        if role == "user":
            out.append({"role": "user", "content": msg["content"]})
        elif role == "assistant":
            asst: dict = {"role": "assistant", "content": msg.get("content")}
            if msg.get("tool_calls"):
                tc_raw = msg["tool_calls"]
                if isinstance(tc_raw, str):
                    tc_raw = json.loads(tc_raw)
                # 兼容两种格式：
                # 1. OpenAI 风格：{id, function: {name, arguments}}
                # 2. 简化风格：{tool, arguments}
                normalized = []
                for tc in tc_raw:
                    tc_id = tc.get("id", "")
                    # 只保留有对应 tool 结果的 call，避免 dangling tool_call
                    if tc_id not in kept_ids:
                        continue
                    if "function" in tc:
                        args = tc["function"]["arguments"]
                        normalized.append({
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": args
                                if isinstance(args, str)
                                else json.dumps(args, ensure_ascii=False),
                            },
                        })
                    elif "tool" in tc:
                        # 简化风格 → 转换为 OpenAI 风格
                        sargs = tc["arguments"]
                        normalized.append({
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc["tool"],
                                "arguments": sargs
                                if isinstance(sargs, str)
                                else json.dumps(sargs, ensure_ascii=False),
                            },
                        })
                if normalized:
                    asst["tool_calls"] = normalized
            # 跳过既无内容又无有效 tool_calls 的空 assistant（dangling 丢弃后可能出现）
            if asst.get("content") or asst.get("tool_calls"):
                out.append(asst)
        elif role == "tool":
            # 只发能对上 assistant tool_call 的结果；孤儿 tool 跳过
            if msg.get("tool_call_id") in kept_ids:
                out.append({
                    "role": "tool",
                    "tool_call_id": msg["tool_call_id"],
                    "content": msg["content"],
                })
        # 其他 role 忽略（防御性）

    return out


def _orm_to_dict(m: AgentMessageORM) -> dict:
    """ORM 消息转 dict 格式。"""
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "tool_calls": m.tool_calls,
        "tool_call_id": m.tool_call_id,
    }


# ===========================================================================
# v0.6 P1.6 — L2 记忆 helpers
# ===========================================================================


def _apply_memory_prepend(messages: list[dict], prepend: str) -> list[dict]:
    """把 relevant memories 块拼到第一条 user 消息前。

    设计:只对第一个 user role 消息拼接(本次 turn 的用户输入),
    不动后续 assistant / tool / system 消息,也不会重复注入。
    返回新列表(不修改入参),便于多次调用(build_messages 每次返回新列表即可)。
    """
    if not prepend:
        return messages
    out: list[dict] = []
    injected = False
    for m in messages:
        if not injected and m.get("role") == "user" and m.get("content"):
            out.append({**m, "content": prepend + "\n\n" + m["content"]})
            injected = True
        else:
            out.append(m)
    return out


async def _do_extract_after_turn(
    device_id: str | None,
    session_id: str,
    history: list[dict],
) -> None:
    """turn_complete 后 fire-and-forget 调。失败静默,不影响 turn。"""
    try:
        factory = get_session_factory()
        async with factory() as session:
            svc = MemoryService(session)
            await svc.extract(
                scope=scope_key(device_id, session_id),
                messages=history,
                session_id=session_id,
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "extract_after_turn_failed",
            session_id=session_id,
            error=str(e),
        )


# ===========================================================================
# Phase 1 — 埋点 helpers
# ===========================================================================


def _new_metrics() -> dict:
    return {
        "iterations": 0, "llm_calls": 0, "tool_calls": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "usage_seen": False,
    }


def _accumulate(agg: dict, usage: dict | None) -> None:
    agg["iterations"] += 1
    agg["llm_calls"] += 1
    if not usage:
        return
    agg["usage_seen"] = True
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        v = usage.get(k)
        if v is not None:
            agg[k] += v


def _emit_metrics(
    agg: dict, session_id: str, device_id: str | None, outcome: str
) -> None:
    logger.info(
        "agent_turn_metrics",
        session_id=session_id, device_id=device_id, outcome=outcome,
        iterations=agg["iterations"], llm_calls=agg["llm_calls"],
        tool_calls=agg["tool_calls"],
        prompt_tokens=agg["prompt_tokens"] if agg["usage_seen"] else None,
        completion_tokens=agg["completion_tokens"] if agg["usage_seen"] else None,
        total_tokens=agg["total_tokens"] if agg["usage_seen"] else None,
    )


# ===========================================================================
# ReAct 主循环
# ===========================================================================


async def _drive_react_loop(
    session_id: str,
    history: list[dict],
    device_id: str | None = None,
) -> AsyncIterator[dict]:
    """共享 ReAct 循环体。两入口做完各自起点差异后委托到此。

    产出的 SSE 事件流与收敛前逐事件等价。
    """
    settings = get_settings()
    llm = LLMClient(settings)
    factory = get_session_factory()
    scope = scope_key(device_id, session_id)

    async with factory() as session:
        memory_service = MemoryService(session)
        memory_index_segment = await memory_service.build_memory_segment(scope)
        memory_block = await memory_service.load_relevant_memories(scope, history)

    agg = _new_metrics()
    for _iteration in range(MAX_REACT_ITERATIONS):
        messages = build_messages(history, memory_index_segment=memory_index_segment)
        messages = _apply_memory_prepend(messages, memory_block)

        response = await llm.chat_with_tools(messages=messages, tools=TOOLS)
        _accumulate(agg, response.get("usage"))
        content = response.get("content")
        tool_calls = response.get("tool_calls") or []

        tc_for_db = None
        if tool_calls:
            tc_for_db = [
                {
                    "id": tc["id"],
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": json.dumps(tc["function"]["arguments"])
                        if isinstance(tc["function"]["arguments"], dict)
                        else tc["function"]["arguments"],
                    },
                }
                for tc in tool_calls
            ]
        async with factory() as session:
            repo = AgentRepository(session)
            await repo.create_message(
                session_id=session_id, role="assistant",
                content=content, tool_calls=tc_for_db,
            )

        yield {"event": "assistant_message", "content": content or ""}

        if tool_calls:
            executor = ToolExecutor(session_id)
            for tool_call in tool_calls:
                tool_id = tool_call["id"]
                tool_name = tool_call["function"]["name"]
                tool_args = tool_call["function"]["arguments"]
                if isinstance(tool_args, str):
                    tool_args = json.loads(tool_args)

                yield {
                    "event": "tool_call_start",
                    "tool_call_id": tool_id,
                    "tool_name": tool_name,
                    "arguments": tool_args,
                }
                agg["tool_calls"] += 1

                try:
                    result = await executor.execute(tool_name, tool_args)
                except Exception as exc:
                    from app.domain.exceptions import HumanConfirmationRequired

                    if isinstance(exc, HumanConfirmationRequired):
                        _emit_metrics(agg, session_id, device_id, "human_confirmation")
                        yield {
                            "event": "human_confirmation_required",
                            "message_id": exc.message_id,
                            "tool_name": exc.tool_name,
                            "arguments": exc.arguments,
                        }
                        return

                    err_payload = {"error": f"{type(exc).__name__}: {exc}"}
                    async with factory() as session:
                        repo = AgentRepository(session)
                        await repo.create_message(
                            session_id=session_id, role="tool",
                            content=json.dumps(err_payload, ensure_ascii=False),
                            tool_call_id=tool_id,
                        )
                    yield {
                        "event": "tool_call_result",
                        "tool_call_id": tool_id,
                        "result": err_payload,
                    }
                    continue

                async with factory() as session:
                    repo = AgentRepository(session)
                    await repo.create_message(
                        session_id=session_id, role="tool",
                        content=json.dumps(result, ensure_ascii=False),
                        tool_call_id=tool_id,
                    )
                yield {
                    "event": "tool_call_result",
                    "tool_call_id": tool_id,
                    "result": result,
                }

            async with factory() as session:
                repo = AgentRepository(session)
                history_rows = await repo.list_messages(session_id)
            history = [_orm_to_dict(m) for m in history_rows]
        else:
            task = asyncio.create_task(
                _do_extract_after_turn(device_id, session_id, history)
            )
            _PENDING_EXTRACTS.add(task)
            task.add_done_callback(_PENDING_EXTRACTS.discard)
            _emit_metrics(agg, session_id, device_id, "turn_complete")
            yield {"event": "turn_complete"}
            return

    _emit_metrics(agg, session_id, device_id, "max_iterations_reached")
    yield {
        "event": "max_iterations_reached",
        "message": f"agent 达到最大推理步数 ({MAX_REACT_ITERATIONS})",
    }


async def run_agent_turn(
    session_id: str,
    user_message: str,
    device_id: str | None = None,
) -> AsyncIterator[dict]:
    """执行一轮 agent 推理 + 行动循环。流式 yield SSE 事件。

    起点差异:加载历史 → 保存 user 消息 → 委托共享循环。
    """
    factory = get_session_factory()

    # 1. 加载历史 + 2. 保存 user 消息
    async with factory() as session:
        repo = AgentRepository(session)
        history_rows = await repo.list_messages(session_id)
        await repo.create_message(
            session_id=session_id, role="user", content=user_message
        )
    history = [_orm_to_dict(m) for m in history_rows] + [
        {"role": "user", "content": user_message}
    ]

    async for evt in _drive_react_loop(session_id, history, device_id):
        yield evt


# ===========================================================================
# 断点续跑（用户决策要求：不是 MVP）
# ===========================================================================


async def run_agent_turn_from_checkpoint(
    session_id: str,
    checkpoint_message_id: str,
    device_id: str | None = None,
) -> AsyncIterator[dict]:
    """从 pending_confirmation 消息处继续执行。

    适用场景：
    1. 用户首次输入"生成文章"
    2. agent 调 generate_article → ToolExecutor 抛 HumanConfirmationRequired（落 pending msg）
    3. ReAct 循环 yield human_confirmation_required 后暂停
    4. 前端弹窗，用户点"确认"
    5. POST /sessions/{sid}/messages/{msg_id}/confirm {approved: true}
    6. 调本函数：
       a. 找到 checkpoint message，解析其 tool_calls[0].arguments
       b. 调 _execute_generate_article_confirmed(args, checkpoint_message_id) → 真正生成预览
       c. 保存 tool 消息（作为该 pending msg 的结果）
       d. 继续 ReAct 循环（重新加载历史 + 调 LLM）

    异常处理：
    - 如果 checkpoint_message_id 不存在或已 resolved：yield error 并退出
    """
    from app.domain.agent.tools import GenerateArticleArgs

    factory = get_session_factory()

    # 1. 找到 checkpoint message
    async with factory() as session:
        repo = AgentRepository(session)
        ckpt_msg = await repo.get_message(checkpoint_message_id)

    if ckpt_msg is None or ckpt_msg.session_id != session_id:
        yield {
            "event": "error",
            "message": f"checkpoint message {checkpoint_message_id} not found",
        }
        return
    if not ckpt_msg.pending_confirmation:
        yield {
            "event": "error",
            "message": f"checkpoint message {checkpoint_message_id} already resolved",
        }
        return

    # 2. 解析 pending message 的 tool_calls，提取 generate_article args
    if not ckpt_msg.tool_calls:
        yield {"event": "error", "message": "no tool_calls in checkpoint message"}
        return
    tc_list = json.loads(ckpt_msg.tool_calls) if isinstance(ckpt_msg.tool_calls, str) else ckpt_msg.tool_calls
    if not tc_list:
        yield {"event": "error", "message": "empty tool_calls in checkpoint message"}
        return

    # 兼容两种格式：OpenAI 风格 (function.name + function.arguments) 或简化风格 (tool + arguments)
    first_tc = tc_list[0]
    if "function" in first_tc:
        # OpenAI 风格
        if first_tc["function"]["name"] != "generate_article":
            yield {
                "event": "error",
                "message": f"checkpoint tool is {first_tc['function']['name']}, expected generate_article",
            }
            return
        args_raw = first_tc["function"]["arguments"]
        if isinstance(args_raw, str):
            args_dict = json.loads(args_raw)
        else:
            args_dict = args_raw
    elif "tool" in first_tc:
        # 简化风格（向后兼容旧数据）
        if first_tc["tool"] != "generate_article":
            yield {
                "event": "error",
                "message": f"checkpoint tool is {first_tc['tool']}, expected generate_article",
            }
            return
        args_dict = first_tc["arguments"]
    else:
        yield {"event": "error", "message": "unrecognized tool_calls format"}
        return

    args = GenerateArticleArgs.model_validate(args_dict)
    # tool_call_id 必须与 assistant 消息的 tool_calls[0].id 一致（OpenAI 协议）。
    # _execute_generate_article 写入时 id=message_id，所以这里用 checkpoint_message_id。
    pending_tool_id = checkpoint_message_id

    # 3. 调 _execute_generate_article_confirmed
    # 注意：confirm_message 已在 API 层 (agent_chat.confirm_action) 调用过，
    # 这里不再重复，否则 idempotent 重复执行（不会出错，但浪费）。
    executor = ToolExecutor(session_id)
    try:
        confirmed_result = await executor._execute_generate_article_confirmed(
            args, checkpoint_message_id
        )
    except NotImplementedError:
        # 占位 stub：完整 ContentWriter 实现在后续集成阶段补
        yield {
            "event": "error",
            "message": "_execute_generate_article_confirmed not yet implemented",
        }
        return
    except Exception as exc:  # noqa: BLE001
        yield {
            "event": "error",
            "message": f"confirmed generation failed: {type(exc).__name__}: {exc}",
        }
        return

    # 5. 保存 tool 消息 + yield result
    async with factory() as session:
        repo = AgentRepository(session)
        await repo.create_message(
            session_id=session_id, role="tool",
            content=json.dumps(confirmed_result, ensure_ascii=False),
            tool_call_id=pending_tool_id,
        )

    yield {
        "event": "tool_call_result",
        "tool_call_id": pending_tool_id,
        "result": confirmed_result,
    }

    # 6. 继续 ReAct 循环（委托共享驱动，基于新 tool 结果继续决策）
    async with factory() as session:
        repo = AgentRepository(session)
        history_rows = await repo.list_messages(session_id)
    history = [_orm_to_dict(m) for m in history_rows]

    async for evt in _drive_react_loop(session_id, history, device_id):
        yield evt