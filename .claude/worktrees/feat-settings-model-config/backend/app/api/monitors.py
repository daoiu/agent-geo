"""Monitor task API: CRUD + run-now + snapshots/trends."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.models.monitor import (
    MentionSnapshot,
    MonitorTask,
    MonitorTaskCreate,
    TrendData,
    TrendPoint,
)
from app.repositories.monitor_repo import MonitorRepository

router = APIRouter(prefix="/monitors", tags=["monitors"])


def _task_to_pydantic(task) -> MonitorTask:
    return MonitorTask(
        id=task.id,
        name=task.name,
        brand=task.brand,
        industry=task.industry,
        target_questions=json.loads(task.target_questions),
        frequency=task.frequency,  # type: ignore[arg-type]
        providers=json.loads(task.providers),
        notify_email=task.notify_email,
        change_threshold=task.change_threshold,
        is_active=bool(task.is_active),
        next_run_at=task.next_run_at,
        last_run_at=task.last_run_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("", status_code=201, response_model=MonitorTask)
async def create_monitor_task(
    body: MonitorTaskCreate,
    session: AsyncSession = Depends(get_session),
) -> MonitorTask:
    repo = MonitorRepository(session)
    task = await repo.create_monitor_task(
        name=body.name,
        brand=body.brand,
        industry=body.industry,
        target_questions=body.target_questions,
        frequency=body.frequency.value,
        providers=body.providers,
        notify_email=body.notify_email,
        change_threshold=body.change_threshold,
    )
    # Schedule (use module attribute for test mocking)
    from app.domain.monitor import scheduler as _scheduler
    _scheduler.schedule_monitor_task(task)
    return _task_to_pydantic(task)


@router.get("", response_model=list[MonitorTask])
async def list_monitor_tasks(
    session: AsyncSession = Depends(get_session),
) -> list[MonitorTask]:
    repo = MonitorRepository(session)
    tasks = await repo.list_monitor_tasks()
    return [_task_to_pydantic(t) for t in tasks]


@router.get("/{task_id}", response_model=MonitorTask)
async def get_monitor_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> MonitorTask:
    repo = MonitorRepository(session)
    task = await repo.get_monitor_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="monitor task not found")
    return _task_to_pydantic(task)


@router.put("/{task_id}", response_model=MonitorTask)
async def update_monitor_task(
    task_id: str,
    body: MonitorTaskCreate,
    session: AsyncSession = Depends(get_session),
) -> MonitorTask:
    repo = MonitorRepository(session)
    await repo.update_monitor_task(
        id=task_id,
        name=body.name,
        brand=body.brand,
        industry=body.industry,
        target_questions=body.target_questions,
        frequency=body.frequency.value,
        providers=body.providers,
        notify_email=body.notify_email,
        change_threshold=body.change_threshold,
    )
    task = await repo.get_monitor_task(task_id)
    # Re-schedule
    from app.domain.monitor import scheduler as _scheduler
    _scheduler.schedule_monitor_task(task)
    return _task_to_pydantic(task)


@router.delete("/{task_id}", status_code=204)
async def delete_monitor_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    from app.domain.monitor import scheduler as _scheduler
    repo = MonitorRepository(session)
    task = await repo.get_monitor_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="monitor task not found")
    _scheduler.unschedule_monitor_task(task_id)
    await repo.delete_monitor_task(task_id)
    return Response(status_code=204)


@router.post("/{task_id}/run", status_code=202)
async def run_monitor_now(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger immediate execution (does NOT change next_run_at)."""
    repo = MonitorRepository(session)
    task = await repo.get_monitor_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="monitor task not found")
    from app.domain.monitor import monitor_service as _service
    # Run in background, don't block API
    asyncio.create_task(_service.execute_monitor_run(task_id))
    return {"status": "triggered"}


@router.get("/{task_id}/snapshots", response_model=list[MentionSnapshot])
async def list_snapshots(
    task_id: str,
    days: int = 30,
    session: AsyncSession = Depends(get_session),
) -> list[MentionSnapshot]:
    repo = MonitorRepository(session)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    snaps = await repo.list_snapshots_since(task_id, cutoff=cutoff)
    result = []
    for s in snaps:
        result.append(MentionSnapshot(
            id=s.id,
            monitor_task_id=s.monitor_task_id,
            run_at=s.run_at,
            mention_rate=s.mention_rate,
            mention_count=s.mention_count,
            total_samples=s.total_samples,
            avg_position=s.avg_position,
            details=json.loads(s.details or "[]"),
            error_message=s.error_message,
            created_at=s.created_at,
        ))
    return result


@router.get("/{task_id}/trends", response_model=TrendData)
async def get_trends(
    task_id: str,
    days: int = 30,
    session: AsyncSession = Depends(get_session),
) -> TrendData:
    repo = MonitorRepository(session)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    snaps = await repo.list_snapshots_since(task_id, cutoff=cutoff)
    return TrendData(
        monitor_id=task_id,
        days=days,
        points=[
            TrendPoint(
                run_at=s.run_at,
                mention_rate=s.mention_rate,
                mention_count=s.mention_count,
                total_samples=s.total_samples,
                avg_position=s.avg_position,
            )
            for s in snaps
        ],
    )
