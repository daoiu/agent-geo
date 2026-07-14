"""P1#28（Task 29）: 人评抽样机制验证。

目标:
- 能从 EvalReport 随机抽 N 条
- 抽样可重现(同 seed = 同结果)
- 优先抽"边界 + 失败"案例(高质量人工 review 信号)
- 导出为 CSV (机器可读) + Markdown (人可读)
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from evals.human_review import (
    HumanSample,
    export_csv,
    export_markdown,
    sample_for_review,
    stratified_sample,
)


def _make_fake_report(total: int = 20, fail_ratio: float = 0.3) -> dict:
    """构造一个伪 EvalReport.to_dict() 数据用于测试。"""
    details = []
    for i in range(total):
        is_fail = (i % 10) < int(fail_ratio * 10)
        details.append(
            {
                "category": ["normal", "boundary", "missing", "induction", "refusal"][i % 5],
                "query": f"test query {i}",
                "result": {
                    "pass": not is_fail,
                    "score": 0.3 if is_fail else 0.8,
                    "keyword_score": 0.4 if is_fail else 0.9,
                    "tool_score": 0.5,
                    "llm_score": 0.5,
                    "reason": "test reason",
                },
                "latency_ms": 10.0 + i,
            }
        )
    return {
        "total": total,
        "pass": int(total * (1 - fail_ratio)),
        "pass_rate": 1 - fail_ratio,
        "avg_score": 0.7,
        "avg_latency_ms": 15.0,
        "by_category": {},
        "details": details,
        "note": "fake",
    }


def test_human_sample_dataclass_roundtrip():
    """HumanSample 应能 round-trip dict。"""
    s = HumanSample(
        id="abc123",
        category="normal",
        query="test",
        response="agent said something",
        expected_keywords=["k1", "k2"],
        expected_tool="search",
        judge_pass=True,
        judge_score=0.8,
        latency_ms=10.5,
    )
    d = s.to_dict()
    assert d["id"] == "abc123"
    assert d["judge_pass"] is True
    assert d["judge_score"] == 0.8
    # round-trip
    s2 = HumanSample.from_dict(d)
    assert s2.id == s.id
    assert s2.expected_keywords == ["k1", "k2"]


def test_sample_for_review_returns_n_samples():
    """抽样 N 条应返回 N 条(不超过总数)。"""
    report = _make_fake_report(total=20)
    samples = sample_for_review(report, n=5, seed=42)
    assert len(samples) == 5
    assert all(isinstance(s, HumanSample) for s in samples)


def test_sample_for_review_is_reproducible_with_seed():
    """同 seed 必须返回相同样本。"""
    report = _make_fake_report(total=30)
    s1 = sample_for_review(report, n=10, seed=42)
    s2 = sample_for_review(report, n=10, seed=42)
    assert [s.id for s in s1] == [s.id for s in s2]


def test_sample_for_review_different_seed_different_results():
    """不同 seed 应给出不同样本(高概率)。"""
    report = _make_fake_report(total=30)
    s1 = sample_for_review(report, n=10, seed=42)
    s2 = sample_for_review(report, n=10, seed=99)
    # 不应完全相同(30 条抽 10 条同 seed 才相同)
    overlap = len(set(s.id for s in s1) & set(s.id for s in s2))
    assert overlap < 10, "不同 seed 不应给完全相同样本"


def test_sample_for_review_prefers_failures_and_boundary():
    """抽样应优先失败/边界案例(高 review 价值)。"""
    report = _make_fake_report(total=20, fail_ratio=0.5)  # 10 fail, 10 pass
    samples = sample_for_review(report, n=6, seed=42)
    # 至少 50% 应是失败案例
    fail_count = sum(1 for s in samples if not s.judge_pass)
    assert fail_count >= 3, (
        f"抽样应优先失败案例; got {fail_count}/6 fails in samples"
    )


def test_sample_for_review_handles_n_larger_than_total():
    """N 大于总数应 clamp 到总数。"""
    report = _make_fake_report(total=5)
    samples = sample_for_review(report, n=100, seed=42)
    assert len(samples) == 5


def test_stratified_sample_balances_categories():
    """分层抽样应覆盖各类别。"""
    report = _make_fake_report(total=20)  # 4 条/类
    samples = stratified_sample(report, n=5, seed=42)
    categories = {s.category for s in samples}
    # 5 条应至少覆盖 3 类
    assert len(categories) >= 3, f"分层抽样应覆盖多类; got {categories}"


def test_export_csv_creates_valid_csv(tmp_path: Path):
    """CSV 导出应包含必要字段。"""
    report = _make_fake_report(total=10)
    samples = sample_for_review(report, n=3, seed=42)
    csv_path = tmp_path / "review.csv"
    export_csv(samples, csv_path)
    assert csv_path.exists()
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 3
    required = {"id", "category", "query", "response", "expected_keywords",
                "judge_pass", "judge_score"}
    assert required.issubset(set(reader.fieldnames or [])), (
        f"CSV missing fields; got {reader.fieldnames}"
    )


def test_export_markdown_is_human_readable(tmp_path: Path):
    """Markdown 导出应包含可读表格 + 类目分组。"""
    report = _make_fake_report(total=10)
    samples = sample_for_review(report, n=3, seed=42)
    md_path = tmp_path / "review.md"
    export_markdown(samples, md_path)
    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")
    # 必须有 markdown 标题
    assert re.search(r"^#\s+人评抽样", content, re.MULTILINE)
    # 必须有 query
    assert "test query" in content
    # 必须有 judge_pass 显示
    assert "✅" in content or "❌" in content or "pass" in content.lower()


def test_export_csv_handles_unicode_in_keywords(tmp_path: Path):
    """CSV 导出应正确处理中文关键词。"""
    report = {
        "total": 1,
        "pass": 0,
        "pass_rate": 0.0,
        "avg_score": 0.0,
        "avg_latency_ms": 0.0,
        "details": [
            {
                "category": "normal",
                "query": "小米品牌 GEO",
                "result": {"pass": False, "score": 0.3, "keyword_score": 0.5,
                           "tool_score": 0.5, "llm_score": 0.5, "reason": "test"},
                "latency_ms": 10.0,
            }
        ],
        "by_category": {},
        "note": "test",
    }
    samples = sample_for_review(report, n=1, seed=42)
    csv_path = tmp_path / "review_unicode.csv"
    export_csv(samples, csv_path)
    content = csv_path.read_text(encoding="utf-8")
    assert "小米" in content
    assert "GEO" in content