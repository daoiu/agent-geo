"""Integration tests for publisher API."""
from unittest.mock import patch

from fastapi.testclient import TestClient


def _create_approved_article(client: TestClient) -> str:
    """Helper: create KB + task + approved article. Returns article_id."""
    from app.core.db import get_session_factory
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    import asyncio
    async def _setup():
        async with get_session_factory()() as s:
            kb = KnowledgeBaseORM(id="kb1", name="KB")
            task = TaskORM(
                id="t1", name="T", kb_id="kb1", topic="X",
                article_count=1, style="neutral", target_length=1000,
            )
            article = ArticleORM(
                id="a1", task_id="t1", title="测试",
                content="# 测试\n\n内容", review_status="approved",
            )
            s.add_all([kb, task])
            await s.commit()
            s.add(article)
            await s.commit()
    asyncio.run(_setup())
    return "a1"


def test_create_publisher_config(client: TestClient) -> None:
    resp = client.post(
        "/api/publishers",
        json={
            "name": "主站",
            "site_url": "https://example.com",
            "username": "admin",
            "app_password": "abcdefghijklmnop",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "主站"
    assert body["username"] == "admin"
    assert "app_password" not in body  # CRITICAL: never exposed


def test_list_publisher_configs(client: TestClient) -> None:
    client.post("/api/publishers", json={
        "name": "A", "site_url": "https://a.com", "username": "u",
        "app_password": "abcdefghijklmnop",
    })
    resp = client.get("/api/publishers")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_publisher_config(client: TestClient) -> None:
    create = client.post("/api/publishers", json={
        "name": "X", "site_url": "https://x.com", "username": "u",
        "app_password": "abcdefghijklmnop",
    })
    pc_id = create.json()["id"]
    resp = client.get(f"/api/publishers/{pc_id}")
    assert resp.status_code == 200
    assert "app_password" not in resp.json()


def test_create_publisher_validates_password_length(client: TestClient) -> None:
    resp = client.post("/api/publishers", json={
        "name": "X", "site_url": "https://x.com", "username": "u",
        "app_password": "short",
    })
    assert resp.status_code == 422


def test_create_publish_job(client: TestClient) -> None:
    _create_approved_article(client)
    pc = client.post("/api/publishers", json={
        "name": "P", "site_url": "https://p.com", "username": "u",
        "app_password": "abcdefghijklmnop",
    }).json()

    with patch("app.tasks.publish_worker.schedule_publish") as mock:
        resp = client.post("/api/publishes", json={
            "article_id": "a1", "config_id": pc["id"],
        })
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"
    assert mock.called


def test_create_publish_job_rejects_non_approved_article(client: TestClient) -> None:
    from app.core.db import get_session_factory
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    import asyncio
    async def _setup():
        async with get_session_factory()() as s:
            kb = KnowledgeBaseORM(id="kb1", name="KB")
            task = TaskORM(
                id="t1", name="T", kb_id="kb1", topic="X",
                article_count=1, style="neutral", target_length=1000,
            )
            article = ArticleORM(
                id="a2", task_id="t1", title="Pending", review_status="pending",
            )
            s.add_all([kb, task])
            await s.commit()
            s.add(article)
            await s.commit()
    asyncio.run(_setup())

    pc = client.post("/api/publishers", json={
        "name": "P", "site_url": "https://p.com", "username": "u",
        "app_password": "abcdefghijklmnop",
    }).json()

    resp = client.post("/api/publishes", json={"article_id": "a2", "config_id": pc["id"]})
    assert resp.status_code == 422


def test_delete_publisher_with_jobs_returns_409(client: TestClient) -> None:
    _create_approved_article(client)
    pc = client.post("/api/publishers", json={
        "name": "P", "site_url": "https://p.com", "username": "u",
        "app_password": "abcdefghijklmnop",
    }).json()

    with patch("app.tasks.publish_worker.schedule_publish"):
        client.post("/api/publishes", json={"article_id": "a1", "config_id": pc["id"]})

    resp = client.delete(f"/api/publishers/{pc['id']}")
    assert resp.status_code == 409
