"""Report retrieval API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.repositories.report_repo import ReportRepository
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])


@router.get("/reports", response_model=list[dict[str, Any]])
async def list_reports(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List recent reports (summaries)."""
    repo = ReportRepository(session)
    svc = ReportService(repo)
    return await svc.list_summaries(limit=50)


@router.get("/reports/{task_id}", response_model=dict)
async def get_report(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get full report JSON by task_id."""
    repo = ReportRepository(session)
    svc = ReportService(repo)
    report = await svc.get_report(task_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found or not completed")
    return report.model_dump()


@router.get("/reports/{task_id}/pdf")
async def get_report_pdf(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Download report as PDF. Renders on first request."""
    repo = ReportRepository(session)
    svc = ReportService(repo)
    try:
        pdf_path = await svc.get_or_render_pdf(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="report not found or not completed")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"geo-report-{task_id[:8]}.pdf",
    )
