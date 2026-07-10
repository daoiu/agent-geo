"""Integration tests for tasks API."""
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_create_task(client: TestClient) -> None:
    # Need a KB first
    kb = client.post("/api/knowledge", json={"name": "TaskKB"}).json()

    with patch("app.api.tasks.schedule_task") as mock:
        resp = client.post(
            "/api/tasks",
            json={
                "name": "测试任务",
                "kb_id": kb["id"],
                "brand": "测试品牌",
                "topic": "生成关于产品的文章",
                "keywords": ["k1", "k2"],
                "article_count": 3,
                "style": "professional",
                "target_length": 1500,
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "测试任务"
    assert body["article_count"] == 3
    assert body["status"] == "pending"
    assert mock.called


def test_create_task_validates_kb_exists(client: TestClient) -> None:
    resp = client.post(
        "/api/tasks",
        json={
            "name": "T", "kb_id": "nonexistent-kb",
            "topic": "足够长的主题", "article_count": 1, "style": "neutral",
        },
    )
    assert resp.status_code == 404


def test_create_task_validates_article_count(client: TestClient) -> None:
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    resp = client.post(
        "/api/tasks",
        json={
            "name": "T", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 100, "style": "neutral",
        },
    )
    assert resp.status_code == 422


def test_list_tasks(client: TestClient) -> None:
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    with patch("app.api.tasks.schedule_task"):
        client.post("/api/tasks", json={
            "name": "T1", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 1, "style": "neutral",
        })
        client.post("/api/tasks", json={
            "name": "T2", "kb_id": kb["id"],
            "topic": "另一个主题", "article_count": 1, "style": "neutral",
        })
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_task_with_articles(client: TestClient) -> None:
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    with patch("app.api.tasks.schedule_task"):
        create = client.post("/api/tasks", json={
            "name": "T", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 2, "style": "neutral",
        })
    task_id = create.json()["id"]
    resp = client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "articles" in body
    assert body["id"] == task_id


def test_delete_task(client: TestClient) -> None:
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    with patch("app.api.tasks.schedule_task"):
        create = client.post("/api/tasks", json={
            "name": "T", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 1, "style": "neutral",
        })
    task_id = create.json()["id"]
    resp = client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 204


def test_cancel_task(client: TestClient) -> None:
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    with patch("app.api.tasks.schedule_task"):
        create = client.post("/api/tasks", json={
            "name": "T", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 1, "style": "neutral",
        })
    task_id = create.json()["id"]
    resp = client.post(f"/api/tasks/{task_id}/cancel")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
