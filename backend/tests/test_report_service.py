"""Tests for report retrieval + on-demand PDF rendering."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models.schemas import (
    BrandInfo, DimensionScore, MentionResult, Report, ScoreCard,
    SiteAudit, Suggestion,
)
from app.repositories.report_repo import ReportRepository
from app.services.report_service import ReportService


@pytest.fixture
def sample_report_dict() -> dict:
    return {
        "id": "test-id",
        "task_id": "test-id",
        "brand": {"name": "X", "industry": "Y", "official_url": "https://example.com"},
        "site_audit": {
            "url": "https://example.com", "crawl_status": "success",
            "crawled_at": "2026-01-01T00:00:00Z",
            "schema": {}, "eeat": {}, "structure": {}, "freshness": {},
            "page_load_ms": None, "robots_txt_allows_ai_bots": {},
        },
        "mentions": [],
        "score_card": {
            "authority": {"name": "a", "score": 5, "weight": 0.25, "evidence": []},
            "relevance": {"name": "r", "score": 5, "weight": 0.30, "evidence": []},
            "structure": {"name": "s", "score": 5, "weight": 0.20, "evidence": []},
            "freshness": {"name": "f", "score": 5, "weight": 0.15, "evidence": []},
            "verifiability": {"name": "v", "score": 5, "weight": 0.10, "evidence": []},
            "overall": 50.0, "mention_rate": 0.0, "avg_mention_position": None,
        },
        "suggestions": [],
        "summary": "s",
        "created_at": "2026-01-01T00:00:00Z",
        "pdf_available": False,
    }


@pytest.mark.asyncio
async def test_get_pdf_renders_if_missing(db_session, sample_report_dict) -> None:
    repo = ReportRepository(db_session)
    from app.models.schemas import DiagnosisRequest
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://example.com",
        target_questions=["a", "b", "c"],
    )
    row = await repo.create(req)
    import json
    await repo.update_report(row.task_id, json.dumps(sample_report_dict))

    with tempfile.TemporaryDirectory() as tmp:
        pdf_file = Path(tmp) / f"{row.task_id}.pdf"
        # Do NOT touch the file — we want get_or_render_pdf to trigger render_pdf

        with patch("app.services.report_service.PDF_DIR", tmp):
            with patch("app.services.report_service.render_pdf") as mock_render:
                def create_file(report, path):
                    Path(path).touch()
                    return path
                mock_render.side_effect = create_file

                svc = ReportService(repo=repo)
                pdf_path = await svc.get_or_render_pdf(row.task_id)

                assert pdf_file.exists()
                assert pdf_path.endswith(".pdf")
                mock_render.assert_called_once()
