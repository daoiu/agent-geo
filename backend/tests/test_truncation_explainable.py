"""P2#36（Task 44）: 截断决策可解释测试。

目标:
- 截断时输出 metadata(哪些消息被裁/被截断位置/节省 token 数)
- TruncationResult dataclass 含详细字段
- 旧 messages 不丢,只标记 dropped/truncated
"""
from __future__ import annotations

import pytest


def test_truncation_result_dataclass() -> None:
    """TruncationResult 必须含详细字段。"""
    from app.domain.agent.truncation_explainable import TruncationResult

    r = TruncationResult(
        kept_messages=[{"role": "user", "content": "hi"}],
        dropped_messages=[{"role": "user", "content": "old"}],
        truncated_messages=[{"role": "tool", "content": "short"}],
        original_token_count=1000,
        final_token_count=600,
        tokens_saved=400,
        strategy="window+summarize",
        decisions=[
            {"message_id": "m1", "action": "kept", "reason": "within window"},
            {"message_id": "m2", "action": "summarized", "reason": "older than window"},
        ],
    )
    assert r.tokens_saved == 400
    assert r.strategy == "window+summarize"
    assert len(r.decisions) == 2


def test_truncation_within_budget_no_changes() -> None:
    """总 token 在预算内,无截断。"""
    from app.domain.agent.truncation_explainable import TruncationResult, truncate_explainable

    messages = [{"role": "user", "content": "hi"}] * 5
    result = truncate_explainable(
        messages,
        token_budget=10_000,
        token_counter=lambda text: len(text) // 4,  # 简化估算
    )
    assert result.tokens_saved == 0
    assert len(result.kept_messages) == 5
    assert len(result.dropped_messages) == 0


def test_truncation_drops_oldest_first() -> None:
    """超预算时优先 drop 旧消息(FIFO)。"""
    from app.domain.agent.truncation_explainable import truncate_explainable

    messages = [
        {"role": "user", "content": "msg1" * 200},  # 大量
        {"role": "user", "content": "msg2" * 200},  # 大量
        {"role": "user", "content": "msg3 short"},
    ]
    result = truncate_explainable(
        messages,
        token_budget=100,
        token_counter=lambda text: len(text) // 4,
    )
    # 旧消息应被 drop
    assert len(result.dropped_messages) >= 1
    # 最新的应保留
    contents_kept = [m.get("content", "") for m in result.kept_messages]
    assert any("msg3" in c for c in contents_kept)


def test_truncation_marks_truncated_vs_dropped() -> None:
    """截断应区分 truncate(部分裁) 和 drop(整条丢)。"""
    from app.domain.agent.truncation_explainable import truncate_explainable

    # 5 个 tool 结果(1 个 user 在最后),keep_recent=1 → 前 4 个都是旧
    messages = [
        {"role": "tool", "content": "x" * 4000},  # 大
        {"role": "tool", "content": "y" * 4000},  # 大
        {"role": "tool", "content": "z" * 4000},  # 大
        {"role": "tool", "content": "w" * 4000},  # 大
        {"role": "tool", "content": "v" * 100},   # 小,最近的
        {"role": "user", "content": "新问题"},
    ]
    result = truncate_explainable(
        messages,
        token_budget=10_000,
        token_counter=lambda text: len(text) // 4,
        tool_result_token_cap=50,  # 工具结果限制 50 token
        tool_result_keep_recent=1,  # 只保留最近 1 个 tool 不动
    )
    # 前 4 个大 tool 应被 truncated(最近的 1 个不动)
    assert len(result.truncated_messages) >= 1


def test_truncation_records_per_message_decisions() -> None:
    """decisions 列表必须记录每条消息的处理动作。"""
    from app.domain.agent.truncation_explainable import truncate_explainable

    messages = [
        {"role": "user", "content": "old"},
        {"role": "user", "content": "new"},
    ]
    result = truncate_explainable(
        messages,
        token_budget=1,  # 极小预算,触发截断
        token_counter=lambda text: len(text) // 4,
    )
    # 每条消息都应有 decision
    assert len(result.decisions) == 2
    for d in result.decisions:
        assert "action" in d
        assert "reason" in d


def test_truncation_result_to_dict_for_logging() -> None:
    """TruncationResult.to_dict 必须输出可序列化 dict。"""
    import json
    from app.domain.agent.truncation_explainable import TruncationResult

    r = TruncationResult(
        kept_messages=[],
        dropped_messages=[],
        truncated_messages=[],
        original_token_count=100,
        final_token_count=50,
        tokens_saved=50,
        strategy="window",
        decisions=[],
    )
    d = r.to_dict()
    # 必须能 JSON 序列化(用于日志/SSE)
    json.dumps(d, ensure_ascii=False)
    assert d["tokens_saved"] == 50
    assert d["strategy"] == "window"


def test_truncation_includes_strategy_reason() -> None:
    """strategy 字段必须描述使用的策略(window/summarize/drop 等)。"""
    from app.domain.agent.truncation_explainable import truncate_explainable

    messages = [{"role": "user", "content": "x" * 1000}] * 3
    result = truncate_explainable(
        messages,
        token_budget=10,
        token_counter=lambda text: len(text) // 4,
    )
    # strategy 应是非空字符串
    assert result.strategy
    assert isinstance(result.strategy, str)


def test_truncation_tokens_saved_calculation() -> None:
    """tokens_saved = original_token_count - final_token_count。"""
    from app.domain.agent.truncation_explainable import truncate_explainable

    messages = [{"role": "user", "content": "x" * 1000}] * 5
    result = truncate_explainable(
        messages,
        token_budget=50,  # 强截断
        token_counter=lambda text: len(text) // 4,
    )
    expected_saved = result.original_token_count - result.final_token_count
    assert result.tokens_saved == expected_saved
    assert result.tokens_saved > 0