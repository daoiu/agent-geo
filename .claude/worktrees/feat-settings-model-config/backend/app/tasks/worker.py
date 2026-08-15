"""Async background worker for executing diagnosis tasks."""
from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.domain.crawler import Crawler
from app.domain.llm_client import LLMClient
from app.models.schemas import DiagnosisRequest
from app.repositories.report_repo import ReportRepository
from app.services.diagnosis_service import DiagnosisService

logger = structlog.get_logger()

# Single global lock — MVP allows only one diagnosis at a time
_EXEC_LOCK = asyncio.Lock()


async def execute_diagnosis(task_id: str, request: DiagnosisRequest) -> None:
    """Run one diagnosis in the background.

    Acquires a global lock so only one runs at a time. Other tasks
    submitted while one is running remain in 'pending' state and will
    be picked up after the lock is released.
    """
    async with _EXEC_LOCK:
        logger.info("diagnosis_starting", task_id=task_id)
        await _run_one(task_id, request)


async def _run_one(task_id: str, request: DiagnosisRequest) -> None:
    """Execute the pipeline for one task."""
    from app.core.db import get_session_factory

    settings = get_settings()
    factory = get_session_factory()

    async with factory() as session:
        repo = ReportRepository(session)
        crawler = Crawler(settings)
        llm = LLMClient(settings)
        try:
            svc = DiagnosisService(repo=repo, crawler=crawler, llm=llm, settings=settings)
            await svc.run(task_id, request)
        finally:
            await crawler.close()


def schedule_diagnosis(task_id: str, request: DiagnosisRequest) -> asyncio.Task[None]:
    """Fire-and-forget background execution. Returns the asyncio.Task."""
    return asyncio.create_task(execute_diagnosis(task_id, request))
