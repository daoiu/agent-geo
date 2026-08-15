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


@pytest.mark.asyncio
async def test_search_chunks_hybrid_uses_hybrid_search(db_session) -> None:
    """DEPRECATED — search_chunks_hybrid 已在 P0#3 阶段 1 废弃。

    原行为 (repo 委派给 HybridSearch) 违反 AGENTS.md §4 架构分层
    (repositories 不允许 import services)。该方法已迁移到
    tool_executor._execute_search_knowledge 直接调用 HybridSearch。
    """
    from app.repositories.knowledge_repo import KnowledgeRepository

    repo = KnowledgeRepository(db_session)
    with pytest.raises(NotImplementedError, match="P0#3"):
        await repo.search_chunks_hybrid("kb1", "test query", top_k=5)


@pytest.mark.asyncio
async def test_list_kbs_returns_doc_count(db_session) -> None:
    """list_kbs 返回结果带 doc_count 字段（LEFT JOIN GROUP BY 单 SQL）。"""
    repo = KnowledgeRepository(db_session)
    kb0 = await repo.create_kb(name="空 KB")          # 0 docs
    kb1 = await repo.create_kb(name="单文档 KB")       # 1 doc
    await repo.add_document(
        kb_id=kb1.id, filename="a.md", file_path="/tmp/a.md",
        file_type="md", file_size=10,
    )
    kbs = await repo.list_kbs()
    by_id = {kb.id: kb for kb in kbs}
    assert by_id[kb0.id].doc_count == 0
    assert by_id[kb1.id].doc_count == 1


@pytest.mark.asyncio
async def test_list_kbs_doc_count_n_plus_one_safe(db_session) -> None:
    """3 个 KB × 各 2 个 doc — list 一次 SQL（无 N+1）。"""
    from sqlalchemy import event
    from app.core.db import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        repo = KnowledgeRepository(session)
        for n in range(3):
            kb = await repo.create_kb(name=f"KB{n}")
            for d in range(2):
                await repo.add_document(
                    kb_id=kb.id, filename=f"d{d}.md", file_path=f"/tmp/d{d}.md",
                    file_type="md", file_size=10,
                )

    # 用 fresh session + 事件探针
    async with factory() as session:
        statements: list[str] = []

        # before_cursor_execute 是 Engine/Connection 级事件，挂到 session 绑定的
        # 底层 sync engine 上。
        sync_engine = session.sync_session.get_bind()

        @event.listens_for(sync_engine, "before_cursor_execute")
        def _capture(conn, cursor, statement, params, ctx, executemany):  # noqa: ANN001
            statements.append(statement)

        repo = KnowledgeRepository(session)
        kbs = await repo.list_kbs()
        for kb in kbs:
            assert kb.doc_count == 2

        event.remove(sync_engine, "before_cursor_execute", _capture)

        # 应当只有 1 个 SELECT（含 JOIN + GROUP BY）；不允许对每个 KB 多发一个 SELECT
        select_count = sum(1 for s in statements if "SELECT" in s.upper())
        assert select_count == 1, f"expected 1 SELECT, got {select_count}: {statements}"
