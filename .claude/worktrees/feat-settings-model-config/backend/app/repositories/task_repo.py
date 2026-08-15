"""Repository for tasks and articles."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v02 import ArticleORM, TaskORM


def _article_placeholder_title(index: int) -> str:
    return f"待生成 #{index + 1}"


class TaskRepository:
    """Data access for tasks and articles."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Tasks ---

    async def create_task(
        self,
        name: str,
        kb_id: str,
        topic: str,
        article_count: int,
        style: str,
        brand: str | None = None,
        keywords: list[str] | None = None,
        target_length: int = 1500,
    ) -> TaskORM:
        task = TaskORM(
            id=str(uuid.uuid4()),
            name=name,
            kb_id=kb_id,
            brand=brand,
            topic=topic,
            keywords=json.dumps(keywords or [], ensure_ascii=False),
            article_count=article_count,
            style=style,
            target_length=target_length,
            status="pending",
            progress=0,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_task(self, task_id: str) -> TaskORM | None:
        result = await self.session.execute(
            select(TaskORM).where(TaskORM.id == task_id)
        )
        return result.scalar_one_or_none()

    async def list_tasks(self) -> list[TaskORM]:
        result = await self.session.execute(
            select(TaskORM).order_by(TaskORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_tasks_by_status(self, status: str) -> list[TaskORM]:
        result = await self.session.execute(
            select(TaskORM)
            .where(TaskORM.status == status)
            .order_by(TaskORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: int | None = None,
        error: str | None = None,
    ) -> None:
        task = await self.get_task(task_id)
        if task is None:
            return
        task.status = status
        if progress is not None:
            task.progress = progress
        if error is not None:
            task.error_message = error
        task.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def delete_task(self, task_id: str) -> None:
        await self.session.execute(
            delete(TaskORM).where(TaskORM.id == task_id)
        )
        await self.session.commit()

    # --- Articles ---

    async def create_article(self, task_id: str, index: int = 0) -> ArticleORM:
        article = ArticleORM(
            id=str(uuid.uuid4()),
            task_id=task_id,
            title=_article_placeholder_title(index),
            review_status="pending",
            cited_chunks=json.dumps([]),
        )
        self.session.add(article)
        await self.session.commit()
        await self.session.refresh(article)
        return article

    async def get_article(self, article_id: str) -> ArticleORM | None:
        result = await self.session.execute(
            select(ArticleORM).where(ArticleORM.id == article_id)
        )
        return result.scalar_one_or_none()

    async def list_articles(self, task_id: str) -> list[ArticleORM]:
        result = await self.session.execute(
            select(ArticleORM)
            .where(ArticleORM.task_id == task_id)
            .order_by(ArticleORM.created_at)
        )
        return list(result.scalars().all())

    async def list_articles_by_status(
        self, review_status: str, task_id: str | None = None
    ) -> list[ArticleORM]:
        stmt = select(ArticleORM).where(ArticleORM.review_status == review_status)
        if task_id is not None:
            stmt = stmt.where(ArticleORM.task_id == task_id)
        stmt = stmt.order_by(ArticleORM.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_article(
        self,
        article_id: str,
        title: str | None = None,
        content: str | None = None,
        content_length: int | None = None,
        cited_chunks: list[str] | None = None,
        llm_provider: str | None = None,
        error_message: str | None = None,
    ) -> None:
        article = await self.get_article(article_id)
        if article is None:
            return
        if title is not None:
            article.title = title
        if content is not None:
            article.content = content
            article.content_length = content_length
        if cited_chunks is not None:
            article.cited_chunks = json.dumps(cited_chunks, ensure_ascii=False)
        if llm_provider is not None:
            article.llm_provider = llm_provider
        if error_message is not None:
            article.error_message = error_message
        article.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_article_review(
        self,
        article_id: str,
        status: str,
        note: str | None = None,
    ) -> None:
        article = await self.get_article(article_id)
        if article is None:
            return
        article.review_status = status
        article.review_note = note
        article.reviewed_at = datetime.now(timezone.utc)
        article.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
