"""APScheduler wrapper for monitor task scheduling."""
from __future__ import annotations

from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.models.monitor import MonitorFrequency

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
        _execute_monitor_run_scheduled,
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


async def _execute_monitor_run_scheduled(monitor_task_id: str) -> None:
    """Proxy function called by APScheduler."""
    from app.domain.monitor.monitor_service import execute_monitor_run
    await execute_monitor_run(monitor_task_id)
