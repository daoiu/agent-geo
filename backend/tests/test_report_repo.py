"""Tests for the ReportRepository."""
import pytest

from app.models.orm import ReportORM
from app.models.schemas import DiagnosisRequest
from app.repositories.report_repo import ReportRepository


@pytest.mark.asyncio
async def test_create_returns_orm_with_id(db_session) -> None:
    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="测试",
        industry="电商",
        official_url="https://example.com",
        target_questions=["q1", "q2", "q3"],
    )
    row = await repo.create(req)

    assert row.id != ""
    assert row.task_id == row.id
    assert row.status == "pending"
    assert row.progress == 0
    assert "brand_name" in row.request_json
    assert "测试" in row.request_json  # "测试"


@pytest.mark.asyncio
async def test_get_by_id_returns_created(db_session) -> None:
    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://example.com",
        target_questions=["a", "b", "c"],
    )
    created = await repo.create(req)
    fetched = await repo.get_by_id(created.id)

    assert fetched is not None
    assert fetched.brand_name == "X"


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_missing(db_session) -> None:
    repo = ReportRepository(db_session)
    fetched = await repo.get_by_id("nonexistent")
    assert fetched is None


@pytest.mark.asyncio
async def test_update_status_changes_fields(db_session) -> None:
    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://example.com",
        target_questions=["a", "b", "c"],
    )
    row = await repo.create(req)

    await repo.update_status(row.task_id, status="crawling", progress=20)
    refreshed = await repo.get_by_task_id(row.task_id)
    assert refreshed.status == "crawling"
    assert refreshed.progress == 20


@pytest.mark.asyncio
async def test_update_report_writes_json_and_pdf(db_session) -> None:
    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://example.com",
        target_questions=["a", "b", "c"],
    )
    row = await repo.create(req)

    await repo.update_report(
        row.task_id,
        report_json='{"score_card":{"overall":80}}',
        pdf_path="/tmp/report.pdf",
    )
    refreshed = await repo.get_by_task_id(row.task_id)
    assert refreshed.report_json is not None
    assert refreshed.pdf_path == "/tmp/report.pdf"


@pytest.mark.asyncio
async def test_list_recent_orders_by_created_desc(db_session) -> None:
    repo = ReportRepository(db_session)
    ids = []
    for i in range(3):
        req = DiagnosisRequest(
            brand_name=f"B{i}", industry="X", official_url="https://example.com",
            target_questions=["a", "b", "c"],
        )
        row = await repo.create(req)
        ids.append(row.id)

    recent = await repo.list_recent(limit=10)
    assert len(recent) == 3
    # most recently created should be first
    assert recent[0].id == ids[-1]
