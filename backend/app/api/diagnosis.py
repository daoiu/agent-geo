"""Diagnosis task API: submit + status polling."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session_factory
from app.models.schemas import DiagnosisRequest, DiagnosisTask
from app.repositories.report_repo import ReportRepository

router = APIRouter(tags=["diagnosis"])


async def get_session() -> AsyncSession:
    """Yield a DB session per request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


@router.post("/diagnosis", status_code=202, response_model=dict)
async def submit_diagnosis(
    request: DiagnosisRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Create a new diagnosis task. Returns task_id (UUID)."""
    repo = ReportRepository(session)
    row = await repo.create(request)
    # Note: actual pipeline execution is wired up in Task 8.1 (async worker)
    return {"task_id": row.id, "status": row.status}


@router.get("/diagnosis/{task_id}/status", response_model=DiagnosisTask)
async def get_task_status(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> DiagnosisTask:
    """Poll task status. Returns 404 if task_id unknown."""
    repo = ReportRepository(session)
    row = await repo.get_by_task_id(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="task not found")

    # Reconstruct DiagnosisTask from DB row
    from app.models.schemas import DiagnosisRequest as Req

    return DiagnosisTask(
        id=row.id,
        request=Req.model_validate_json(row.request_json),
        status=row.status,  # type: ignore[arg-type]
        progress=row.progress,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
