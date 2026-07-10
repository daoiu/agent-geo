"""Tests for ReindexService (startup-time lazy vectorization)."""
from unittest.mock import patch, MagicMock

import pytest

from app.services.reindex import ReindexService


@pytest.mark.asyncio
async def test_reindex_indexes_missing_chunks(db_session) -> None:
    """Chunks not in ChromaDB should be embedded and added."""
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.models.orm_v02 import KnowledgeBaseORM, KnowledgeDocumentORM, KnowledgeChunkORM

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

            # Mock the batch add
            mock_index._collection = MagicMock()

            stats = await ReindexService().reindex_all()

    # Verify
    assert kb.id in stats
    assert stats[kb.id]["total"] == 2
    assert stats[kb.id]["indexed"] == 2
    assert stats[kb.id]["skipped"] == 0

    # Verify add was called
    assert mock_index._collection.add.called


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