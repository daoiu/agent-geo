"""Tests for PublishRepository."""
import pytest

from app.models.orm_v03 import PublisherConfigORM, PublishJobORM
from app.repositories.publisher_repo import PublishRepository


@pytest.mark.asyncio
async def test_create_publisher_config(db_session) -> None:
    repo = PublishRepository(db_session)
    pc = await repo.create_publisher_config(
        name="主站", site_url="https://example.com",
        username="admin", app_password_encrypted="encrypted-blob",
    )
    assert pc.id != ""
    assert pc.is_default == 0


@pytest.mark.asyncio
async def test_get_publisher_config(db_session) -> None:
    repo = PublishRepository(db_session)
    pc = await repo.create_publisher_config(
        name="X", site_url="https://x.com", username="u",
        app_password_encrypted="enc",
    )
    fetched = await repo.get_publisher_config(pc.id)
    assert fetched is not None
    assert fetched.name == "X"


@pytest.mark.asyncio
async def test_list_publisher_configs(db_session) -> None:
    repo = PublishRepository(db_session)
    await repo.create_publisher_config(name="A", site_url="https://a.com", username="u", app_password_encrypted="e")
    await repo.create_publisher_config(name="B", site_url="https://b.com", username="u", app_password_encrypted="e")
    pcs = await repo.list_publisher_configs()
    assert len(pcs) == 2


@pytest.mark.asyncio
async def test_delete_publisher_config(db_session) -> None:
    repo = PublishRepository(db_session)
    pc = await repo.create_publisher_config(name="X", site_url="https://x.com", username="u", app_password_encrypted="e")
    await repo.delete_publisher_config(pc.id)
    assert await repo.get_publisher_config(pc.id) is None


@pytest.mark.asyncio
async def test_update_publisher_config(db_session) -> None:
    repo = PublishRepository(db_session)
    pc = await repo.create_publisher_config(
        name="原名", site_url="https://x.com", username="u", app_password_encrypted="e",
    )
    await repo.update_publisher_config(
        pc.id, name="新名", site_url="https://y.com", username="admin", is_default=True,
    )
    fetched = await repo.get_publisher_config(pc.id)
    assert fetched is not None
    assert fetched.name == "新名"
    assert fetched.site_url == "https://y.com"
    assert fetched.username == "admin"
    assert fetched.is_default == 1


@pytest.mark.asyncio
async def test_create_publish_job(db_session) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted="e",
    )
    db_session.add_all([kb, task, pc])
    await db_session.commit()
    db_session.add(article)
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")
    assert job.id != ""
    assert job.status == "pending"
    assert job.title_override is None


@pytest.mark.asyncio
async def test_create_publish_job_with_title_override(db_session) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted="e",
    )
    db_session.add_all([kb, task, pc])
    await db_session.commit()
    db_session.add(article)
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(
        article_id="a1", config_id="pc1", title_override="新标题",
    )
    assert job.title_override == "新标题"


@pytest.mark.asyncio
async def test_update_publish_job_status(db_session) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted="e",
    )
    db_session.add_all([kb, task, pc])
    await db_session.commit()
    db_session.add(article)
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")
    await repo.update_publish_job_status(job.id, status="running")
    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "running"

    await repo.update_publish_job_status(job.id, status="failed", error="oops")
    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "failed"
    assert refreshed.error_message == "oops"


@pytest.mark.asyncio
async def test_update_publish_job_success(db_session) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted="e",
    )
    db_session.add_all([kb, task, pc])
    await db_session.commit()
    db_session.add(article)
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")
    await repo.update_publish_job_success(
        job.id, remote_post_id=42, remote_url="https://x.com/?p=42"
    )
    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "success"
    assert refreshed.remote_post_id == 42
    assert refreshed.remote_url == "https://x.com/?p=42"
    assert refreshed.published_at is not None


@pytest.mark.asyncio
async def test_count_publish_jobs_by_config(db_session) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted="e",
    )
    db_session.add_all([kb, task, pc])
    await db_session.commit()
    db_session.add(article)
    await db_session.commit()

    repo = PublishRepository(db_session)
    await repo.create_publish_job(article_id="a1", config_id="pc1")
    await repo.create_publish_job(article_id="a1", config_id="pc1")
    count = await repo.count_publish_jobs_by_config("pc1")
    assert count == 2
