"""Integration tests for reviews API."""
import asyncio
from unittest.mock import patch

from fastapi.testclient import TestClient


def _create_task_with_article(client: TestClient):
    """Helper: create KB + task with 1 article."""
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    with patch("app.api.tasks.schedule_task"):
        create = client.post("/api/tasks", json={
            "name": "T", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 1, "style": "neutral",
        })
    task_id = create.json()["id"]
    # Manually create an article via repo
    from app.core.db import get_session_factory
    from app.repositories.task_repo import TaskRepository

    async def _setup():
        async with get_session_factory()() as s:
            repo = TaskRepository(s)
            article = await repo.create_article(task_id)
            await repo.update_article(
                article.id, title="测试文章", content="# 测试\n\n内容",
                content_length=10, cited_chunks=[],
            )
            return article.id

    article_id = asyncio.run(_setup())
    return article_id


def test_list_reviews_by_status(client: TestClient) -> None:
    article_id = _create_task_with_article(client)
    resp = client.get("/api/reviews?status=pending")
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert article_id in ids


def test_approve_article(client: TestClient) -> None:
    article_id = _create_task_with_article(client)
    resp = client.post(f"/api/reviews/{article_id}/approve", json={})
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "approved"


def test_reject_requires_note(client: TestClient) -> None:
    article_id = _create_task_with_article(client)
    resp = client.post(f"/api/reviews/{article_id}/reject", json={"note": ""})
    assert resp.status_code == 422  # missing note

    resp = client.post(f"/api/reviews/{article_id}/reject", json={"note": "内容不准确"})
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "rejected"


def test_get_article_with_chunks(client: TestClient) -> None:
    article_id = _create_task_with_article(client)
    resp = client.get(f"/api/reviews/{article_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == article_id
    assert body["content"] == "# 测试\n\n内容"
