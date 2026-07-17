"""① 混合检索管道:hybrid_search.search_pipeline 编排测试。

覆盖两件事:缓存命中直返(不进召回)、未命中走「向量+BM25 → RRF → 重排」全管道。
通过 monkeypatch 注入 VectorIndex / EmbeddingService / bm25_rank / rewrite,
避免依赖真实 ChromaDB / LLM。
"""
from app.services.hybrid_search import HybridSearch


class _FakeCacheMiss:
    async def get(self, q):
        return None

    async def set(self, q, r):
        pass


class _FakeCacheHit:
    async def get(self, q):
        return [{"id": "cached"}]

    async def set(self, q, r):
        pass


class _IdReranker:
    def rerank(self, q, cands, top_k):
        return cands[:top_k]


async def test_pipeline_returns_cache_hit_fast(monkeypatch):
    hs = HybridSearch(cache=_FakeCacheHit(), reranker=_IdReranker())
    out = await hs.search_pipeline("kb1", "q", top_k=5)
    assert out == [{"id": "cached"}]  # 命中直接返回,不进召回


async def test_pipeline_recall_rerank(monkeypatch):
    # mock 向量召回 + bm25 + 改写,验证融合→重排出结果
    import app.services.hybrid_search as mod

    class _FakeIndex:
        def __init__(self, kb_id):
            pass

        def query(self, query_embedding, top_k):
            return [{"id": "v1", "content": "向量命中"}]

    # 替成假 embed:任意输入 → 2 维零向量即可
    class _FakeEmbedding:
        @classmethod
        def embed(cls, texts):
            return [[0.0, 0.0] for _ in texts]

    monkeypatch.setattr(mod, "VectorIndex", _FakeIndex)
    monkeypatch.setattr(mod, "EmbeddingService", _FakeEmbedding)
    monkeypatch.setattr(
        mod, "bm25_rank", lambda corpus, q, top_k: [{"id": "b1", "content": "bm25命中"}]
    )

    async def _fake_load_corpus(kb_id):
        return [("b1", "bm25命中")]

    monkeypatch.setattr(mod, "_load_corpus", _fake_load_corpus)

    async def _fake_rewrite(q, llm, n, enable_hyde):
        return [q]

    monkeypatch.setattr(mod, "rewrite", _fake_rewrite)

    hs = HybridSearch(cache=_FakeCacheMiss(), reranker=_IdReranker())
    out = await hs.search_pipeline("kb1", "q", top_k=5)
    ids = {h["id"] for h in out}
    assert ids & {"v1", "b1"}  # 至少召回其一