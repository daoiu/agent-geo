"""v0.4 Agent session CRUD API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.models.agent import (
    AgentMessage,
    AgentSession,
    AgentSessionDetail,
    CreateSessionRequest,
    UpdateSessionRequest,
)
from app.repositories.agent_repo import AgentRepository

router = APIRouter(prefix="/agent/sessions", tags=["agent"])


@router.post("", status_code=201, response_model=AgentSession)
async def create_session(
    body: CreateSessionRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentSession:
    """创建新 session。"""
    repo = AgentRepository(session)
    s = await repo.create_session(title=body.title)
    return s


@router.get("", response_model=list[AgentSession])
async def list_sessions(
    session: AsyncSession = Depends(get_session),
) -> list[AgentSession]:
    """列出最近 50 个 session。"""
    repo = AgentRepository(session)
    return await repo.list_sessions(limit=50)


@router.get("/{session_id}", response_model=AgentSessionDetail)
async def get_session_detail(
    session_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentSessionDetail:
    """获取 session 详情 + 完整消息历史。"""
    repo = AgentRepository(session)
    sess = await repo.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    messages = await repo.list_messages(session_id)
    return AgentSessionDetail(
        id=sess.id,
        title=sess.title,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
        messages=[AgentMessage.model_validate(m) for m in messages],
    )


@router.delete("/{session_id}", status_code=204, response_class=Response)
async def delete_session(
    session_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """删除 session。"""
    repo = AgentRepository(session)
    sess = await repo.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    await repo.delete_session(session_id)
    return Response(status_code=204)


@router.patch("/{session_id}", response_model=AgentSession)
async def update_session_title(
    session_id: str,
    body: UpdateSessionRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentSession:
    """更新 session 标题。"""
    repo = AgentRepository(session)
    await repo.update_session_title(session_id, title=body.title)
    sess = await repo.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    return sess