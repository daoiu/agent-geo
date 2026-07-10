"""ReindexService 测试(启动时 lazy 向量化)。"""
from unittest.mock import patch, MagicMock

import pytest

from app.services.reindex import ReindexService


@pytest.mark.asyncio
async def test_reindex_indexes_missing_chunks(db_session) -> None:
    """Chunks not in ChromaDB should be embedded and added via VectorIndex.add_chunks."""
    from app.repositories.knowledge_repo import KnowledgeRepository

    # Setup: 1 KB with 2 chunks
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[
            {"chunk_index": 0, "content": "chunk 1", "content_length": 7},
            {"chunk_index": 1, "content": "chunk 2", "content_length": 7},
        ],
    )
    await db_session.commit()

    # Mock VectorIndex.get_all_ids to return empty (nothing indexed yet)
    with patch("app.services.reindex.VectorIndex") as MockIndex:
        mock_index = MockIndex.return_value
        mock_index.get_all_ids.return_value = set()  # nothing indexed

        # Mock EmbeddingService.embed to return fake vectors
        with patch("app.services.reindex.EmbeddingService") as MockEmbed:
            MockEmbed.embed.return_value = [[0.1] * 512, [0.2] * 512]

            stats = await ReindexService().reindex_all()

    # Verify
    assert kb.id in stats
    assert stats[kb.id]["total"] == 2
    assert stats[kb.id]["indexed"] == 2
    assert stats[kb.id]["skipped"] == 0
    assert stats[kb.id]["cleaned"] == 0

    # R6: 走 VectorIndex.add_chunks 封装(传 embeddings),不再 _collection.add
    mock_index.add_chunks.assert_called()
    call_kwargs = mock_index.add_chunks.call_args.kwargs
    assert "embeddings" in call_kwargs
    assert call_kwargs["embeddings"] == [[0.1] * 512, [0.2] * 512]


@pytest.mark.asyncio
async def test_reindex_reindexes_pending_chunks_even_if_id_in_chroma(db_session) -> None:
    """R2 修复:pending_index=True 的 chunks 即便 id 已在 ChromaDB 也要重新索引。"""
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.models.orm_v02 import KnowledgeChunkORM
    from sqlalchemy import update, select

    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[{"chunk_index": 0, "content": "x", "content_length": 1}],
    )
    await db_session.commit()

    # 拿到 chunk id 并 mark pending_index=True(模拟之前 ChromaDB 失败)
    result = await db_session.execute(
        select(KnowledgeChunkORM).where(KnowledgeChunkORM.kb_id == kb.id)
    )
    chunk = result.scalars().one()
    await db_session.execute(
        update(KnowledgeChunkORM).where(KnowledgeChunkORM.id == chunk.id).values(pending_index=True)
    )
    await db_session.commit()

    with patch("app.services.reindex.VectorIndex") as MockIndex, \
         patch("app.services.reindex.EmbeddingService") as MockEmbed:
        mock_index = MockIndex.return_value
        # 模拟 ChromaDB 里其实有这个 chunk(成功索引过)
        mock_index.get_all_ids.return_value = {chunk.id}
        MockEmbed.embed.return_value = [[0.1] * 512]

        stats = await ReindexService().reindex_all()

    # pending_index=True → 即便 id 已在 ChromaDB,也要 reindex
    assert stats[kb.id]["indexed"] == 1
    assert stats[kb.id]["skipped"] == 0
    assert mock_index.add_chunks.called


@pytest.mark.asyncio
async def test_reindex_cleans_orphan_chromadb_chunks(db_session) -> None:
    """R7 修复:SQLite 没有但 ChromaDB 仍有的旧向量应被清理。"""
    from app.repositories.knowledge_repo import KnowledgeRepository

    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[{"chunk_index": 0, "content": "x", "content_length": 1}],
    )
    await db_session.commit()

    with patch("app.services.reindex.VectorIndex") as MockIndex:
        mock_index = MockIndex.return_value
        # ChromaDB 有 2 个 chunks,其中 1 个在 SQLite 不存在(孤儿)
        real_chunk_id = await repo.list_chunk_ids_for_doc(doc.id)
        orphan_id = "orphan-from-failed-delete"
        mock_index.get_all_ids.return_value = {real_chunk_id[0], orphan_id}

        stats = await ReindexService().reindex_all()

    # 孤儿被清理
    mock_index.delete_chunks.assert_called_with([orphan_id])
    assert stats[kb.id]["cleaned"] == 1
    # SQLite 的真 chunk 已在 ChromaDB → 不需重 index
    assert stats[kb.id]["indexed"] == 0
    assert stats[kb.id]["skipped"] == 1


@pytest.mark.asyncio
async def test_reindex_skips_already_indexed(db_session) -> None:
    """Chunks already in ChromaDB should be skipped."""
    from app.repositories.knowledge_repo import KnowledgeRepository

    # Setup
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[{"chunk_index": 0, "content": "x", "content_length": 1}],
    )
    # Get the actual chunk id from the DB
    all_chunks = await repo.list_chunks(kb.id)
    chunk_id = all_chunks[0].id
    await db_session.commit()

    with patch("app.services.reindex.VectorIndex") as MockIndex:
        mock_index = MockIndex.return_value
        # Simulate chunk already indexed
        mock_index.get_all_ids.return_value = {chunk_id}

        stats = await ReindexService().reindex_all()

    # No embedding should happen
    assert stats[kb.id]["indexed"] == 0
    assert stats[kb.id]["skipped"] == 1


@pytest.mark.asyncio
async def test_reindex_handles_empty_kb(db_session) -> None:
    """A KB with no chunks should not be processed."""
    from app.repositories.knowledge_repo import KnowledgeRepository

    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="Empty KB")
    await db_session.commit()
    # No chunks

    stats = await ReindexService().reindex_all()
    assert stats[kb.id]["total"] == 0
    assert stats[kb.id]["indexed"] == 0