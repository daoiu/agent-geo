"""v0.4 Agent Chat API：SSE 流式 chat + 确认端点(支持断点续跑)。

v0.6 P1.6 — 加 `X-Device-Id` 依赖(L2 跨会话偏好用)。

CR-2:event_generator 直接 yield bytes(spec L445 字节契约,resume_from_checkpoint
和 run_agent_turn 现都产 SSE 字节流),StreamingResponse 透传。
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import device_id_header
from app.api.diagnosis import get_session
from app.domain.agent.dispatch import run_agent_turn
from app.domain.agent.langgraph_nodes.resume import resume_from_checkpoint
from app.repositories.agent_repo import AgentRepository


def _replay_marker_bytes(session_id: str, message_id: str) -> bytes:
    """SSE 'replay_start' 标记事件字节(replay_turn 端点前置)。"""
    return (
        f"event: replay_start\n"
        f"data: {json.dumps({'message_id': message_id, 'session_id': session_id}, ensure_ascii=False)}\n\n"
    ).encode("utf-8")


async def run_replay(
    session_id: str,
    message_id: str,
    device_id: str | None = None,
) -> AsyncIterator[bytes]:
    """P2#32 / Task 41: 从任意 message_id 重放 turn(产 SSE 字节流)。"""
    yield _replay_marker_bytes(session_id, message_id)
    async for sse_bytes in resume_from_checkpoint(
        session_id, message_id, device_id=device_id
    ):
        yield sse_bytes

router = APIRouter(prefix="/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# 请求体
# ---------------------------------------------------------------------------


class SendMessageRequest(BaseModel):
    """发送 user message 请求体。"""

    content: str = Field(..., min_length=1, max_length=4000)


class ConfirmActionRequest(BaseModel):
    """确认 / 取消 human-in-the-loop 工具调用。

    v0.6+ P1#26(Task 27):
    - reason: 可选,reject 时记录用户拒绝原因,作为 user 消息写入历史,
      LLM 下次 turn 能看到并据此调整(避免重复同类请求)
    - approved=True 时 reason 被忽略
    """

    approved: bool
    reason: str | None = None


# ---------------------------------------------------------------------------
# SSE 端点
# ---------------------------------------------------------------------------


@router.post("/sessions/{session_id}/messages", response_model=None)
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    session: AsyncSession = Depends(get_session),
    device_id: str | None = Depends(device_id_header),
):
    """发送 user message,流式返回 agent 的 SSE 字节流(react_loop 等价)。"""
    repo = AgentRepository(session)
    sess = await repo.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")

    async def event_generator() -> AsyncIterator[bytes]:
        async for sse_bytes in run_agent_turn(
            session_id, body.content, device_id=device_id
        ):
            yield sse_bytes

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.post(
    "/sessions/{session_id}/messages/{message_id}/confirm",
    response_model=None,
)
async def confirm_action(
    session_id: str,
    message_id: str,
    body: ConfirmActionRequest,
    session: AsyncSession = Depends(get_session),
    device_id: str | None = Depends(device_id_header),
):
    """确认或取消 human-in-the-loop 工具调用。

    approved=False:标记 resolved + 写"取消"消息 + 返回 JSON。
    approved=True:调 resume_from_checkpoint 从断点续跑并 stream SSE 字节流。
    """
    repo = AgentRepository(session)
    msg = await repo.get_message(message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="message not found")
    if msg.session_id != session_id:
        raise HTTPException(
            status_code=404, detail="message does not belong to this session"
        )
    if not msg.pending_confirmation:
        raise HTTPException(
            status_code=409, detail="message is not pending confirmation"
        )

    if not body.approved:
        # 拒绝:标记 resolved + 追加 user/assistant 消息
        # v0.6+ P1#26(Task 27):有 reason 时用 reason 作为 user 消息(LLM 下次可见)
        await repo.confirm_message(message_id, approved=False)
        user_content = (body.reason or "").strip() or "取消"
        await repo.create_message(session_id=session_id, role="user", content=user_content)
        await repo.create_message(
            session_id=session_id, role="assistant", content="好的，已取消。"
        )
        return Response(
            content=json.dumps({"status": "cancelled", "message_id": message_id}, ensure_ascii=False),
            media_type="application/json",
        )

    # approved=True:标记 resolved 并 stream 续跑 SSE 字节流
    await repo.confirm_message(message_id, approved=True)

    async def event_generator() -> AsyncIterator[bytes]:
        async for sse_bytes in resume_from_checkpoint(
            session_id, message_id, device_id=device_id
        ):
            yield sse_bytes

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# v0.7+ P2#32(Task 41): 显式 replay API — 从任意 message_id 重放 turn
# ---------------------------------------------------------------------------


@router.post(
    "/sessions/{session_id}/replay/{message_id}",
    response_model=None,
)
async def replay_turn(
    session_id: str,
    message_id: str,
    session: AsyncSession = Depends(get_session),
    device_id: str | None = Depends(device_id_header),
):
    """从任意 message 重放 turn(P2#32 / Task 41)。

    与 confirm 的区别:
    - confirm: 仅对 pending_confirmation 续跑
    - replay: 任意 message(包括 user / 已完成) — 用于调试 / A/B 测试

    流格式:先 yield `replay_start` 标记字节,然后调 resume_from_checkpoint 输出完整 SSE 字节流。
    """
    repo = AgentRepository(session)
    msg = await repo.get_message(message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="message not found")
    if msg.session_id != session_id:
        raise HTTPException(
            status_code=404, detail="message does not belong to this session"
        )

    async def event_generator() -> AsyncIterator[bytes]:
        yield _replay_marker_bytes(session_id, message_id)
        async for sse_bytes in resume_from_checkpoint(
            session_id, message_id, device_id=device_id
        ):
            yield sse_bytes

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )