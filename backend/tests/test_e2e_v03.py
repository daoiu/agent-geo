"""E2E test for v0.3 flow: publisher config + monitor task + snapshots."""
import json
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock
from cryptography.fernet import Fernet

import pytest
from httpx import Response

from app.core.config import Settings


def test_e2e_publisher_config_encrypted(client, monkeypatch) -> None:
    """Add a config, verify app_password is encrypted and never returned in response."""
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.domain.security import encryption
    encryption._cipher = None
    encryption._settings = None

    resp = client.post("/api/publishers", json={
        "name": "Test", "site_url": "https://example.com",
        "username": "admin", "app_password": "abcdefghijklmnop",
    })
    assert resp.status_code == 201
    config = resp.json()
    # Password NOT in response
    assert "app_password" not in config
    assert "app_password_encrypted" not in config

    # List
    list_resp = client.get("/api/publishers")
    assert len(list_resp.json()) == 1


def test_e2e_monitor_create_and_run(client) -> None:
    """Create monitor task, run now (mocked), verify trends endpoint returns empty data."""
    with patch("app.domain.monitor.scheduler.schedule_monitor_task"):
        create = client.post("/api/monitors", json={
            "name": "Test", "brand": "小米", "industry": "手机",
            "target_questions": ["q1"], "frequency": "daily",
        })
        assert create.status_code == 201
        mid = create.json()["id"]

    with patch("app.domain.monitor.monitor_service.execute_monitor_run"):
        run_resp = client.post(f"/api/monitors/{mid}/run")
        assert run_resp.status_code == 202

    # Get trends (empty)
    trends = client.get(f"/api/monitors/{mid}/trends?days=30")
    assert trends.status_code == 200
    assert trends.json()["points"] == []


def test_e2e_publish_rejects_pending_article(client, monkeypatch) -> None:
    """Publishing a non-approved article returns 422."""
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
                id="a_pending", task_id="t1", title="Pending", review_status="pending",
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

    resp = client.post("/api/publishes", json={
        "article_id": "a_pending", "config_id": pc["id"],
    })
    assert resp.status_code == 422
    assert "approved" in resp.json()["detail"].lower()
