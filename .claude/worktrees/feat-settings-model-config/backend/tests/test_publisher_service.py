"""Tests for PublishService (orchestrates publish flow)."""
from unittest.mock import patch

import pytest
import respx
from cryptography.fernet import Fernet
from httpx import Response

from app.core.config import Settings
from app.domain.publisher.publisher_service import PublishService
from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
from app.models.orm_v03 import PublisherConfigORM
from app.repositories.publisher_repo import PublishRepository


@pytest.fixture
def settings_with_key() -> Settings:
    return Settings(
        encryption_key=Fernet.generate_key().decode(),
        publish_timeout_s=5,
    )


async def _setup_approved_article(session, *, article_id="a1", config_id="pc1"):
    """Insert KB + task + approved article + publisher config. Returns encrypted password."""
    from app.domain.security.encryption import encrypt

    encrypted_pw = encrypt("test-app-password")
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(
        id=article_id, task_id="t1",
        title="测试文章",
        content="# 标题\n\n内容",
        review_status="approved",
    )
    pc = PublisherConfigORM(
        id=config_id, name="主站", site_url="https://example.com",
        username="admin", app_password_encrypted=encrypted_pw,
    )
    session.add_all([kb, task, pc])
    await session.commit()
    session.add(article)
    await session.commit()
    return encrypted_pw


@pytest.mark.asyncio
@respx.mock
async def test_execute_publish_success(db_session, settings_with_key, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings_with_key)
    from app.domain.security import encryption
    encryption._cipher = None
    encryption._settings = settings_with_key

    await _setup_approved_article(db_session)

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")

    respx.post("https://example.com/wp-json/wp/v2/posts").mock(
        return_value=Response(
            201,
            json={"id": 42, "link": "https://example.com/?p=42"},
        )
    )

    svc = PublishService(repo=repo, settings=settings_with_key)
    await svc.execute_publish(job.id)

    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "success"
    assert refreshed.remote_post_id == 42
    assert refreshed.remote_url == "https://example.com/?p=42"


@pytest.mark.asyncio
@respx.mock
async def test_execute_publish_failure_401(db_session, settings_with_key, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings_with_key)
    from app.domain.security import encryption
    encryption._cipher = None
    encryption._settings = settings_with_key

    await _setup_approved_article(db_session)

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")

    respx.post("https://example.com/wp-json/wp/v2/posts").mock(
        return_value=Response(401, json={"code": "rest_unauthorized"})
    )

    svc = PublishService(repo=repo, settings=settings_with_key)
    await svc.execute_publish(job.id)

    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "failed"
    assert "认证失败" in refreshed.error_message


@pytest.mark.asyncio
async def test_execute_publish_rejects_non_approved_article(db_session, settings_with_key) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    from app.domain.security.encryption import encrypt

    encrypted_pw = encrypt("test")
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(id="t1", name="T", kb_id="kb1", topic="X", article_count=1, style="neutral", target_length=1000)
    article = ArticleORM(id="a1", task_id="t1", title="Pending", review_status="pending", content="X")
    pc = PublisherConfigORM(id="pc1", name="P", site_url="https://x.com", username="u", app_password_encrypted=encrypted_pw)
    db_session.add_all([kb, task, pc])
    await db_session.commit()
    db_session.add(article)
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")

    svc = PublishService(repo=repo, settings=settings_with_key)
    await svc.execute_publish(job.id)

    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "failed"
    assert "not approved" in refreshed.error_message
