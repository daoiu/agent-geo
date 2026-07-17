"""BM25 召回:rank_bm25.BM25Okapi + 领域分词。

提供纯函数 bm25_rank(便于单测)+ 异步 bm25_search_kb(载入 KB chunk 后调用)。
"""
from __future__ import annotations

from rank_bm25 import BM25Okapi

from app.services.retrieval.tokenizer import tokenize


def bm25_rank(corpus: list[tuple[str, str]], query: str, top_k: int = 20) -> list[dict]:
    """对语料按 BM25 打分排序,返回 [{id, content, _bm25_score}] 列表。

    空 corpus / 空切词后 query → 返回 [];分数 ≤0 的候选也丢弃。
    """
    q_tokens = tokenize(query)
    if not corpus or not q_tokens:
        return []
    tokenized = [tokenize(content) or [""] for _, content in corpus]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(q_tokens)
    ranked = sorted(
        zip(corpus, scores), key=lambda x: -x[1]
    )[:top_k]
    return [
        {"id": cid, "content": content, "_bm25_score": float(score)}
        for (cid, content), score in ranked
        if score > 0
    ]


async def bm25_search_kb(kb_id: str, query: str, top_k: int = 20, repo=None) -> list[dict]:
    """载入 KB chunk 后 BM25 排序。repo=None → 用默认 session。"""
    if repo is None:
        from app.core.db import get_session_factory
        from app.repositories.knowledge_repo import KnowledgeRepository
        async with get_session_factory()() as session:
            chunks = await KnowledgeRepository(session).list_chunks(kb_id)
    else:
        chunks = await repo.list_chunks(kb_id)
    corpus = [(c.id, c.content) for c in chunks]
    return bm25_rank(corpus, query, top_k)