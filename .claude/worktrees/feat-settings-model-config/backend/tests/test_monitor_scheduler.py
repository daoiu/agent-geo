"""Tests for monitor scheduler wrapper."""
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from app.domain.monitor.scheduler import (
    frequency_to_interval,
    get_scheduler,
    schedule_monitor_task,
    unschedule_monitor_task,
)
from app.models.monitor import MonitorFrequency


class TestFrequencyInterval:
    def test_hourly(self) -> None:
        assert frequency_to_interval(MonitorFrequency.HOURLY) == timedelta(hours=1)

    def test_daily(self) -> None:
        assert frequency_to_interval(MonitorFrequency.DAILY) == timedelta(days=1)

    def test_weekly(self) -> None:
        assert frequency_to_interval(MonitorFrequency.WEEKLY) == timedelta(weeks=1)


class TestSchedulerSingleton:
    def test_returns_same_instance(self) -> None:
        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2


def test_schedule_and_unschedule() -> None:
    """Adding and removing a monitor task works."""
    scheduler = get_scheduler()
    # Clear any prior state
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)

    # Mock task with id and frequency
    task = MagicMock()
    task.id = "test-monitor-1"
    task.frequency = "daily"
    task.is_active = True
    task.name = "Test"
    task.next_run_at = None

    schedule_monitor_task(task)
    assert scheduler.get_job("monitor_test-monitor-1") is not None

    unschedule_monitor_task("test-monitor-1")
    assert scheduler.get_job("monitor_test-monitor-1") is None
