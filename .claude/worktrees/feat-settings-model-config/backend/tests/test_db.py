"""Tests for database setup and ORM model."""
import pytest
from sqlalchemy import select

from app.models.orm import ReportORM


@pytest.mark.asyncio
async def test_create_and_read_report(db_session) -> None:
    """A row inserted via ORM can be read back."""
    report = ReportORM(
        id="test-id-1",
        task_id="task-id-1",
        brand_name="测试品牌",
        industry="电商",
        official_url="https://example.com",
        status="pending",
        request_json='{"brand_name":"测试品牌"}',
    )
    db_session.add(report)
    await db_session.commit()

    result = await db_session.execute(
        select(ReportORM).where(ReportORM.id == "test-id-1")
    )
    fetched = result.scalar_one()

    assert fetched.brand_name == "测试品牌"
    assert fetched.status == "pending"
    assert fetched.progress == 0  # default
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_default_progress_is_zero(db_session) -> None:
    """Newly inserted rows default progress to 0."""
    report = ReportORM(
        id="x",
        task_id="y",
        brand_name="b",
        industry="i",
        official_url="https://example.com",
        status="pending",
        request_json="{}",
    )
    db_session.add(report)
    await db_session.commit()
    assert report.progress == 0
