"""① 混合检索管道:重排测试。

覆盖两件事:IdentityReranker 保序截断、CrossEncoderReranker 按模型打分排序。
CrossEncoder 模型加载较重,单测用 __new__ 跳过 __init__ 直接注入 _model。
"""
from app.services.retrieval.reranker import IdentityReranker, CrossEncoderReranker


def test_identity_keeps_order_and_truncates():
    cands = [{"id": "a", "content": "x"}, {"id": "b", "content": "y"}, {"id": "c", "content": "z"}]
    out = IdentityReranker().rerank("q", cands, top_k=2)
    assert [c["id"] for c in out] == ["a", "b"]


def test_cross_encoder_reorders_by_score(monkeypatch):
    r = CrossEncoderReranker.__new__(CrossEncoderReranker)  # 跳过 __init__ 加载模型

    class _FakeModel:
        def predict(self, pairs):
            # 第二个候选给最高分
            return [0.1, 0.9, 0.5][: len(pairs)]
    r._model = _FakeModel()

    cands = [{"id": "a", "content": "x"}, {"id": "b", "content": "y"}, {"id": "c", "content": "z"}]
    out = r.rerank("q", cands, top_k=2)
    assert out[0]["id"] == "b"
    assert out[0]["_rerank_score"] == 0.9