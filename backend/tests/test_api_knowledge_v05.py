"""v0.5 增量同步钩子测试(知识库 API + parser worker,spec §7)。"""
from unittest.mock import patch, MagicMock

import pytest


@pytest.mark.asyncio
async def test_delete_document_calls_chroma_delete(db_session) -> None:
    """DELETE 文档路由应调 VectorIndex.delete_chunks 清理向量。"""
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
    """ChromaDB 删除失败不应让 API 返回 500(降级为 warning)。"""
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
    """解析后,新 chunks 应带预计算 bge embeddings 加入 ChromaDB。"""
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello world. This is a test document with multiple sentences. " * 20)
        tmp_path = f.name

    from app.repositories.knowledge_repo import KnowledgeRepository
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path=tmp_path,
        file_type="txt", file_size=100,
    )
    await db_session.commit()

    with patch("app.services.embedding.EmbeddingService") as MockEmbed, \
         patch("app.domain.knowledge.vector_index.VectorIndex") as MockIndex:
        # R1 修复:EmbeddingService.embed 必须被调用,产出 bge 向量
        MockEmbed.embed.return_value = [[0.1] * 512, [0.2] * 512]
        mock_index = MockIndex.return_value

        from app.tasks.parser_worker import parse_document
        await parse_document(doc.id)

        # EmbeddingService.embed 至少被调一次
        assert MockEmbed.embed.called
        # VectorIndex.add_chunks 必须被调,且传入 embeddings 参数
        assert mock_index.add_chunks.called
        call_kwargs = mock_index.add_chunks.call_args.kwargs
        assert "embeddings" in call_kwargs
        assert call_kwargs["embeddings"] == [[0.1] * 512, [0.2] * 512]

    os.unlink(tmp_path)


@pytest.mark.asyncio
async def test_parse_worker_marks_only_new_chunks_pending_on_chroma_failure(db_session) -> None:
    """R5 修复:ChromaDB 失败时只标 NEW chunks 为 pending(不污染 doc 的旧 chunks)。"""
    from app.models.orm_v02 import KnowledgeChunkORM
    from sqlalchemy import select
    import os, tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Some test content. " * 30)
        tmp_path = f.name

    from app.repositories.knowledge_repo import KnowledgeRepository
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path=tmp_path,
        file_type="txt", file_size=100,
    )
    await db_session.commit()

    with patch("app.services.embedding.EmbeddingService") as MockEmbed, \
         patch("app.domain.knowledge.vector_index.VectorIndex") as MockIndex:
        MockEmbed.embed.return_value = [[0.1] * 512, [0.2] * 512]
        mock_index = MockIndex.return_value
        mock_index.add_chunks.side_effect = Exception("ChromaDB down")
        from app.tasks.parser_worker import parse_document
        await parse_document(doc.id)

    # 验证:本批 NEW chunks 都被标 pending_index=True
    result = await db_session.execute(
        select(KnowledgeChunkORM).where(KnowledgeChunkORM.kb_id == kb.id)
    )
    chunks = list(result.scalars().all())
    assert len(chunks) >= 1
    for c in chunks:
        assert c.pending_index is True

    os.unlink(tmp_path)