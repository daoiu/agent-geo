"""ContentWriterSpecialist 真实执行链路测试(全链路落库,非 mock _execute)。

覆盖 Task 6 落地的三条真实路径:
- single: 生成 → TaskORM(article_count=1) + ArticleORM 落库 + handoff_log
- batch: 1 个 TaskORM + N 篇 ArticleORM
- LLM 生成失败 → SpecialistHandoffError → handoff failed(主 Agent 降级)
"""
from __future__ import annotations

import os

# 测试不调用真实 LLM,允许缺少 API key
os.environ.setdefault("GEO_ALLOW_MISSING_LLM_KEY", "1")

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.domain.agent.content_writer_specialist import ContentWriterSpecialist
from app.domain.agent.handoff import HandoffRequest


def _make_specialist(db_session) -> ContentWriterSpecialist:
    """用测试 DB 的 engine 构造 specialist(纪律 3 状态隔离的独立 factory)。"""
    settings = Settings(_env_file=None)
    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    return ContentWriterSpecialist(settings, factory)


async def _make_kb(db_session) -> str:
    """建一个 KB 返回 kb_id(TaskORM.kb_id NOT NULL)。"""
    from app.repositories.knowledge_repo import KnowledgeRepository

    kb = await KnowledgeRepository(db_session).create_kb(name="KB")
    await db_session.commit()
    return kb.id


def _single_request(kb_id: str) -> HandoffRequest:
    return HandoffRequest(
        handoff_id=str(uuid.uuid4()),
        specialist="content_writer",
        task_id="task-single",
        session_id="session-e2e",
        started_at=datetime.now(timezone.utc),
        timeout_seconds=300,
        payload={
            "mode": "single",
            "kb_id": kb_id,
            "brand": "Acme",
            "topic": "AI 趋势",
            "keywords": ["AI"],
            "style": "professional",
            "target_length": 1500,
            "chunks": [],  # specialist 补检索
        },
    )


@pytest.mark.asyncio
async def test_single_generates_and_persists_article(db_session):
    """single 全链路:生成成功 → task + article 落库,返回 article_id/title/content。"""
    from app.repositories.task_repo import TaskRepository

    kb_id = await _make_kb(db_session)
    specialist = _make_specialist(db_session)

    with patch(
        "app.domain.generator.content_writer_agent.ContentWriterAgent.write_article",
        new=AsyncMock(return_value=("AI 趋势报告", "# AI 趋势报告\n正文内容...")),
    ):
        result = await specialist.handoff(_single_request(kb_id))

    assert result.status == "success"
    assert result.result["title"] == "AI 趋势报告"
    assert result.result["content"].startswith("# AI 趋势报告")
    assert result.result["task_id"]
    assert result.result["article_id"]

    # DB 落库验证
    task_repo = TaskRepository(db_session)
    task = await task_repo.get_task(result.result["task_id"])
    assert task is not None
    assert task.status == "completed"
    assert task.brand == "Acme"
    assert task.article_count == 1

    article = await task_repo.get_article(result.result["article_id"])
    assert article is not None
    assert article.content.startswith("# AI 趋势报告")
    assert article.title == "AI 趋势报告"
    assert article.review_status == "pending"

    # 纪律 5: handoff_log 落库
    from sqlalchemy import select

    from app.models.orm_v05 import HandoffLogORM

    log_row = (
        await db_session.execute(
            select(HandoffLogORM).where(HandoffLogORM.id == result.handoff_id)
        )
    ).scalar_one_or_none()
    assert log_row is not None
    assert log_row.status == "success"


@pytest.mark.asyncio
async def test_single_llm_failure_raises_handoff_failed(db_session):
    """LLM transient 失败(content 空)→ handoff failed,article 标错误。"""
    from app.repositories.task_repo import TaskRepository

    kb_id = await _make_kb(db_session)
    specialist = _make_specialist(db_session)

    with patch(
        "app.domain.generator.content_writer_agent.ContentWriterAgent.write_article",
        new=AsyncMock(return_value=("", "")),  # transient 失败约定
    ):
        result = await specialist.handoff(_single_request(kb_id))

    assert result.status == "failed"
    assert "LLM 调用失败" in result.error or "transient" in result.error

    # article 应标记失败(审计可见)
    task_repo = TaskRepository(db_session)
    tasks = await task_repo.list_tasks()
    assert any(t.brand == "Acme" for t in tasks)
    failed_task = next(t for t in tasks if t.brand == "Acme")
    arts = await task_repo.list_articles(failed_task.id)
    assert len(arts) == 1
    assert "生成失败" in (arts[0].title or "")


@pytest.mark.asyncio
async def test_batch_generates_n_articles(db_session):
    """batch 全链路:1 个 TaskORM + N 篇 ArticleORM 全部落库。"""
    from app.repositories.task_repo import TaskRepository

    kb_id = await _make_kb(db_session)
    specialist = _make_specialist(db_session)

    request = HandoffRequest(
        handoff_id=str(uuid.uuid4()),
        specialist="content_writer",
        task_id="task-batch",
        session_id="session-e2e",
        started_at=datetime.now(timezone.utc),
        timeout_seconds=300,
        payload={
            "mode": "batch",
            "kb_id": kb_id,
            "brand": "Acme",
            "topic": "批量主题",
            "keywords": ["AI"],
            "article_count": 3,
            "style": "neutral",
            "target_length": 1500,
        },
    )

    with patch(
        "app.domain.generator.content_writer_agent.ContentWriterAgent.write_article",
        new=AsyncMock(return_value=("标题", "正文...")),
    ):
        result = await specialist.handoff_batch(request)

    assert result.status == "success"
    assert len(result.result["task_ids"]) == 1
    assert len(result.result["article_ids"]) == 3
    assert result.result["failed_count"] == 0

    task_repo = TaskRepository(db_session)
    task = await task_repo.get_task(result.result["task_ids"][0])
    assert task is not None
    assert task.status == "completed"
    articles = await task_repo.list_articles(task.id)
    assert len(articles) == 3
    assert all(a.content == "正文..." for a in articles)


@pytest.mark.asyncio
async def test_batch_partial_failure_marks_articles(db_session):
    """batch 部分失败:失败篇标 error_message,其余正常落库。"""
    from app.repositories.task_repo import TaskRepository

    kb_id = await _make_kb(db_session)
    specialist = _make_specialist(db_session)

    request = HandoffRequest(
        handoff_id=str(uuid.uuid4()),
        specialist="content_writer",
        task_id="task-batch-partial",
        session_id="session-e2e",
        started_at=datetime.now(timezone.utc),
        timeout_seconds=300,
        payload={
            "mode": "batch",
            "kb_id": kb_id,
            "brand": "Acme",
            "topic": "批量主题",
            "keywords": [],
            "article_count": 2,
            "style": "neutral",
            "target_length": 1500,
        },
    )

    with patch(
        "app.domain.generator.content_writer_agent.ContentWriterAgent.write_article",
        new=AsyncMock(side_effect=[("标题", "正文..."), ("", "")]),
    ):
        result = await specialist.handoff_batch(request)

    assert result.status == "success"
    assert result.result["failed_count"] == 1
    assert len(result.result["article_ids"]) == 1

    task_repo = TaskRepository(db_session)
    articles = await task_repo.list_articles(result.result["task_ids"][0])
    ok = [a for a in articles if a.error_message is None]
    failed = [a for a in articles if a.error_message is not None]
    assert len(failed) == 1
    assert len(failed[0].error_message or "") > 0
    assert ok[0].content == "正文..."
