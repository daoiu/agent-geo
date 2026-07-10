"""Reindex service: lazy vectorization of existing chunks at startup."""
from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.knowledge.vector_index import VectorIndex
from app.repositories.knowledge_repo import KnowledgeRepository
from app.services.embedding import EmbeddingService

logger = structlog.get_logger()


class ReindexService:
    """Find chunks without vectors and embed them.

    Called once at startup (in main.py lifespan). Idempotent: chunks
    already in ChromaDB are skipped.
    """

    async def reindex_all(self) -> dict[str, dict]:
        """Reindex all knowledge bases. Returns per-kb stats."""
        settings = get_settings()
        stats: dict[str, dict] = {}

        async with get_session_factory()() as session:
            repo = KnowledgeRepository(session)
            kbs = await repo.list_kbs()

            for kb in kbs:
                kb_stats = await self._reindex_one_kb(repo, kb.id, settings)
                stats[kb.id] = kb_stats

        total_indexed = sum(s["indexed"] for s in stats.values())
        logger.info("reindex_done", total_kbs=len(stats), total_indexed=total_indexed)
        return stats

    async def _reindex_one_kb(self, repo: KnowledgeRepository, kb_id: str, settings) -> dict:
        # 1. Get all chunks from SQLite
        all_chunks = await repo.list_chunks(kb_id)
        if not all_chunks:
            return {"total": 0, "indexed": 0, "skipped": 0}

        # 2. Get already-indexed IDs from ChromaDB
        index = VectorIndex(kb_id)
        indexed_ids = index.get_all_ids()

        # 3. Find chunks to index
        to_index = [c for c in all_chunks if c.id not in indexed_ids]
        if not to_index:
            return {"total": len(all_chunks), "indexed": 0, "skipped": len(all_chunks)}

        # 4. Embed + index in batches
        for i in range(0, len(to_index), settings.embedding_batch_size):
            batch = to_index[i:i + settings.embedding_batch_size]
            texts = [c.content for c in batch]
            embeddings = EmbeddingService.embed(texts)
            index._collection.add(
                ids=[c.id for c in batch],
                documents=texts,
                embeddings=embeddings,
                metadatas=[
                    {
                        "doc_id": c.doc_id,
                        "chunk_index": c.chunk_index,
                        "kb_id": kb_id,
                    }
                    for c in batch
                ],
            )

        return {
            "total": len(all_chunks),
            "indexed": len(to_index),
            "skipped": len(all_chunks) - len(to_index),
        }