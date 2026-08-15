"""APScheduler wrapper for monitor task scheduling.

v0.6+ Multi-Agent: 提供 _build_monitor_callback 工厂函数,
构造走 MonitorSpecialist 的 callback。schedule_monitor_task 使用此 callback。
"""
from __future__ import annotations

from datetime import timedelta

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.models.monitor import MonitorFrequency

logger = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global AsyncIOScheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler() -> None:
    """Start the global scheduler (idempotent)."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()


def shutdown_scheduler(wait: bool = False) -> None:
    """Shutdown the global scheduler (idempotent)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=wait)
    _scheduler = None


def frequency_to_interval(freq: MonitorFrequency | str) -> timedelta:
    """Map a frequency enum/string to a timedelta interval."""
    if isinstance(freq, str):
        freq = MonitorFrequency(freq)
    return {
        MonitorFrequency.HOURLY: timedelta(hours=1),
        MonitorFrequency.DAILY: timedelta(days=1),
        MonitorFrequency.WEEKLY: timedelta(weeks=1),
    }[freq]


def _job_id(task_id: str) -> str:
    return f"monitor_{task_id}"


def _build_monitor_callback():
    """构造一个走 MonitorSpecialist 的回调,供 APScheduler 注册。

    v0.6+ Multi-Agent 改造: callback 改走 specialist,不再直接调 execute_monitor_run。
    """
    from app.core.config import get_settings
    from app.core.db import get_session_factory
    from app.domain.monitor.monitor_specialist import MonitorSpecialist

    settings = get_settings()
    factory = get_session_factory()
    specialist = MonitorSpecialist(settings, factory)

    async def callback(monitor_task_id: str) -> None:
        """APScheduler 触发入口,委派给 specialist(spec §5.1)。"""
        result = await specialist.run(monitor_task_id)
        if result.status == "failed":
            logger.warning(
                "monitor_specialist_failed",
                monitor_task_id=monitor_task_id,
                error=result.error,
            )

    return callback


def schedule_monitor_task(task) -> None:
    """Add or replace a scheduled job for a monitor task.

    `task` is expected to have attributes: id, frequency, is_active, name, next_run_at.
    """
    scheduler = get_scheduler()
    job_id = _job_id(task.id)

    # Remove existing job if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if not task.is_active:
        return

    interval = frequency_to_interval(task.frequency)
    scheduler.add_job(
        _build_monitor_callback(),
        trigger=IntervalTrigger(seconds=interval.total_seconds()),
        args=[task.id],
        id=job_id,
        name=f"Monitor: {task.name}",
        replace_existing=True,
        next_run_time=getattr(task, "next_run_at", None),
    )


def unschedule_monitor_task(task_id: str) -> None:
    scheduler = get_scheduler()
    job_id = _job_id(task_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


async def load_all_monitor_tasks() -> None:
    """On startup, reload all active monitor tasks from DB into the scheduler."""
    from app.core.db import get_session_factory
    from app.repositories.monitor_repo import MonitorRepository

    factory = get_session_factory()
    async with factory() as session:
        repo = MonitorRepository(session)
        tasks = await repo.list_active_monitor_tasks()
        for task in tasks:
            schedule_monitor_task(task)

