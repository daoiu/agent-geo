"""Tests for the DiagnosisService orchestration."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.domain.crawler import Crawler
from app.domain.llm_client import LLMClient
from app.models.schemas import (
    DiagnosisRequest,
    DimensionScore,
    EeatSignals,
    FreshnessScore,
    MentionResult,
    SchemaCoverage,
    ScoreCard,
    SiteAudit,
    StructureScore,
)
from app.services.diagnosis_service import DiagnosisService


@pytest.fixture
def settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        llm_call_timeout_s=5,
    )


@pytest.fixture
def mock_audit() -> SiteAudit:
    from datetime import datetime, timezone
    return SiteAudit(
        url="https://example.com", crawl_status="success",
        crawled_at=datetime.now(timezone.utc),
        schema=SchemaCoverage(has_organization=True, detected_schemas=["Organization"]),
        eeat=EeatSignals(has_about_page=True),
        structure=StructureScore(h1_count_ok=True, bluf_score=0.8),
        freshness=FreshnessScore(days_since_update=10, has_publish_date=True),
        robots_txt_allows_ai_bots={"GPTBot": True},
    )


@pytest.fixture
def mock_mentions() -> list[MentionResult]:
    return [
        MentionResult(question="q1", llm_provider="deepseek", llm_answer="ok",
                      brand_mentioned=True, mention_position=1),
    ]


@pytest.mark.asyncio
async def test_run_completes_through_all_stages(
    db_session, settings, mock_audit, mock_mentions
) -> None:
    from app.repositories.report_repo import ReportRepository

    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://example.com",
        target_questions=["q1", "q2", "q3"],
    )
    row = await repo.create(req)

    # Mock collaborators
    crawler = AsyncMock(spec=Crawler)
    crawler.audit = AsyncMock(return_value=mock_audit)

    llm = AsyncMock(spec=LLMClient)
    llm.query_mentions = AsyncMock(return_value=mock_mentions)

    svc = DiagnosisService(repo=repo, crawler=crawler, llm=llm, settings=settings)

    await svc.run(row.task_id, req)

    final = await repo.get_by_task_id(row.task_id)
    assert final.status == "completed"
    assert final.progress == 100
    assert final.report_json is not None
    assert final.pdf_path is None  # PDF rendering is opt-in (separate path)


@pytest.mark.asyncio
async def test_run_marks_failed_on_crawl_error(
    db_session, settings, mock_audit
) -> None:
    from app.domain.exceptions import CrawlError
    from app.repositories.report_repo import ReportRepository

    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://dead.example.com",
        target_questions=["q1", "q2", "q3"],
    )
    row = await repo.create(req)

    crawler = AsyncMock(spec=Crawler)
    crawler.audit = AsyncMock(side_effect=CrawlError(reason="DNS", url="https://dead.example.com"))
    llm = AsyncMock(spec=LLMClient)

    svc = DiagnosisService(repo=repo, crawler=crawler, llm=llm, settings=settings)
    await svc.run(row.task_id, req)

    final = await repo.get_by_task_id(row.task_id)
    assert final.status == "failed"
    assert final.error_message is not None
    assert "DNS" in final.error_message
