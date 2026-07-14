"""ContentWriter Specialist LLM-as-judge 评测基线测试。"""
from __future__ import annotations

import os

os.environ.setdefault("GEO_ALLOW_MISSING_LLM_KEY", "1")

from evals.content_writer_judge import (
    SAMPLE_CASES,
    judge_article_quality,
)


def test_sample_cases_count():
    """评测样例至少 30 条(spec §7 Sprint 3)。"""
    assert len(SAMPLE_CASES) >= 30


def test_judge_returns_score_0_to_5():
    """judge 返回 0-5 整数分。"""
    case = SAMPLE_CASES[0]
    score = judge_article_quality(
        case["brand"], case["topic"], case["generated_content"],
        llm_client=None,  # 强制走 mock 路径
    )
    assert isinstance(score, int)
    assert 0 <= score <= 5


def test_sample_case_schema():
    """样例必须有 brand / topic / generated_content / expected_keywords 字段。"""
    for case in SAMPLE_CASES:
        assert "brand" in case
        assert "topic" in case
        assert "generated_content" in case
        assert "expected_keywords" in case
