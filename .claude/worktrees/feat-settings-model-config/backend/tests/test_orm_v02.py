"""Tests for v0.2 ORM models."""
import json

import pytest

from app.models.orm_v02 import (
    ArticleORM,
    KnowledgeBaseORM,
    KnowledgeChunkORM,
    KnowledgeDocumentORM,
    TaskORM,
)


@pytest.mark.asyncio
async def test_kb_orm_create_and_read(db_session) -> None:
    kb = KnowledgeBaseORM(
        id="kb1",
        name="测试知识库",
        description="描述",
    )
    db_session.add(kb)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(KnowledgeBaseORM).where(KnowledgeBaseORM.id == "kb1")
    )
    fetched = result.scalar_one()
    assert fetched.name == "测试知识库"


@pytest.mark.asyncio
async def test_document_orm_foreign_key(db_session) -> None:
    from sqlalchemy import select

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    doc = KnowledgeDocumentORM(
        id="d1",
        kb_id="kb1",
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_type="pdf",
        parse_status="pending",
    )
    db_session.add(doc)
    await db_session.commit()

    result = await db_session.execute(
        select(KnowledgeDocumentORM).where(KnowledgeDocumentORM.id == "d1")
    )
    fetched = result.scalar_one()
    assert fetched.kb_id == "kb1"
    assert fetched.parse_status == "pending"


@pytest.mark.asyncio
async def test_chunk_orm(db_session) -> None:
    from sqlalchemy import select

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    doc = KnowledgeDocumentORM(
        id="d1", kb_id="kb1", filename="x.txt",
        file_path="/tmp/x.txt", file_type="txt", parse_status="success",
    )
    db_session.add_all([kb, doc])
    await db_session.commit()

    chunk = KnowledgeChunkORM(
        id="c1", doc_id="d1", kb_id="kb1",
        chunk_index=0, content="some content", content_length=12,
    )
    db_session.add(chunk)
    await db_session.commit()

    result = await db_session.execute(
        select(KnowledgeChunkORM).where(KnowledgeChunkORM.id == "c1")
    )
    fetched = result.scalar_one()
    assert fetched.content == "some content"
    assert fetched.chunk_index == 0


@pytest.mark.asyncio
async def test_task_orm(db_session) -> None:
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    task = TaskORM(
        id="t1", name="测试任务", kb_id="kb1",
        brand="测试品牌", topic="主题", keywords=json.dumps(["k1", "k2"]),
        article_count=3, style="neutral", target_length=1500,
        status="pending",
    )
    db_session.add(task)
    await db_session.commit()

    assert task.status == "pending"
    assert task.article_count == 3


@pytest.mark.asyncio
async def test_article_orm(db_session) -> None:
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1",
        topic="X", article_count=1, style="neutral", target_length=1000,
    )
    db_session.add_all([kb, task])
    await db_session.commit()

    article = ArticleORM(
        id="a1", task_id="t1", title="待生成 #1",
        review_status="pending", cited_chunks=json.dumps([]),
    )
    db_session.add(article)
    await db_session.commit()

    assert article.review_status == "pending"
    assert article.error_message is None
