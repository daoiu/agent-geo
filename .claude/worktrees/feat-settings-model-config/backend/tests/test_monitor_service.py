"""Tests for MonitorService."""
import json
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest

from app.models.orm_v03 import MonitorTaskORM
from app.repositories.monitor_repo import MonitorRepository


def _make_mention(*, question: str, mentioned: bool, position: int | None = None, error: str | None = None):
    """Build a MentionResult-like object for LLMClient.query_mentions mocking."""
    return SimpleNamespace(
        question=question, llm_provider="deepseek",
        llm_answer="<answer>", brand_mentioned=mentioned, mention_position=position,
        error=error,
    )


@pytest.mark.asyncio
async def test_execute_monitor_run_creates_snapshot(db_session) -> None:
    from app.domain.monitor.monitor_service import execute_monitor_run

    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="小米", industry="手机",
        target_questions=["小米14怎么样", "小米vs华为"],
        frequency="daily", providers=["deepseek"],
    )

    mentions = [
        _make_mention(question="小米14怎么样", mentioned=True, position=1),
        _make_mention(question="小米vs华为", mentioned=False),
    ]

    with patch("app.domain.monitor.monitor_service.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.query_mentions = AsyncMock(return_value=mentions)
        with patch("app.domain.monitor.monitor_service.check_and_notify_change", new=AsyncMock()):
            await execute_monitor_run(m.id)

    snaps = await repo.list_snapshots_since(m.id, datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert len(snaps) == 1
    assert snaps[0].mention_rate == 0.5  # 1/2
    assert snaps[0].mention_count == 1
    assert snaps[0].total_samples == 2


@pytest.mark.asyncio
async def test_execute_monitor_run_inactive_skips(db_session) -> None:
    from app.domain.monitor.monitor_service import execute_monitor_run

    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y",
        target_questions=["q"], frequency="daily", providers=["deepseek"],
    )
    await repo.update_monitor_task(m.id, is_active=False)

    with patch("app.domain.monitor.monitor_service.LLMClient") as MockLLM:
        await execute_monitor_run(m.id)
        MockLLM.assert_not_called()

    snaps = await repo.list_snapshots_since(m.id, datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert snaps == []


@pytest.mark.asyncio
async def test_execute_monitor_run_handles_llm_failure(db_session) -> None:
    from app.domain.monitor.monitor_service import execute_monitor_run

    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y",
        target_questions=["q"], frequency="daily", providers=["deepseek"],
    )

    with patch("app.domain.monitor.monitor_service.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.query_mentions = AsyncMock(side_effect=Exception("LLM down"))
        with patch("app.domain.monitor.monitor_service.check_and_notify_change", new=AsyncMock()):
            await execute_monitor_run(m.id)

    snaps = await repo.list_snapshots_since(m.id, datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert len(snaps) == 1
    assert snaps[0].error_message is not None
    assert "LLM down" in snaps[0].error_message


@pytest.mark.asyncio
async def test_check_and_notify_change_sends_email_on_significant_change(db_session) -> None:
    from app.domain.monitor.monitor_service import check_and_notify_change

    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="监测小米", brand="小米", industry="手机",
        target_questions=["q"], frequency="daily", providers=["deepseek"],
        notify_email="test@example.com", change_threshold=0.1,
    )

    s1_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc) - timedelta(days=1),
        mention_rate=0.3, mention_count=3, total_samples=10, avg_position=1.0,
        details=[], error_message=None,
    )
    s2_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc),
        mention_rate=0.6, mention_count=6, total_samples=10, avg_position=1.0,
        details=[], error_message=None,
    )

    task = await repo.get_monitor_task(m.id)

    with patch("app.domain.notification.notification_service.send_email", new=AsyncMock()) as mock_send:
        await check_and_notify_change(task, current_rate=0.6, snapshot_id=s2_id)
        mock_send.assert_called_once()
        # Check that the previous snapshot used was s1
        call_args = mock_send.call_args
        assert "上升" in call_args.kwargs.get("subject", "") or "上升" in call_args.args[1]


@pytest.mark.asyncio
async def test_check_and_notify_change_skips_email_on_small_change(db_session) -> None:
    from app.domain.monitor.monitor_service import check_and_notify_change

    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y",
        target_questions=["q"], frequency="daily", providers=["deepseek"],
        notify_email="test@example.com", change_threshold=0.5,  # 50% threshold
    )

    s1_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc) - timedelta(days=1),
        mention_rate=0.3, mention_count=3, total_samples=10, avg_position=1.0,
        details=[], error_message=None,
    )
    s2_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc),
        mention_rate=0.35, mention_count=3, total_samples=10, avg_position=1.0,
        details=[], error_message=None,
    )

    task = await repo.get_monitor_task(m.id)

    with patch("app.domain.notification.notification_service.send_email", new=AsyncMock()) as mock_send:
        await check_and_notify_change(task, current_rate=0.35, snapshot_id=s2_id)
        mock_send.assert_not_called()
