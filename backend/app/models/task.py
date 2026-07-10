"""Pydantic models for tasks, articles, reviews."""
from __future__ import annotations

import json
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Style(str, Enum):
    NEUTRAL = "neutral"
    PROFESSIONAL = "professional"
    CASUAL = "casual"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISE_REQUESTED = "revise_requested"


class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    kb_id: str
    brand: str | None = Field(None, max_length=100)
    topic: str = Field(..., min_length=5, max_length=500)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    article_count: int = Field(1, ge=1, le=20)
    style: Style = Style.NEUTRAL
    target_length: int = Field(1500, ge=300, le=10000)


class Task(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kb_id: str
    brand: str | None
    topic: str
    keywords: list[str]
    article_count: int
    style: Style
    target_length: int
    status: TaskStatus
    progress: int = Field(..., ge=0, le=100)
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class Article(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    title: str | None
    content: str | None
    content_length: int | None
    review_status: ReviewStatus
    review_note: str | None
    reviewed_at: datetime | None
    cited_chunks: list[str] = Field(default_factory=list)
    llm_provider: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_obj(cls, article) -> "Article":
        """Convert ORM ArticleORM → Pydantic Article (parses cited_chunks JSON).

        Single source of truth used by both tasks.py and reviews.py.
        """
        cited = json.loads(article.cited_chunks or "[]")
        return cls(
            id=article.id,
            task_id=article.task_id,
            title=article.title,
            content=article.content,
            content_length=article.content_length,
            review_status=article.review_status,  # type: ignore[arg-type]
            review_note=article.review_note,
            reviewed_at=article.reviewed_at,
            cited_chunks=cited,
            llm_provider=article.llm_provider,
            error_message=article.error_message,
            created_at=article.created_at,
            updated_at=article.updated_at,
        )


class ReviewAction(BaseModel):
    """Action body for approve / reject endpoints."""

    note: str | None = Field(None, max_length=2000)


class TaskWithArticles(Task):
    """Task detail response shape: Task fields + nested articles list."""

    articles: list[Article] = Field(default_factory=list)
