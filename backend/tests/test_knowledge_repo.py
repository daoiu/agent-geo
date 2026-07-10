"""Tests for KnowledgeRepository."""
import pytest

from app.models.orm_v02 import (
    KnowledgeBaseORM,
    KnowledgeChunkORM,
    KnowledgeDocumentORM,
)
from app.repositories.knowledge_repo import KnowledgeRepository


@pytest.mark.asyncio
async def test_create_and_get_kb(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="测试 KB", description="描述")
    fetched = await repo.get_kb(kb.id)
    assert fetched is not None
    assert fetched.name == "测试 KB"


@pytest.mark.asyncio
async def test_list_kbs(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    await repo.create_kb(name="A")
    await repo.create_kb(name="B")
    kbs = await repo.list_kbs()
    assert len(kbs) == 2


@pytest.mark.asyncio
async def test_add_document_and_list(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.pdf", file_path="/tmp/x.pdf",
        file_type="pdf", file_size=1024,
    )
    docs = await repo.list_documents(kb.id)
    assert len(docs) == 1
    assert docs[0].parse_status == "pending"


@pytest.mark.asyncio
async def test_update_document_status(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.update_document_status(
        doc.id, status="success", chunk_count=10
    )
    refreshed = await repo.get_document(doc.id)
    assert refreshed.parse_status == "success"
    assert refreshed.chunk_count == 10
    assert refreshed.parse_error is None


@pytest.mark.asyncio
async def test_update_document_status_with_error(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="bad.pdf", file_path="/tmp/bad.pdf",
        file_type="pdf", file_size=0,
    )
    await repo.update_document_status(doc.id, status="failed", error="corrupted")
    refreshed = await repo.get_document(doc.id)
    assert refreshed.parse_status == "failed"
    assert refreshed.parse_error == "corrupted"


@pytest.mark.asyncio
async def test_add_and_search_chunks(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    count = await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[
            {"chunk_index": 0, "content": "小米手机性能优秀", "content_length": 8},
            {"chunk_index": 1, "content": "华为手机拍照好", "content_length": 7},
            {"chunk_index": 2, "content": "苹果生态系统完善", "content_length": 8},
        ],
    )
    assert count == 3

    # Search for "小米"
    results = await repo.search_chunks_by_keyword(
        kb_id=kb.id, keywords=["小米"], top_k=5
    )
    assert len(results) == 1
    assert "小米" in results[0].content


@pytest.mark.asyncio
async def test_search_chunks_ranks_by_keyword_count(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[
            {"chunk_index": 0, "content": "小米手机", "content_length": 4},
            {"chunk_index": 1, "content": "小米手机小米手机小米", "content_length": 9},
        ],
    )
    results = await repo.search_chunks_by_keyword(
        kb_id=kb.id, keywords=["小米"], top_k=5
    )
    # First result should be the one with more "小米" mentions
    assert results[0].chunk_index == 1


@pytest.mark.asyncio
async def test_delete_kb_cascades(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[{"chunk_index": 0, "content": "hello", "content_length": 5}],
    )
    await repo.delete_kb(kb.id)
    from sqlalchemy import select
    result = await db_session.execute(
        select(KnowledgeDocumentORM).where(KnowledgeDocumentORM.kb_id == kb.id)
    )
    assert result.scalars().all() == []
