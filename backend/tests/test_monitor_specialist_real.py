"""MonitorSpecialist 真实执行链路测试(Task 8 落地后)。

- _execute_with_timeout 复用 MonitorService 核心逻辑 → snapshot 落库
- 返回结果 dict 含 mention_rate / snapshot_id
- 无 LLM key / 无 active task 场景不炸
"""
from __future__ import annotations

import os

# 测试不调用真实 LLM,允许缺少 API key
os.environ.setdefault("GEO_ALLOW_MISSING_LLM_KEY", "1")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.domain.monitor.monitor_specialist import MonitorSpecialist


def _make_specialist(db_session) -> MonitorSpecialist:
    settings = Settings(_env_file=None)
    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    return MonitorSpecialist(settings, factory)


async def _make_monitor_task(db_session) -> str:
    """建一个 active monitor task,返回 id。"""
    from app.repositories.monitor_repo import MonitorRepository

    repo = MonitorRepository(db_session)
    task = await repo.create_monitor_task(
        name="测试监测",
        brand="Acme",
        industry="AI",
        target_questions=["Acme 怎么样"],
        frequency="daily",
        providers=["deepseek"],
        notify_email=None,
    )
    await db_session.commit()
    return task.id


def _mention(question: str, provider: str, mentioned: bool, error: str | None = None):
    from app.models.schemas import MentionResult

    return MentionResult(
        question=question,
        llm_provider=provider,
        llm_answer="答",
        brand_mentioned=mentioned,
        mention_position=1 if mentioned else None,
        error=error,
    )


@pytest.mark.asyncio
async def test_run_real_execution_creates_snapshot(db_session):
    """真实执行:LLM 查询 → snapshot 落库 → 结果含 mention_rate。"""
    from sqlalchemy import select

    from app.models.orm_v03 import MentionSnapshotORM

    task_id = await _make_monitor_task(db_session)
    specialist = _make_specialist(db_session)

    mentions = [
        _mention("Acme 怎么样", "deepseek", mentioned=True),
        _mention("Acme 怎么样", "deepseek", mentioned=False),
        _mention("Acme 怎么样", "deepseek", mentioned=True, error="timeout"),
    ]

    with patch(
        "app.domain.monitor.monitor_service.LLMClient"
    ) as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm.query_mentions = AsyncMock(return_value=mentions)
        mock_llm_cls.return_value = mock_llm

        result = await specialist.run(task_id)

    assert result.status == "success"
    assert result.result["monitor_task_id"] == task_id
    assert result.result["mention_rate"] == 0.5  # 2 个有效样本中 1 个提到
    assert result.result["mention_count"] == 1
    assert result.result["total_samples"] == 2  # error 样本被排除
    assert result.result["snapshot_id"]

    # snapshot 落库验证
    row = (
        await db_session.execute(
            select(MentionSnapshotORM).where(
                MentionSnapshotORM.id == result.result["snapshot_id"]
            )
        )
    ).scalar_one_or_none()
    assert row is not None
    assert row.mention_rate == 0.5
    assert row.monitor_task_id == task_id


@pytest.mark.asyncio
async def test_run_inactive_task_skips(db_session):
    """inactive task:跳过执行,不落 snapshot。"""
    from app.repositories.monitor_repo import MonitorRepository

    repo = MonitorRepository(db_session)
    task = await repo.create_monitor_task(
        name="停用监测", brand="Acme", industry="AI",
        target_questions=["q"], frequency="daily", providers=["deepseek"],
    )
    task.is_active = False
    await db_session.commit()

    specialist = _make_specialist(db_session)
    result = await specialist.run(task.id)

    assert result.status == "success"
    assert result.result.get("skipped") is True
    assert result.result.get("snapshot_id") is None
