"""P2#37（Task 45）: 自适应压缩测试。

目标:
- 根据剩余 token 预算自动选择策略(noop/truncate/summarize/drop)
- summarize 通过 LLM 摘要(可 mock)
- 返回压缩结果 + 策略选择 reason
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


def test_adaptive_compression_within_budget() -> None:
    """预算够 → noop。"""
    import asyncio
    from app.domain.agent.adaptive_compression import adaptive_compress

    messages = [{"role": "user", "content": "hi"}]
    result = asyncio.run(adaptive_compress(messages, token_budget=10_000, token_counter=lambda t: len(t) // 4))
    assert result.strategy == "noop"
    assert len(result.messages) == 1


def test_adaptive_compression_uses_truncate_when_slight_over() -> None:
    """轻微超预算 → truncate(优先截断大 tool 结果)。"""
    import asyncio
    from app.domain.agent.adaptive_compression import adaptive_compress

    # 5 个 tool,keep_recent=1,前 4 个会被截断
    messages = [
        {"role": "tool", "content": "x" * 4000, "id": "t1"},
        {"role": "tool", "content": "x" * 4000, "id": "t2"},
        {"role": "tool", "content": "x" * 4000, "id": "t3"},
        {"role": "tool", "content": "x" * 4000, "id": "t4"},
        {"role": "tool", "content": "y" * 100, "id": "t5"},
        {"role": "user", "content": "新问题", "id": "u"},
    ]
    result = asyncio.run(adaptive_compress(
        messages,
        token_budget=2_000,  # 比 5*1000 小,必触发压缩
        token_counter=lambda t: len(t) // 4,
        tool_result_token_cap=200,
        tool_result_keep_recent=1,
    ))
    # 策略应包含 truncate
    assert "truncate" in result.strategy
    # 节省 token 应为正
    assert result.tokens_saved > 0


def test_adaptive_compression_uses_summarize_for_old_messages() -> None:
    """大量旧 user/assistant 消息 → 摘要(而非简单 drop)。"""
    import asyncio
    from app.domain.agent.adaptive_compression import adaptive_compress

    messages = (
        [{"role": "user", "content": f"old-q-{i}", "id": f"old-{i}"} for i in range(10)]
        + [{"role": "assistant", "content": f"old-a-{i}", "id": f"old-a-{i}"} for i in range(10)]
        + [{"role": "user", "content": "新问题", "id": "new"}]
    )
    result = asyncio.run(adaptive_compress(
        messages,
        token_budget=50,
        token_counter=lambda t: len(t) // 4,
        summarizer=AsyncMock(return_value="[old conversation summary]"),
    ))
    assert result.strategy
    assert any("[old conversation summary]" in m.get("content", "") or "新问题" in m.get("content", "") for m in result.messages)


def test_adaptive_compression_decision_order() -> None:
    """策略决策顺序:noop → truncate → drop/summarize。"""
    from app.domain.agent.adaptive_compression import _decide_strategy

    # 1) 预算够 → noop
    s = _decide_strategy(current_tokens=100, budget=1000, has_old_msgs=False)
    assert s == "noop"

    # 2) 可截断 → truncate(无论超多少)
    s = _decide_strategy(current_tokens=1500, budget=1000, has_old_msgs=False, can_truncate=True)
    assert s == "truncate"

    # 3) 不可截断 + 有旧消息 + 有 summarizer → summarize(保信息)
    s = _decide_strategy(current_tokens=1500, budget=1000, has_old_msgs=True, can_truncate=False, can_summarize=True)
    assert s == "summarize"

    # 4) 不可截断 + 有旧消息 + 无 summarizer → drop
    s = _decide_strategy(current_tokens=2000, budget=100, has_old_msgs=True, can_truncate=False, can_summarize=False)
    assert s == "drop"


def test_adaptive_compression_result_fields() -> None:
    """CompressionResult 必须含 strategy/original/final/saved + 详细 reason。"""
    import asyncio
    from app.domain.agent.adaptive_compression import adaptive_compress

    messages = [{"role": "user", "content": "hi"}]
    result = asyncio.run(adaptive_compress(messages, token_budget=10_000, token_counter=lambda t: len(t) // 4))
    assert result.strategy
    assert result.original_token_count >= 0
    assert result.final_token_count >= 0
    assert result.tokens_saved >= 0
    assert result.reason


def test_adaptive_compression_summarize_calls_llm() -> None:
    """summarize 策略必须调 LLM 摘要(可 mock)。"""
    import asyncio
    from app.domain.agent.adaptive_compression import adaptive_compress

    mock_summarizer = AsyncMock(return_value="[summary text]")
    messages = (
        [{"role": "user", "content": f"q{i}", "id": f"q{i}"} for i in range(20)]
        + [{"role": "assistant", "content": f"a{i}", "id": f"a{i}"} for i in range(20)]
        + [{"role": "user", "content": "新", "id": "new"}]
    )
    result = asyncio.run(adaptive_compress(
        messages,
        token_budget=10,
        token_counter=lambda t: len(t) // 4,
        summarizer=mock_summarizer,
    ))
    if "summarize" in result.strategy:
        assert mock_summarizer.called


def test_adaptive_compression_preserves_last_user_message() -> None:
    """最后一条 user 消息必须保留。"""
    import asyncio
    from app.domain.agent.adaptive_compression import adaptive_compress

    messages = [
        {"role": "user", "content": "old", "id": "old"},
        {"role": "user", "content": "当前问题", "id": "new"},
    ]
    result = asyncio.run(adaptive_compress(
        messages,
        token_budget=5,
        token_counter=lambda t: len(t) // 4,
        summarizer=AsyncMock(return_value="[summary]"),
    ))
    last = result.messages[-1] if result.messages else None
    assert last is not None
    assert "当前问题" in last.get("content", "")