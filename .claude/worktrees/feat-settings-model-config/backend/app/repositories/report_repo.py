"""Repository for ReportORM — all DB access for the reports table."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ReportORM
from app.models.schemas import DiagnosisRequest


class ReportRepository:
    """Data access for the reports table.

    All methods are async and require a session bound to a transaction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, req: DiagnosisRequest) -> ReportORM:
        """Insert a new pending task. Returns the persisted row."""
        new_id = str(uuid.uuid4())
        row = ReportORM(
            id=new_id,
            task_id=new_id,
            brand_name=req.brand_name,
            industry=req.industry,
            official_url=str(req.official_url),
            status="pending",
            progress=0,
            request_json=req.model_dump_json(),
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_by_id(self, id: str) -> ReportORM | None:
        """Fetch by primary key."""
        result = await self.session.execute(
            select(ReportORM).where(ReportORM.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_task_id(self, task_id: str) -> ReportORM | None:
        """Fetch by task_id (== id in MVP)."""
        return await self.get_by_id(task_id)

    async def update_status(
        self,
        task_id: str,
        status: str,
        progress: int,
        error: str | None = None,
    ) -> None:
        """Update lifecycle status and progress."""
        row = await self.get_by_task_id(task_id)
        if row is None:
            return
        row.status = status
        row.progress = progress
        if error is not None:
            row.error_message = error
        row.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_report(
        self,
        task_id: str,
        report_json: str,
        pdf_path: str | None = None,
    ) -> None:
        """Write the final report JSON and optional PDF path."""
        row = await self.get_by_task_id(task_id)
        if row is None:
            return
        row.report_json = report_json
        if pdf_path is not None:
            row.pdf_path = pdf_path
        row.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def list_recent(self, limit: int = 50) -> list[ReportORM]:
        """List reports ordered by creation time descending."""
        result = await self.session.execute(
            select(ReportORM).order_by(ReportORM.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
