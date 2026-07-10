"""Async worker for content generation tasks."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import jieba
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session_factory
from app.domain.generator.content_writer import ContentWriter
from app.domain.knowledge.retriever import search_chunks
from app.repositories.task_repo import TaskRepository

logger = structlog.get_logger()

# Reuse the v0.1 global lock for single-flight execution
_EXEC_LOCK = asyncio.Lock()


async def _process_one(
    task: Any,
    index: int,
    article: Any,
    task_repo: TaskRepository,
    writer: ContentWriter,
    top_k: int,
    default_provider: str,
) -> None:
    """Generate one article. On failure, mark article with error and continue."""
    try:
        # Keyword retrieval using jieba
        keywords_list = json.loads(task.keywords or "[]")
        query = task.topic + " " + " ".join(keywords_list)
        keywords = [w for w in jieba.cut(query) if len(w.strip()) > 1]
        chunks = await search_chunks(
            session=task_repo.session,
            kb_id=task.kb_id,
            keywords=keywords,
            top_k=top_k,
        )

        chunks_for_prompt = [
            {"index": i + 1, "content": c.content} for i, c in enumerate(chunks)
        ]

        title, content = await writer.write_article(
            brand=task.brand,
            topic=task.topic,
            keywords=keywords_list,
            style=task.style,
            target_length=task.target_length,
            chunks=chunks_for_prompt,
        )

        if not content:
            await task_repo.update_article(
                article.id,
                title=f"生成失败 #{index + 1}",
                error_message="LLM 调用失败",
            )
            return

        await task_repo.update_article(
            article.id,
            title=title,
            content=content,
            content_length=len(content),
            cited_chunks=[c.id for c in chunks],
            llm_provider=default_provider,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("article_generation_failed", article_id=article.id)
        await task_repo.update_article(
            article.id,
            title=f"生成失败 #{index + 1}",
            error_message=f"{type(e).__name__}: {e}",
        )


async def _run_with_session(
    task_id: str,
    session: AsyncSession,
    settings: Settings,
    default_provider: str,
) -> None:
    task_repo = TaskRepository(session)
    task = await task_repo.get_task(task_id)
    if task is None:
        logger.error("task_not_found", task_id=task_id)
        return

    # Already cancelled? Skip.
    if task.status == "cancelled":
        return

    try:
        task.status = "running"
        await task_repo.session.commit()

        # Create placeholder articles
        for i in range(task.article_count):
            await task_repo.create_article(task_id, index=i)

        articles = await task_repo.list_articles(task_id)
        writer = ContentWriter(settings)

        for i, article in enumerate(articles):
            # Re-check status before each article (cancellable mid-run)
            current = await task_repo.get_task(task_id)
            if current is None or current.status == "cancelled":
                logger.info("task_cancelled", task_id=task_id, after=i)
                break
            await _process_one(
                task,
                i,
                article,
                task_repo,
                writer,
                settings.retrieval_top_k,
                default_provider,
            )
            progress = int((i + 1) / task.article_count * 100)
            await task_repo.update_task_status(
                task_id, status="running", progress=progress
            )

        task = await task_repo.get_task(task_id)
        if task and task.status != "cancelled":
            task.status = "completed"
            task.progress = 100
            await task_repo.session.commit()
    except Exception as e:  # noqa: BLE001
        logger.exception("task_failed", task_id=task_id)
        await task_repo.update_task_status(
            task_id, status="failed", error=f"{type(e).__name__}: {e}"
        )


async def run_task(task_id: str, session: AsyncSession | None = None) -> None:
    """Execute the full task pipeline.

    If `session` is provided, use it directly (lets tests share the
    fixture's session to avoid cross-transaction visibility issues).
    Otherwise create a new session from the global factory.
    """
    settings = get_settings()
    default_provider = (
        settings.enabled_providers[0] if settings.enabled_providers else "deepseek"
    )

    if session is not None:
        await _run_with_session(task_id, session, settings, default_provider)
    else:
        factory = get_session_factory()
        async with factory() as s:
            await _run_with_session(task_id, s, settings, default_provider)


async def execute_task_with_lock(task_id: str) -> None:
    """Wrap run_task with the v0.1 lock for single-flight execution."""
    async with _EXEC_LOCK:
        await run_task(task_id)


def schedule_task(task_id: str) -> asyncio.Task[None]:
    """Fire-and-forget background execution with lock."""
    return asyncio.create_task(execute_task_with_lock(task_id))
