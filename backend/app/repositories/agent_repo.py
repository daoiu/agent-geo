"""Agent 数据访问层（v0.4）：agent_sessions + agent_messages CRUD。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v04 import AgentMessageORM, AgentSessionORM


_DEFAULT_TITLE = "新对话"


class AgentRepository:
    """v0.4 agent 表的数据访问。

    所有方法都需要绑定了事务的 AsyncSession（依赖注入）。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

    async def create_session(self, title: str | None = None) -> AgentSessionORM:
        """创建会话，title 为 None 时使用默认。"""
        s = AgentSessionORM(
            id=str(uuid.uuid4()),
            title=title or _DEFAULT_TITLE,
        )
        self.session.add(s)
        await self.session.commit()
        await self.session.refresh(s)
        return s

    async def get_session(self, id: str) -> AgentSessionORM | None:
        """按 id 查 session，不存在返回 None。"""
        result = await self.session.execute(
            select(AgentSessionORM).where(AgentSessionORM.id == id)
        )
        return result.scalar_one_or_none()

    async def list_sessions(self, limit: int = 50) -> list[AgentSessionORM]:
        """按 updated_at 倒序列出最近会话。"""
        result = await self.session.execute(
            select(AgentSessionORM)
            .order_by(AgentSessionORM.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_session(self, id: str) -> None:
        """删除 session，级联删除其消息。"""
        await self.session.execute(
            delete(AgentSessionORM).where(AgentSessionORM.id == id)
        )
        await self.session.commit()

    async def update_session_title(self, id: str, title: str) -> None:
        """更新 title 并 bump updated_at。id 不存在时静默忽略。"""
        s = await self.get_session(id)
        if s is None:
            return
        s.title = title
        s.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_session_timestamp(self, id: str) -> None:
        """bump session 的 updated_at（用于'最近活跃'排序）。"""
        s = await self.get_session(id)
        if s is None:
            return
        s.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Message
    # ------------------------------------------------------------------

    async def create_message(
        self,
        session_id: str,
        role: str,
        content: str | None = None,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
        pending_confirmation: bool = False,
    ) -> AgentMessageORM:
        """创建消息并 bump session 的 updated_at。"""
        m = AgentMessageORM(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
            tool_call_id=tool_call_id,
            pending_confirmation=1 if pending_confirmation else 0,
        )
        self.session.add(m)
        await self.session.commit()
        await self.session.refresh(m)
        # bump session timestamp
        await self.update_session_timestamp(session_id)
        return m

    async def get_message(self, id: str) -> AgentMessageORM | None:
        """按 id 查 message。"""
        result = await self.session.execute(
            select(AgentMessageORM).where(AgentMessageORM.id == id)
        )
        return result.scalar_one_or_none()

    async def list_messages(self, session_id: str) -> list[AgentMessageORM]:
        """按 created_at 升序列出某 session 的所有消息。"""
        result = await self.session.execute(
            select(AgentMessageORM)
            .where(AgentMessageORM.session_id == session_id)
            .order_by(AgentMessageORM.created_at)
        )
        return list(result.scalars().all())

    async def confirm_message(self, id: str, approved: bool) -> None:
        """把 pending_confirmation 标回 0（resolved）。

        无论 approved True/False，都视为用户已处理这条 pending 消息。
        '取消' / '拒绝' 的语义由 API 层写入新消息表达。
        id 不存在时静默忽略。
        """
        m = await self.get_message(id)
        if m is None:
            return
        m.pending_confirmation = 0
        await self.session.commit()