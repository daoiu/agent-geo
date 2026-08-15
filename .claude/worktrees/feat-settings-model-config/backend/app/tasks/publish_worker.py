"""Async worker for publish jobs (shared _EXEC_LOCK with v0.1/v0.2)."""
from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.publisher.publisher_service import PublishService
from app.repositories.publisher_repo import PublishRepository

logger = structlog.get_logger()
_EXEC_LOCK = asyncio.Lock()


async def execute_publish(publish_job_id: str) -> None:
    """Execute one publish job. Called directly in tests; wrapped in lock in schedule."""
    factory = get_session_factory()
    settings = get_settings()
    async with factory() as session:
        repo = PublishRepository(session)
        svc = PublishService(repo=repo, settings=settings)
        await svc.execute_publish(publish_job_id)


async def execute_with_lock(publish_job_id: str) -> None:
    async with _EXEC_LOCK:
        await execute_publish(publish_job_id)


def schedule_publish(publish_job_id: str) -> asyncio.Task[None]:
    """Fire-and-forget background execution."""
    return asyncio.create_task(execute_with_lock(publish_job_id))
