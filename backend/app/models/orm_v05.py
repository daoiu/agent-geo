"""SQLAlchemy ORM models for v0.6+ (multi-agent handoff log).

v0.6+ Multi-Agent 改造:
- HandoffLogORM — 主 Agent → Specialist handoff 的全量日志(纪律 5 成本归因基础)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.orm import Base, _utcnow


class HandoffLogORM(Base):
    """主 Agent → Specialist 委派的持久化日志。

    用于:
    - 纪律 1 幂等键查询(check_idempotency)
    - 纪律 5 成本 dashboard(按 specialist / status 聚合)
    - 失败率 / 超时率监控
    """

    __tablename__ = "handoff_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # = handoff_id
    specialist: Mapped[str] = mapped_column(String(32), index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True)  # success/failed/timeout/cancelled
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_handoff_log_specialist_started", "specialist", "started_at"),
        Index("ix_handoff_log_session_started", "session_id", "started_at"),
    )
