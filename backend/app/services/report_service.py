"""Report retrieval + on-demand PDF rendering."""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.domain.renderer import render_pdf
from app.models.schemas import Report
from app.repositories.report_repo import ReportRepository

PDF_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "reports"


class ReportService:
    """Provides access to stored reports + PDF rendering."""

    def __init__(self, repo: ReportRepository) -> None:
        self.repo = repo

    async def get_report(self, task_id: str) -> Report | None:
        """Load completed report by task_id. Returns None if not found or not done."""
        row = await self.repo.get_by_task_id(task_id)
        if row is None or row.report_json is None:
            return None
        data = json.loads(row.report_json)
        return Report(**data)

    async def list_summaries(self, limit: int = 50) -> list[dict]:
        """Return lightweight summaries for the report list page."""
        rows = await self.repo.list_recent(limit=limit)
        return [
            {
                "id": r.id,
                "brand_name": r.brand_name,
                "industry": r.industry,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "overall_score": _extract_overall(r.report_json),
            }
            for r in rows
        ]

    async def get_or_render_pdf(self, task_id: str) -> str:
        """Return PDF path; render if not yet on disk."""
        row = await self.repo.get_by_task_id(task_id)
        if row is None or row.report_json is None:
            raise FileNotFoundError(f"Report {task_id} not found or not completed")

        pdf_dir = Path(PDF_DIR)
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = pdf_dir / f"{task_id}.pdf"

        if pdf_path.exists():
            return str(pdf_path)

        report = Report(**json.loads(row.report_json))
        render_pdf(report, str(pdf_path))

        # Update DB with path
        await self.repo.update_report(task_id, row.report_json, pdf_path=str(pdf_path))
        return str(pdf_path)


def _extract_overall(report_json: str | None) -> float | None:
    if not report_json:
        return None
    try:
        data = json.loads(report_json)
        return data.get("score_card", {}).get("overall")
    except (json.JSONDecodeError, KeyError):
        return None
