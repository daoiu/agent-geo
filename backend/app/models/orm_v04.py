"""SQLAlchemy ORM models for v0.4 (agent sessions and messages).

v0.6 P1.6: 新增 AgentMemoryORM — 跨会话偏好层(L2)
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.orm import Base, _utcnow


class AgentSessionORM(Base):
    """An Agent conversation session."""

    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class AgentMessageORM(Base):
    """A single message in an agent session (user/assistant/tool/system)."""

    __tablename__ = "agent_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)  # user/assistant/tool/system
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    tool_call_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pending_confirmation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )


class AgentMemoryORM(Base):
    """A single long-term memory (cross-session preference/fact).

    v0.6 P1.6 (L2 层):scope = device_id 或 `anon:<session_id>`。
    每条记忆归一类:user / feedback / project / reference。
    `body_md` 完整 markdown,前三列做索引常驻 SYSTEM prompt。
    """

    __tablename__ = "agent_memories"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(_uuid.uuid4()),
    )
    scope: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("scope", "name", name="uq_agent_memories_scope_name"),
        Index("idx_agent_memories_scope_mtime", "scope", "updated_at"),
    )