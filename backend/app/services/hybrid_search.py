"""Hybrid search: combine vector (ChromaDB) + keyword (SQLite LIKE) via RRF.

Falls back to keyword-only if ChromaDB fails (degraded mode).
"""
from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.knowledge.vector_index import VectorIndex
from app.repositories.knowledge_repo import KnowledgeRepository
from app.services.embedding import EmbeddingService
from app.services.retrieval.bm25_search import bm25_rank
from app.services.retrieval.query_rewrite import rewrite
from app.services.retrieval.reranker import get_reranker
from app.services.retrieval.semantic_cache import get_cache

logger = structlog.get_logger()


async def _load_corpus(kb_id: str) -> list[tuple[str, str]]:
    """载入 KB 全量 chunk 供 BM25 召回用。返回 [(chunk_id, content), ...]。"""
    async with get_session_factory()() as session:
        chunks = await KnowledgeRepository(session).list_chunks(kb_id)
    return [(c.id, c.content) for c in chunks]


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
    """Orchestrate vector + keyword + RRF with graceful fallback.

    v0.7+ ① 混合检索管道:新增可注入的 __init__(rewriter / reranker / cache / llm)
    与 search_pipeline 全管道方法(缓存 → 改写 → 双路召回 → RRF → 重排)。
    既有 search / _hybrid_search / _keyword_search / search_across_kbs 保持向后兼容。
    """

    def __init__(self, rewriter=None, reranker=None, cache=None, llm=None) -> None:
        # 全部可注入,默认 None 表示在 search_pipeline 内按需取真实实现
        self._rewriter = rewriter
        self._reranker = reranker
        self._cache = cache
        self._llm = llm

    async def search_pipeline(self, kb_id: str, query: str, top_k: int = 5) -> list[dict]:
        """全管道检索:语义缓存 → 查询改写 → 向量+BM25 双路 → RRF → 重排。

        每环都做降级(任一环坏不阻断):缓存/改写/向量/BM25 失败仅 warning。
        无 LLM key → 跳过改写;无 reranker 模型 → 恒等重排;无 Redis → 缓存 no-op。
        """
        settings = get_settings()
        cache = self._cache if self._cache is not None else get_cache(
            settings, EmbeddingService.embed
        )
        reranker = self._reranker if self._reranker is not None else get_reranker(settings)

        # 1. 语义缓存
        cached = await cache.get(query)
        if cached is not None:
            return cached

        # 2. 查询改写
        llm = self._llm
        if llm is None:
            from app.domain.llm_client import LLMClient
            llm = LLMClient(settings)
        if settings.enable_query_rewrite:
            variants = await rewrite(
                query,
                llm,
                n=settings.multi_query_n,
                enable_hyde=settings.enable_hyde,
            )
        else:
            variants = [query]

        # 3. 双路召回(每条改写)
        vector_hits: list[dict] = []
        keyword_hits: list[dict] = []
        corpus = await _load_corpus(kb_id)
        for v in variants:
            try:
                embedding = EmbeddingService.embed([v])[0]
                vector_hits.extend(
                    VectorIndex(kb_id).query(
                        query_embedding=embedding,
                        top_k=settings.hybrid_top_k_vector,
                    )
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("pipeline_vector_failed", error=str(e))
            keyword_hits.extend(bm25_rank(corpus, v, top_k=settings.hybrid_top_k_keyword))

        # 4. RRF 融合 → top-M 候选
        fused = rrf_fusion(
            vector_hits, keyword_hits,
            top_k=settings.rerank_top_m, k=settings.hybrid_rrf_k,
        )

        # 5. Cross-Encoder 重排 → top-k
        reranked = reranker.rerank(query, fused, top_k=top_k)

        # 6. 回填缓存
        await cache.set(query, reranked)
        return reranked

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
        index = VectorIndex(kb_id)
        # 用 EmbeddingService 预计算 query 向量(512 维),与 collection 同空间
        query_embedding = EmbeddingService.embed([query])[0]
        vector_results = index.query(query_embedding=query_embedding, top_k=settings.hybrid_top_k_vector)
        keyword_results = await self._keyword_search(kb_id, query, top_k=settings.hybrid_top_k_keyword)
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

    async def search_across_kbs(self, query: str, top_k: int = 10) -> list[dict]:
        """v0.6 P1.3: hybrid recall across **all** knowledge bases.

        Runs vector search per-KB against each KB's ChromaDB collection and
        a single global keyword search, then RRF-fuses them into one ranked
        list. Each hit carries ``metadata.kb_name`` + ``doc_filename`` so
        the caller can render attribution. Per-KB vector failures are
        logged + skipped (degraded mode).
        """
        settings = get_settings()
        import jieba

        # 1. Vector recall: enumerate KBs, query each collection, tag with kb_name
        kb_list: list = []
        try:
            async with get_session_factory()() as session:
                repo = KnowledgeRepository(session)
                kb_list = await repo.list_kbs()
        except Exception as e:  # noqa: BLE001
            logger.warning("cross_kb_list_failed, falling back to keyword",
                           error=str(e))

        vector_results: list[dict] = []
        kb_name_by_id = {kb.id: kb.name for kb in kb_list}
        # 跨库路径:同一 query 一次算 embedding,所有 KB 共用(避免重复 embed)
        shared_query_embedding = EmbeddingService.embed([query])[0]
        for kb in kb_list:
            try:
                index = VectorIndex(kb.id)
                hits = index.query(
                    query_embedding=shared_query_embedding,
                    top_k=settings.hybrid_top_k_vector,
                )
                for hit in hits:
                    hit["_kb_name"] = kb.name
                vector_results.extend(hits)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "cross_kb_vector_failed",
                    kb_id=kb.id, kb_name=kb.name, error=str(e),
                )

        # 2. Global keyword recall: chunks joined with documents + bases
        keywords = [w for w in jieba.cut(query) if len(w.strip()) > 1]
        keyword_results: list[dict] = []
        if keywords:
            try:
                async with get_session_factory()() as session:
                    repo = KnowledgeRepository(session)
                    kw_hits = await repo.search_chunks_all_keywords(
                        keywords=keywords,
                        top_k=settings.hybrid_top_k_keyword,
                    )
                for hit in kw_hits:
                    keyword_results.append(
                        {
                            "id": hit["chunk"].id,
                            "content": hit["chunk"].content,
                            "metadata": {
                                "doc_id": hit["doc_id"],
                                "chunk_index": hit["chunk_index"],
                                "kb_id": hit["kb_id"],
                                "kb_name": hit["kb_name"],
                                "doc_filename": hit["doc_filename"],
                            },
                            "_sources": ["keyword"],
                        }
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning("cross_kb_keyword_failed", error=str(e))

        # 3. Backfill kb_name on vector-only hits
        for hit in vector_results:
            meta = hit.setdefault("metadata", {})
            if not meta.get("kb_name"):
                meta["kb_name"] = kb_name_by_id.get(meta.get("kb_id", ""), "")

        # 4. RRF fusion
        return rrf_fusion(
            vector_results, keyword_results,
            top_k=top_k, k=settings.hybrid_rrf_k,
        )
