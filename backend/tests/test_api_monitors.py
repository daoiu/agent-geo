"""Integration tests for monitor API."""
import json
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_create_monitor_task(client: TestClient) -> None:
    with patch("app.domain.monitor.scheduler.schedule_monitor_task") as mock:
        resp = client.post(
            "/api/monitors",
            json={
                "name": "监测小米",
                "brand": "小米",
                "industry": "手机",
                "target_questions": ["q1", "q2"],
                "frequency": "daily",
                "providers": ["deepseek"],
                "notify_email": "test@example.com",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "监测小米"
    assert mock.called


def test_list_monitors(client: TestClient) -> None:
    with patch("app.domain.monitor.scheduler.schedule_monitor_task"):
        client.post("/api/monitors", json={
            "name": "M1", "brand": "X", "industry": "Y",
            "target_questions": ["q1"], "frequency": "daily",
        })
    resp = client.get("/api/monitors")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_create_monitor_validates_brand(client: TestClient) -> None:
    resp = client.post("/api/monitors", json={
        "name": "M", "brand": "", "industry": "Y",
        "target_questions": ["q1"], "frequency": "daily",
    })
    assert resp.status_code == 422


def test_get_monitor(client: TestClient) -> None:
    with patch("app.domain.monitor.scheduler.schedule_monitor_task"):
        create = client.post("/api/monitors", json={
            "name": "M", "brand": "X", "industry": "Y",
            "target_questions": ["q1"], "frequency": "daily",
        })
    mid = create.json()["id"]
    resp = client.get(f"/api/monitors/{mid}")
    assert resp.status_code == 200


def test_delete_monitor_unschedules(client: TestClient) -> None:
    with patch("app.domain.monitor.scheduler.schedule_monitor_task"):
        create = client.post("/api/monitors", json={
            "name": "M", "brand": "X", "industry": "Y",
            "target_questions": ["q1"], "frequency": "daily",
        })
    mid = create.json()["id"]
    with patch("app.domain.monitor.scheduler.unschedule_monitor_task") as mock_un:
        resp = client.delete(f"/api/monitors/{mid}")
    assert resp.status_code == 204
    mock_un.assert_called_once_with(mid)


def test_run_monitor_now(client: TestClient) -> None:
    with patch("app.domain.monitor.scheduler.schedule_monitor_task"):
        create = client.post("/api/monitors", json={
            "name": "M", "brand": "X", "industry": "Y",
            "target_questions": ["q1"], "frequency": "daily",
        })
    mid = create.json()["id"]

    with patch("app.domain.monitor.monitor_service.execute_monitor_run") as mock_run:
        mock_run.return_value = None
        resp = client.post(f"/api/monitors/{mid}/run")
    assert resp.status_code == 202
