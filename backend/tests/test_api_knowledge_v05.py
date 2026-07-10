"""Tests for v0.5 incremental sync hooks in knowledge API + parser worker (spec §7)."""
from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.asyncio
async def test_delete_document_calls_chroma_delete(db_session) -> None:
    """DELETE /api/knowledge/{kb_id}/documents/{doc_id} should call VectorIndex.delete_chunks."""
    from app.repositories.knowledge_repo import KnowledgeRepository

    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=10,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[{"chunk_index": 0, "content": "x", "content_length": 1}],
    )
    await db_session.commit()
    chunk_ids = await repo.list_chunk_ids_for_doc(doc.id)
    assert len(chunk_ids) == 1

    with patch("app.domain.knowledge.vector_index.VectorIndex") as MockIndex:
        mock_index = MockIndex.return_value
        with patch("app.api.knowledge.get_session", return_value=db_session):
            from fastapi.testclient import TestClient
            from app.main import app
            with TestClient(app) as client:
                resp = client.delete(f"/api/knowledge/{kb.id}/documents/{doc.id}")
        assert resp.status_code == 204
        mock_index.delete_chunks.assert_called_once_with(chunk_ids)


@pytest.mark.asyncio
async def test_delete_document_chroma_failure_does_not_break_api(db_session) -> None:
    """ChromaDB delete failure should not cause API to return 500."""
    from app.repositories.knowledge_repo import KnowledgeRepository

    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=10,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[{"chunk_index": 0, "content": "x", "content_length": 1}],
    )
    await db_session.commit()

    with patch("app.domain.knowledge.vector_index.VectorIndex") as MockIndex:
        mock_index = MockIndex.return_value
        mock_index.delete_chunks.side_effect = Exception("ChromaDB down")
        with patch("app.api.knowledge.get_session", return_value=db_session):
            from fastapi.testclient import TestClient
            from app.main import app
            with TestClient(app) as client:
                resp = client.delete(f"/api/knowledge/{kb.id}/documents/{doc.id}")
        # Should still succeed (ChromaDB cleanup is best-effort)
        assert resp.status_code == 204


@pytest.mark.asyncio
async def test_parse_worker_indexes_chunks_to_chroma(db_session) -> None:
    """After parse, new chunks should be added to ChromaDB."""
    from app.repositories.knowledge_repo import KnowledgeRepository
    import os
    import tempfile

    # Create a real file for the parser
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello world. This is a test document with multiple sentences. " * 20)
        tmp_path = f.name

    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path=tmp_path,
        file_type="txt", file_size=100,
    )
    await db_session.commit()

    with patch("app.domain.knowledge.vector_index.VectorIndex") as MockIndex:
        mock_index = MockIndex.return_value

        # Run parse_document directly
        from app.tasks.parser_worker import parse_document
        await parse_document(doc.id)

        # VectorIndex should be constructed and add_chunks called
        MockIndex.assert_called_with(kb.id)
        assert mock_index.add_chunks.called

    os.unlink(tmp_path)


@pytest.mark.asyncio
async def test_parse_worker_marks_chunks_pending_on_chroma_failure(db_session) -> None:
    """If ChromaDB add fails, chunks should be marked pending_index=True."""
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.models.orm_v02 import KnowledgeChunkORM
    from sqlalchemy import select
    import os, tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Some test content. " * 30)
        tmp_path = f.name

    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path=tmp_path,
        file_type="txt", file_size=100,
    )
    await db_session.commit()

    with patch("app.domain.knowledge.vector_index.VectorIndex") as MockIndex:
        mock_index = MockIndex.return_value
        mock_index.add_chunks.side_effect = Exception("ChromaDB down")
        from app.tasks.parser_worker import parse_document
        await parse_document(doc.id)

    # Verify chunks are marked pending_index=True
    result = await db_session.execute(
        select(KnowledgeChunkORM).where(KnowledgeChunkORM.kb_id == kb.id)
    )
    chunks = list(result.scalars().all())
    assert len(chunks) >= 1
    for c in chunks:
        assert c.pending_index is True

    os.unlink(tmp_path)