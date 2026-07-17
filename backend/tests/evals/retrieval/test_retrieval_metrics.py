"""检索指标纯函数测试。TDD:Step 1 — 先写失败测试,确认红色。"""
from evals.retrieval.retrieval_metrics import recall_at_k, mrr_at_k, precision_at_k


def test_recall_full_hit():
    assert recall_at_k(["a", "b", "c"], ["a", "b"], k=3) == 1.0


def test_recall_partial():
    assert recall_at_k(["a", "x", "y"], ["a", "b"], k=3) == 0.5


def test_recall_respects_k():
    # 相关命中排在第 4 位,k=3 截断后召回 0
    assert recall_at_k(["x", "y", "z", "a"], ["a"], k=3) == 0.0


def test_recall_empty_relevant_is_one():
    # 无相关标注时约定返回 1.0(不惩罚)
    assert recall_at_k(["a"], [], k=3) == 1.0


def test_mrr_first_position():
    assert mrr_at_k(["a", "b"], ["a"], k=3) == 1.0


def test_mrr_second_position():
    assert mrr_at_k(["x", "a"], ["a"], k=3) == 0.5


def test_mrr_no_hit():
    assert mrr_at_k(["x", "y"], ["a"], k=3) == 0.0


def test_precision_at_k():
    # 前 3 命中 2 个 → 2/3
    assert round(precision_at_k(["a", "b", "x"], ["a", "b"], k=3), 3) == 0.667


def test_dedup_retrieved():
    # 重复 id 不重复计分
    assert recall_at_k(["a", "a", "b"], ["a", "b"], k=3) == 1.0