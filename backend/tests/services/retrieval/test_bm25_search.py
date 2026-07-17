"""① 混合检索管道:BM25 召回测试。

覆盖三件事:相关块排前、空 corpus/query 不抛。
"""
from app.services.retrieval.bm25_search import bm25_rank


def test_bm25_ranks_relevant_first():
    corpus = [
        ("c1", "GEO 是生成式引擎优化技术"),
        ("c2", "今天天气很好适合出门"),
        ("c3", "生成式引擎优化能提升品牌曝光"),
    ]
    hits = bm25_rank(corpus, "生成式引擎优化", top_k=2)
    assert len(hits) == 2
    assert hits[0]["id"] in {"c1", "c3"}  # 相关块排前
    assert all("_bm25_score" in h for h in hits)


def test_bm25_empty_corpus():
    assert bm25_rank([], "任意", top_k=5) == []


def test_bm25_empty_query():
    assert bm25_rank([("c1", "内容")], "", top_k=5) == []