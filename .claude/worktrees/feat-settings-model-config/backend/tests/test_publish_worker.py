"""Tests for publish worker."""
from unittest.mock import patch, AsyncMock

import pytest

from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
from app.models.orm_v03 import PublisherConfigORM
from app.repositories.publisher_repo import PublishRepository
from app.tasks.publish_worker import execute_publish


@pytest.mark.asyncio
async def test_execute_publish_runs_service(db_session) -> None:
    from app.domain.security.encryption import encrypt

    encrypted_pw = encrypt("test")
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(
        id="a1", task_id="t1", title="测试", content="X", review_status="approved",
    )
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted=encrypted_pw,
    )
    db_session.add_all([kb, task, pc])
    await db_session.commit()
    db_session.add(article)
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")

    with patch("app.tasks.publish_worker.PublishService") as MockSvc:
        # PublishService.execute_publish is async, so the mock must be AsyncMock
        MockSvc.return_value.execute_publish = AsyncMock()
        await execute_publish(job.id)
        MockSvc.assert_called_once()
        MockSvc.return_value.execute_publish.assert_called_once_with(job.id)
