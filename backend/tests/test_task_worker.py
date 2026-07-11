"""Tests for the task worker."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.repositories.knowledge_repo import KnowledgeRepository
from app.repositories.task_repo import TaskRepository
from app.tasks.task_worker import run_task


def _make_test_factory(db_session):
    """Wrap a single AsyncSession in a sessionmaker that yields the same session."""
    return async_sessionmaker(bind=db_session.bind, expire_on_commit=False)


async def _reload(db_session, model_cls, obj_id):
    """Reload an ORM row fresh from the DB to avoid lazy-load IO after worker commit."""
    from sqlalchemy import select
    stmt = select(model_cls).where(model_cls.id == obj_id)
    result = await db_session.execute(stmt)
    return result.scalar_one()


@pytest.mark.asyncio
async def test_run_task_creates_articles_and_generates(db_session) -> None:
    factory = _make_test_factory(db_session)
    repo = KnowledgeRepository(db_session)
    task_repo = TaskRepository(db_session)

    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[
            {"chunk_index": 0, "content": "测试内容", "content_length": 4},
        ],
    )

    task = await task_repo.create_task(
        name="T", kb_id=kb.id, brand="Brand",
        topic="测试主题", keywords=[],
        article_count=2, style="neutral", target_length=500,
    )

    with patch("app.tasks.task_worker.ContentWriterAgent") as MockWriter:
        mock_instance = MockWriter.return_value
        mock_instance.write_article = AsyncMock(return_value=("生成标题", "生成内容"))
        await run_task(task.id, session=db_session)

    from app.models.orm_v02 import TaskORM
    refreshed = await _reload(db_session, TaskORM, task.id)
    assert refreshed.status == "completed"
    assert refreshed.progress == 100
    articles = await task_repo.list_articles(task.id)
    assert len(articles) == 2
    assert all(a.title == "生成标题" for a in articles)
    assert all(a.content == "生成内容" for a in articles)


@pytest.mark.asyncio
async def test_run_task_continues_on_article_failure(db_session) -> None:
    factory = _make_test_factory(db_session)
    repo = KnowledgeRepository(db_session)
    task_repo = TaskRepository(db_session)

    kb = await repo.create_kb(name="KB")
    task = await task_repo.create_task(
        name="T", kb_id=kb.id, topic="X", article_count=3, style="neutral",
    )

    with patch("app.tasks.task_worker.ContentWriterAgent") as MockWriter:
        mock_instance = MockWriter.return_value
        # First succeeds, second raises, third succeeds
        mock_instance.write_article = AsyncMock(
            side_effect=[("T1", "C1"), Exception("LLM down"), ("T3", "C3")]
        )
        await run_task(task.id, session=db_session)

    from app.models.orm_v02 import TaskORM
    refreshed = await _reload(db_session, TaskORM, task.id)
    assert refreshed.status == "completed"
    articles = await task_repo.list_articles(task.id)
    assert len(articles) == 3
    # Middle one has error
    assert articles[1].error_message is not None
    assert articles[1].content is None
    # Others succeeded
    assert articles[0].content == "C1"
    assert articles[2].content == "C3"


@pytest.mark.asyncio
async def test_run_task_respects_cancellation(db_session) -> None:
    factory = _make_test_factory(db_session)
    repo = KnowledgeRepository(db_session)
    task_repo = TaskRepository(db_session)

    kb = await repo.create_kb(name="KB")
    task = await task_repo.create_task(
        name="T", kb_id=kb.id, topic="X", article_count=5, style="neutral",
    )

    # Mark task as cancelled before run
    await task_repo.update_task_status(task.id, status="cancelled")

    with patch("app.tasks.task_worker.ContentWriterAgent") as MockWriter:
        mock_instance = MockWriter.return_value
        mock_instance.write_article = AsyncMock(return_value=("T", "C"))
        await run_task(task.id, session=db_session)

    # No articles should be created since task was cancelled
    from sqlalchemy import select
    from app.models.orm_v02 import ArticleORM
    result = await db_session.execute(
        select(ArticleORM).where(ArticleORM.task_id == task.id)
    )
    assert len(list(result.scalars().all())) == 0
