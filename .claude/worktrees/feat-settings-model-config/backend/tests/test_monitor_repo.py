"""Tests for MonitorRepository."""
import json
from datetime import datetime, timezone, timedelta

import pytest

from app.models.orm_v03 import MonitorTaskORM
from app.repositories.monitor_repo import MonitorRepository


@pytest.mark.asyncio
async def test_create_monitor_task(db_session) -> None:
    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M1", brand="小米", industry="手机",
        target_questions=["q1", "q2"],
        frequency="daily", providers=["deepseek"],
        notify_email="test@example.com",
        change_threshold=0.15,
    )
    assert m.id != ""
    assert m.is_active == 1
    assert json.loads(m.target_questions) == ["q1", "q2"]
    assert json.loads(m.providers) == ["deepseek"]


@pytest.mark.asyncio
async def test_get_monitor_task(db_session) -> None:
    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y", target_questions=["q"],
        frequency="daily", providers=["deepseek"],
    )
    fetched = await repo.get_monitor_task(m.id)
    assert fetched.name == "M"


@pytest.mark.asyncio
async def test_list_active_monitor_tasks(db_session) -> None:
    repo = MonitorRepository(db_session)
    a = await repo.create_monitor_task(
        name="A", brand="X", industry="Y", target_questions=["q"],
        frequency="daily", providers=["deepseek"],
    )
    i = await repo.create_monitor_task(
        name="I", brand="X", industry="Y", target_questions=["q"],
        frequency="daily", providers=["deepseek"],
    )
    await repo.update_monitor_task(i.id, is_active=False)

    actives = await repo.list_active_monitor_tasks()
    assert {t.id for t in actives} == {a.id}


@pytest.mark.asyncio
async def test_create_snapshot_and_get_previous(db_session) -> None:
    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y", target_questions=["q"],
        frequency="daily", providers=["deepseek"],
    )

    s1_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc) - timedelta(days=1),
        mention_rate=0.3, mention_count=3, total_samples=10,
        avg_position=1.5, details=[], error_message=None,
    )
    s2_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc),
        mention_rate=0.6, mention_count=6, total_samples=10,
        avg_position=1.0, details=[], error_message=None,
    )

    # Get previous before s2 should return s1
    prev = await repo.get_previous_snapshot(m.id, before_id=s2_id)
    assert prev is not None
    assert prev.id == s1_id
    assert prev.mention_rate == 0.3


@pytest.mark.asyncio
async def test_list_snapshots_since(db_session) -> None:
    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y", target_questions=["q"],
        frequency="daily", providers=["deepseek"],
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=10)
    await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc) - timedelta(days=20),
        mention_rate=0.1, mention_count=1, total_samples=10, avg_position=None,
        details=[], error_message=None,
    )
    await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc) - timedelta(days=5),
        mention_rate=0.5, mention_count=5, total_samples=10, avg_position=1.0,
        details=[], error_message=None,
    )

    recent = await repo.list_snapshots_since(m.id, cutoff=cutoff)
    assert len(recent) == 1
    assert recent[0].mention_rate == 0.5
