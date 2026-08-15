"""HandoffLogRepository 测试:纪律 1 幂等键 + 纪律 5 日志写入。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.agent.handoff import HandoffRequest, HandoffResult
from app.models.orm import Base
from app.repositories.handoff_log_repo import HandoffLogRepository


@pytest.fixture
async def session_factory():
    """用 in-memory sqlite 跑单测。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _make_request(handoff_id: str | None = None) -> HandoffRequest:
    return HandoffRequest(
        handoff_id=handoff_id or str(uuid.uuid4()),
        specialist="content_writer",
        task_id="task-1",
        session_id="session-1",
        started_at=datetime.now(timezone.utc),
        timeout_seconds=300,
        payload={"kb_id": "kb-1"},
    )


def _make_result(handoff_id: str, status: str = "success") -> HandoffResult:
    return HandoffResult(
        handoff_id=handoff_id,
        status=status,
        result={"article_id": "art-1"} if status == "success" else None,
        error=None if status == "success" else "测试失败",
        duration_ms=1500,
        token_usage={"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
    )


async def test_insert_writes_log(session_factory):
    """insert 后能从 DB 查到记录。"""
    async with session_factory() as session:
        repo = HandoffLogRepository(session)
        req = _make_request()
        result = _make_result(req.handoff_id)
        await repo.insert(req, result)
        await session.commit()

    async with session_factory() as session:
        repo = HandoffLogRepository(session)
        existing = await repo.check_idempotency(req.handoff_id, window_hours=24)
        assert existing is not None
        assert existing.handoff_id == req.handoff_id
        assert existing.status == "success"


async def test_check_idempotency_returns_none_for_unknown_id(session_factory):
    """不存在的 handoff_id 返回 None。"""
    async with session_factory() as session:
        repo = HandoffLogRepository(session)
        result = await repo.check_idempotency("nonexistent-id", window_hours=24)
        assert result is None


async def test_check_idempotency_excludes_failed_results(session_factory):
    """失败的 handoff 不应被幂等(允许主 Agent 重试)。"""
    async with session_factory() as session:
        repo = HandoffLogRepository(session)
        req = _make_request()
        failed_result = _make_result(req.handoff_id, status="failed")
        await repo.insert(req, failed_result)
        await session.commit()

    async with session_factory() as session:
        repo = HandoffLogRepository(session)
        # 失败的不应被幂等,check_idempotency 返回 None 表示"需要重试"
        existing = await repo.check_idempotency(req.handoff_id, window_hours=24)
        assert existing is None


async def test_aggregate_by_specialist_counts_per_specialist(session_factory):
    """aggregate_by_specialist 返回每个 specialist 的成功/失败/超时计数。"""
    async with session_factory() as session:
        repo = HandoffLogRepository(session)
        # 插入 3 条 content_writer 记录(2 成功 1 失败)
        for i, status in enumerate(["success", "success", "failed"]):
            req = _make_request(handoff_id=f"id-{i}")
            res = _make_result(req.handoff_id, status=status)
            await repo.insert(req, res)
        await session.commit()

    async with session_factory() as session:
        repo = HandoffLogRepository(session)
        agg = await repo.aggregate_by_specialist(days=7)
        cw = next((r for r in agg if r["specialist"] == "content_writer"), None)
        assert cw is not None
        assert cw["success_count"] == 2
        assert cw["failed_count"] == 1
