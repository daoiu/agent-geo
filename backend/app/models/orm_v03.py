"""SQLAlchemy ORM models for v0.3 (publishers, monitor tasks, snapshots)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, REAL, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.orm import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PublisherConfigORM(Base):
    """WordPress site credentials for publishing."""

    __tablename__ = "publisher_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    site_url: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    app_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )


class PublishJobORM(Base):
    """One publish attempt of an Article to a WordPress site."""

    __tablename__ = "publish_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    article_id: Mapped[str] = mapped_column(
        String, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    config_id: Mapped[str] = mapped_column(
        String, ForeignKey("publisher_configs.id", ondelete="RESTRICT"), nullable=False
    )
    title_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    remote_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class MonitorTaskORM(Base):
    """A long-running monitor: periodically query LLM and record snapshots."""

    __tablename__ = "monitor_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str] = mapped_column(String, nullable=False)
    industry: Mapped[str] = mapped_column(String, nullable=False)
    target_questions: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    frequency: Mapped[str] = mapped_column(String, default="daily", nullable=False)
    providers: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    notify_email: Mapped[str | None] = mapped_column(String, nullable=True)
    change_threshold: Mapped[float] = mapped_column(REAL, default=0.15, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class MentionSnapshotORM(Base):
    """Result of one monitor execution."""

    __tablename__ = "mention_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    monitor_task_id: Mapped[str] = mapped_column(
        String, ForeignKey("monitor_tasks.id", ondelete="CASCADE"), nullable=False
    )
    run_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    mention_rate: Mapped[float] = mapped_column(REAL, nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_position: Mapped[float | None] = mapped_column(REAL, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
