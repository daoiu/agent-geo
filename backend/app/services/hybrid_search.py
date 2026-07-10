"""Hybrid search: combine vector (ChromaDB) + keyword (SQLite LIKE) via RRF.

Falls back to keyword-only if ChromaDB fails (degraded mode).
"""
from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.knowledge.vector_index import VectorIndex
from app.repositories.knowledge_repo import KnowledgeRepository

logger = structlog.get_logger()


def rrf_fusion(
    vector_results: list[dict],
    keyword_results: list[dict],
    top_k: int = 5,
    k: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion.

    Final score = sum(1 / (k + rank)) for each list the chunk appears in.
    Chunks appearing in both lists get summed scores (ranked higher).
    """
    scores: dict[str, float] = {}
    chunk_data: dict[str, dict] = {}

    for rank, chunk in enumerate(vector_results, start=1):
        cid = chunk["id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        chunk_data[cid] = {**chunk, "_sources": ["vector"]}

    for rank, chunk in enumerate(keyword_results, start=1):
        cid = chunk["id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        if cid in chunk_data:
            existing = chunk_data[cid].get("_sources", [])
            chunk_data[cid] = {**chunk_data[cid], **chunk, "_sources": existing + ["keyword"]}
        else:
            chunk_data[cid] = {**chunk, "_sources": ["keyword"]}

    sorted_ids = sorted(scores.keys(), key=lambda x: -scores[x])
    return [{**chunk_data[cid], "_rrf_score": scores[cid]} for cid in sorted_ids[:top_k]]


class HybridSearch:
    """Orchestrates vector + keyword + RRF with graceful fallback."""

    async def search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Hybrid search. Falls back to keyword-only if vector fails."""
        try:
            return await self._hybrid_search(kb_id, query, top_k)
        except Exception as e:
            logger.warning(
                "hybrid_search_failed, falling back to keyword",
                kb_id=kb_id, error=str(e),
            )
            return await self._keyword_search(kb_id, query, top_k)

    async def _hybrid_search(self, kb_id: str, query: str, top_k: int) -> list[dict]:
        settings = get_settings()
        # 1. Vector search
        index = VectorIndex(kb_id)
        vector_results = index.query(query_text=query, top_k=settings.hybrid_top_k_vector)
        # 2. Keyword search
        keyword_results = await self._keyword_search(kb_id, query, top_k=settings.hybrid_top_k_keyword)
        # 3. RRF fusion
        return rrf_fusion(vector_results, keyword_results, top_k=top_k, k=settings.hybrid_rrf_k)

    async def _keyword_search(self, kb_id: str, query: str, top_k: int) -> list[dict]:
        """Use existing v0.2 jieba-based keyword search."""
        import jieba

        keywords = [w for w in jieba.cut(query) if len(w.strip()) > 1]
        if not keywords:
            return []
        async with get_session_factory()() as session:
            repo = KnowledgeRepository(session)
            chunks = await repo.search_chunks_by_keyword(
                kb_id=kb_id, keywords=keywords, top_k=top_k
            )
        return [
            {
                "id": c.id,
                "content": c.content,
                "metadata": {
                    "doc_id": c.doc_id,
                    "chunk_index": c.chunk_index,
                    "kb_id": c.kb_id,
                },
                "_sources": ["keyword"],
            }
            for c in chunks
        ]