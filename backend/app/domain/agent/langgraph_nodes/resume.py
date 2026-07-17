"""T7 — HITL generate_article 确认续跑(迁自 react_loop.run_agent_turn_from_checkpoint)。

react_loop 路径:L596-717 手动解析 checkpoint tool_calls、调 _execute_generate_article_
confirmed、写 tool message、yield tool_call_result、继续 ReAct 循环。

react_graph 路径:LangGraph 自带 interrupt / resume 机制 — tool 节点抛
HumanConfirmation → interrupt(payload) → LangGraph 持久化 checkpoint → 前端
确认 → resume_from_checkpoint(session_id, checkpoint_message_id) 用
Command(resume=user_decision) + graph.astream_events 续跑,LangGraph 自动
从 interrupt 处恢复,经 SSEBridge._dispatch 输出 SSE 字节。

校验逻辑(沿用 react_loop L596-417 的契约):
- checkpoint_message_id 不存在 / 不属于 session_id / 已 resolved → yield error 事件退出
- 解析失败(无 tool_calls)→ yield error 事件退出
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import structlog

from app.core.db import get_session_factory
from app.domain.agent.langgraph_nodes.policy import resume_command
from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge
from app.domain.agent.react_graph import build_react_graph
from app.repositories.agent_repo import AgentRepository

logger = structlog.get_logger()


def _emit(event_type: str, data: dict) -> bytes:
    payload = {"event": event_type, **data}
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


async def resume_from_checkpoint(
    session_id: str,
    checkpoint_message_id: str,
    device_id: str | None = None,
    user_decision: dict | None = None,
) -> AsyncIterator[bytes]:
    """HITL generate_article 确认续跑入口(react_loop 等价)。

    与 react_loop.run_agent_turn_from_checkpoint 行为字节级对齐:
    - 同样的校验(缺失 / 已 resolved / 格式不识别 → yield error)
    - 同样的 SSE 字节流(经 SSEBridge._dispatch 输出 7 类事件 + turn_complete)
    - 同样的 session_id / device_id 关联

    user_decision 默认为 {"approved": True}(generate_article 确认)。
    """
    factory = get_session_factory()

    # 1. 找到 checkpoint message
    async with factory() as session:
        repo = AgentRepository(session)
        ckpt_msg = await repo.get_message(checkpoint_message_id)

    if ckpt_msg is None or ckpt_msg.session_id != session_id:
        yield _emit("error", {
            "message": f"checkpoint message {checkpoint_message_id} not found",
        })
        return
    if not ckpt_msg.pending_confirmation:
        yield _emit("error", {
            "message": f"checkpoint message {checkpoint_message_id} already resolved",
        })
        return

    # 2. 解析 tool_calls 校验(react_loop L382-417 等价)
    if not ckpt_msg.tool_calls:
        yield _emit("error", {"message": "no tool_calls in checkpoint message"})
        return
    tc_list = (
        json.loads(ckpt_msg.tool_calls)
        if isinstance(ckpt_msg.tool_calls, str)
        else ckpt_msg.tool_calls
    )
    if not tc_list:
        yield _emit("error", {"message": "empty tool_calls in checkpoint message"})
        return
    first_tc = tc_list[0]
    if "function" in first_tc:
        if first_tc["function"]["name"] != "generate_article":
            yield _emit("error", {
                "message": (
                    f"checkpoint tool is {first_tc['function']['name']}, "
                    "expected generate_article"
                ),
            })
            return
    elif "tool" in first_tc:
        if first_tc["tool"] != "generate_article":
            yield _emit("error", {
                "message": (
                    f"checkpoint tool is {first_tc['tool']}, "
                    "expected generate_article"
                ),
            })
            return
    else:
        yield _emit("error", {"message": "unrecognized tool_calls format"})
        return

    # 3. 用 LangGraph Command(resume=...) 续跑,经 SSEBridge 输出 SSE 字节
    decision = user_decision or {"approved": True}
    command = resume_command(decision)
    graph = build_react_graph()
    bridge = SSEBridge()
    # 初始化 bridge 状态(react_graph 路径 T4)
    bridge._session_id = session_id
    bridge._device_id = device_id
    bridge._turn_start = None  # resume 不计入 turn_duration
    bridge._primary_provider = None

    try:
        async for event in graph.astream_events(
            command,
            config={"configurable": {"thread_id": session_id}},
            version="v2",
        ):
            async for sse in bridge._dispatch(event):
                yield sse
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "resume_failed",
            session_id=session_id,
            checkpoint_message_id=checkpoint_message_id,
            error=str(exc),
        )
        yield _emit("error", {
            "message": f"resume failed: {type(exc).__name__}: {exc}",
        })