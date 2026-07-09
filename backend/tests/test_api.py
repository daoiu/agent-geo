"""Integration tests for the FastAPI app."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    """Health check still works."""
    resp = client.get("/health")
    assert resp.status_code == 200


def test_post_diagnosis_returns_202_and_task_id(client: TestClient) -> None:
    resp = client.post(
        "/api/diagnosis",
        json={
            "brand_name": "测试",
            "industry": "电商",
            "official_url": "https://example.com",
            "target_questions": ["q1", "q2", "q3"],
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "task_id" in body
    assert body["status"] == "pending"


def test_post_diagnosis_validates_url(client: TestClient) -> None:
    resp = client.post(
        "/api/diagnosis",
        json={
            "brand_name": "x",
            "industry": "y",
            "official_url": "not-a-url",
            "target_questions": ["q1", "q2", "q3"],
        },
    )
    assert resp.status_code == 422


def test_get_status_returns_task(client: TestClient) -> None:
    create = client.post(
        "/api/diagnosis",
        json={
            "brand_name": "X", "industry": "Y",
            "official_url": "https://example.com",
            "target_questions": ["a", "b", "c"],
        },
    )
    task_id = create.json()["task_id"]

    resp = client.get(f"/api/diagnosis/{task_id}/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == task_id
    assert body["status"] in ("pending", "crawling", "querying_llm", "completed", "failed")


def test_get_status_404_for_missing(client: TestClient) -> None:
    resp = client.get("/api/diagnosis/00000000-0000-0000-0000-000000000000/status")
    assert resp.status_code == 404


def test_list_reports_returns_array(client: TestClient) -> None:
    resp = client.get("/api/reports")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_submit_starts_background_task(client: TestClient) -> None:
    """Submitting kicks off async work; status changes over time."""
    import time
    from unittest.mock import patch, AsyncMock

    # Patch the worker to avoid real network calls
    with patch("app.tasks.worker.schedule_diagnosis") as mock_schedule:
        resp = client.post(
            "/api/diagnosis",
            json={
                "brand_name": "Async", "industry": "X",
                "official_url": "https://example.com",
                "target_questions": ["a", "b", "c"],
            },
        )
        assert resp.status_code == 202
        assert mock_schedule.called


def test_full_diagnosis_flow_with_mocked_workers(client: TestClient) -> None:
    """Submit → poll → complete → fetch report → download PDF (mocked)."""
    from unittest.mock import patch
    from datetime import datetime, timezone

    # Mock schedule_diagnosis to run inline
    async def inline_run(task_id, request):
        from app.core.db import get_session_factory
        from app.repositories.report_repo import ReportRepository
        from app.models.schemas import SiteAudit, SchemaCoverage, ScoreCard, DimensionScore
        from app.domain.scorer import compute_score_card, generate_suggestions

        factory = get_session_factory()
        async with factory() as session:
            repo = ReportRepository(session)
            audit = SiteAudit(
                url=str(request.official_url), crawl_status="success",
                crawled_at=datetime.now(timezone.utc),
                schema=SchemaCoverage(has_organization=True, detected_schemas=["Organization"]),
            )
            mentions = []
            card = compute_score_card(audit, mentions)
            suggestions = generate_suggestions(card, audit, mentions)
            report = {
                "id": task_id, "task_id": task_id,
                "brand": {"name": request.brand_name, "industry": request.industry,
                          "official_url": str(request.official_url)},
                "site_audit": audit.model_dump(mode="json"),
                "mentions": [], "score_card": card.model_dump(),
                "suggestions": [s.model_dump() for s in suggestions],
                "summary": "测试摘要",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "pdf_available": False,
            }
            import json
            await repo.update_report(task_id, json.dumps(report, default=str))
            await repo.update_status(task_id, status="completed", progress=100)

    def run_inline(tid, req):
        """Synchronous wrapper: run inline_run in a dedicated thread."""
        import asyncio, threading
        def _thread_target():
            asyncio.run(inline_run(tid, req))
        t = threading.Thread(target=_thread_target)
        t.start()
        t.join()

    with patch("app.tasks.worker.schedule_diagnosis") as mock:
        mock.side_effect = run_inline

        # 1. Submit
        resp = client.post("/api/diagnosis", json={
            "brand_name": "E2E测试", "industry": "测试",
            "official_url": "https://example.com",
            "target_questions": ["q1", "q2", "q3"],
        })
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]

        # 2. Poll status until completed (or timeout)
        import time
        for _ in range(20):
            status_resp = client.get(f"/api/diagnosis/{task_id}/status")
            assert status_resp.status_code == 200
            if status_resp.json()["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)

        assert status_resp.json()["status"] == "completed"

        # 3. Get full report
        report_resp = client.get(f"/api/reports/{task_id}")
        assert report_resp.status_code == 200
        report = report_resp.json()
        assert report["brand"]["name"] == "E2E测试"
        assert "score_card" in report

        # 4. List reports
        list_resp = client.get("/api/reports")
        assert list_resp.status_code == 200
        assert any(r["id"] == task_id for r in list_resp.json())

        # 5. PDF download
        with patch("app.api.reports.ReportService.get_or_render_pdf") as mock_get_pdf:
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(b"%PDF-1.4\n%fake pdf content")
                pdf_path = f.name
            mock_get_pdf.return_value = pdf_path

            pdf_resp = client.get(f"/api/reports/{task_id}/pdf")
            assert pdf_resp.status_code == 200
            assert pdf_resp.headers["content-type"] == "application/pdf"
            os.unlink(pdf_path)
