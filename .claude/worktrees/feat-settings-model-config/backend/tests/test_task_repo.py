"""Tests for TaskRepository."""
import json

import pytest

from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
from app.repositories.task_repo import TaskRepository


@pytest.mark.asyncio
async def test_create_task(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    task = await repo.create_task(
        name="T1", kb_id="kb1", brand="Brand",
        topic="Topic", keywords=["k1", "k2"],
        article_count=3, style="neutral", target_length=1500,
    )
    assert task.id != ""
    assert task.status == "pending"
    assert json.loads(task.keywords) == ["k1", "k2"]


@pytest.mark.asyncio
async def test_update_task_status(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    task = await repo.create_task(
        name="T", kb_id="kb1", topic="X", article_count=1, style="neutral",
    )
    await repo.update_task_status(task.id, status="running", progress=50)
    refreshed = await repo.get_task(task.id)
    assert refreshed.status == "running"
    assert refreshed.progress == 50


@pytest.mark.asyncio
async def test_list_tasks_orders_by_created_desc(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    t1 = await repo.create_task(name="T1", kb_id="kb1", topic="X", article_count=1, style="neutral")
    t2 = await repo.create_task(name="T2", kb_id="kb1", topic="Y", article_count=1, style="neutral")
    tasks = await repo.list_tasks()
    assert tasks[0].id == t2.id  # most recent first


@pytest.mark.asyncio
async def test_create_article_placeholder(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    task = await repo.create_task(
        name="T", kb_id="kb1", topic="X", article_count=1, style="neutral",
    )
    article = await repo.create_article(task.id)
    assert article.title == "待生成 #1"
    assert article.review_status == "pending"
    assert article.content is None


@pytest.mark.asyncio
async def test_update_article_content(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()
    task = await repo.create_task(
        name="T", kb_id="kb1", topic="X", article_count=1, style="neutral",
    )
    article = await repo.create_article(task.id)
    await repo.update_article(
        article.id,
        title="新标题",
        content="# 标题\n\n内容",
        content_length=10,
        cited_chunks=["c1", "c2"],
        llm_provider="deepseek",
    )
    refreshed = await repo.get_article(article.id)
    assert refreshed.title == "新标题"
    assert refreshed.content == "# 标题\n\n内容"
    assert json.loads(refreshed.cited_chunks) == ["c1", "c2"]


@pytest.mark.asyncio
async def test_update_article_review(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()
    task = await repo.create_task(
        name="T", kb_id="kb1", topic="X", article_count=1, style="neutral",
    )
    article = await repo.create_article(task.id)
    await repo.update_article_review(article.id, status="approved", note="OK")
    refreshed = await repo.get_article(article.id)
    assert refreshed.review_status == "approved"
    assert refreshed.review_note == "OK"
    assert refreshed.reviewed_at is not None


@pytest.mark.asyncio
async def test_list_articles_by_review_status(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()
    task = await repo.create_task(
        name="T", kb_id="kb1", topic="X", article_count=3, style="neutral",
    )
    a1 = await repo.create_article(task.id)
    a2 = await repo.create_article(task.id)
    a3 = await repo.create_article(task.id)
    await repo.update_article_review(a1.id, status="approved")
    await repo.update_article_review(a2.id, status="rejected", note="bad")

    pending = await repo.list_articles_by_status("pending")
    approved = await repo.list_articles_by_status("approved")
    assert {a.id for a in pending} == {a3.id}
    assert {a.id for a in approved} == {a1.id}
