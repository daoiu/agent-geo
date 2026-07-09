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
