"""验证历史摘要策略（窗口+摘要双层）（P1#12 / Task 13）。

行为契约：
- HistorySummarizer 接受 LLM 客户端 + 窗口大小
- 当 history <= 窗口：跳过摘要，输出与 build_messages 等价
- 当 history > 窗口：摘要旧消息（窗口外），保留窗口内消息原样
- 摘要消息作为 system role 插入，紧跟在主 system prompt 之后
- LLM 摘要失败（transient 异常）→ 用 placeholder 兜底，不阻塞主流程
- 编程错误仍向上抛
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.domain.agent.summarizer import HistorySummarizer
from app.domain.exceptions import _LLM_TRANSIENT_EXCEPTIONS


def _history(n: int) -> list[dict]:
    """生成 n 条 user 消息历史。"""
    return [{"role": "user", "content": f"msg-{i}"} for i in range(n)]


def _history_with_roles(roles: list[str]) -> list[dict]:
    """按给定 roles 列表生成 history。"""
    return [{"role": r, "content": f"content for {r}-{i}"} for i, r in enumerate(roles)]


# ===========================================================================
# 不触发摘要的快路径
# ===========================================================================


@pytest.mark.asyncio
async def test_short_history_skips_summary() -> None:
    """history <= 窗口时，跳过摘要，输出与 build_messages 等价。"""
    mock_llm = AsyncMock()
    summarizer = HistorySummarizer(llm=mock_llm, window_size=10)
    history = _history(5)  # 5 < 10

    out = await summarizer.build_messages_with_summary(
        history=history,
        window_messages=10,
    )

    # LLM 不应被调用
    assert not mock_llm.chat.called, "history ≤ 窗口时不应调 LLM"
    # 首条是 system prompt（与 build_messages 一致）
    assert out[0]["role"] == "system"
    assert "GEO" in out[0]["content"]
    # 应只有 1 条 system（无摘要注入）
    system_count = sum(1 for m in out if m["role"] == "system")
    assert system_count == 1
    # 5 条 user 全部保留
    user_count = sum(1 for m in out if m["role"] == "user")
    assert user_count == 5


# ===========================================================================
# 触发摘要的慢路径
# ===========================================================================


@pytest.mark.asyncio
async def test_long_history_summarizes_older_messages() -> None:
    """history > 窗口时，窗口外消息被 LLM 摘要，窗口内保留原样。"""
    mock_llm = AsyncMock()
    mock_llm.chat_with_tools = AsyncMock(return_value={
        "content": "摘要：用户问了5个问题",
        "tool_calls": None,
        "usage": None,
    })
    summarizer = HistorySummarizer(llm=mock_llm, window_size=3)
    history = _history(8)  # 8 > 3,前 5 条要被摘要

    out = await summarizer.build_messages_with_summary(
        history=history,
        window_messages=3,
    )

    # LLM 应被调 1 次（摘要前 5 条）
    assert mock_llm.chat_with_tools.call_count == 1
    # 第 1 条是主 system prompt
    assert out[0]["role"] == "system"
    assert "GEO" in out[0]["content"]
    # 第 2 条是摘要 system
    assert out[1]["role"] == "system"
    assert "摘要" in out[1]["content"]
    assert "用户问了5个问题" in out[1]["content"]
    # 窗口内 3 条 user 应保留原样
    user_msgs = [m for m in out if m["role"] == "user"]
    assert len(user_msgs) == 3
    assert user_msgs[0]["content"] == "msg-5"  # history[-3][0] == msg-5
    assert user_msgs[1]["content"] == "msg-6"
    assert user_msgs[2]["content"] == "msg-7"


@pytest.mark.asyncio
async def test_summary_inserted_as_second_system_message() -> None:
    """摘要消息必须在主 system prompt 之后、user 消息之前。"""
    mock_llm = AsyncMock()
    mock_llm.chat_with_tools = AsyncMock(return_value={
        "content": "X", "tool_calls": None, "usage": None,
    })
    summarizer = HistorySummarizer(llm=mock_llm, window_size=2)
    history = _history(5)

    out = await summarizer.build_messages_with_summary(history=history, window_messages=2)

    # 前两条都应是 system
    assert out[0]["role"] == "system"
    assert out[1]["role"] == "system"
    assert "历史摘要" in out[1]["content"] or "摘要" in out[1]["content"]


# ===========================================================================
# 失败兜底
# ===========================================================================


@pytest.mark.asyncio
async def test_summarizer_falls_back_on_transient_error() -> None:
    """LLM 摘要抛 transient 异常时，用 placeholder 兜底，不阻塞主流程。"""
    import asyncio
    from openai import APITimeoutError
    mock_llm = AsyncMock()
    mock_llm.chat_with_tools = AsyncMock(side_effect=APITimeoutError("timeout"))
    summarizer = HistorySummarizer(llm=mock_llm, window_size=3)
    history = _history(8)

    out = await summarizer.build_messages_with_summary(history=history, window_messages=3)

    # 不应抛异常
    # 应有 placeholder 摘要
    assert out[1]["role"] == "system"
    assert "摘要失败" in out[1]["content"] or "placeholder" in out[1]["content"].lower() or "[truncated" in out[1]["content"]
    # 窗口内 3 条 user 仍然保留
    user_msgs = [m for m in out if m["role"] == "user"]
    assert len(user_msgs) == 3


@pytest.mark.asyncio
async def test_summarizer_propagates_programming_error() -> None:
    """编程错误（AttributeError）→ 仍然向上抛，不被吞。"""
    mock_llm = AsyncMock()
    mock_llm.chat_with_tools = AsyncMock(side_effect=AttributeError("'NoneType' has no attribute 'x'"))
    summarizer = HistorySummarizer(llm=mock_llm, window_size=3)
    history = _history(8)

    with pytest.raises(AttributeError):
        _ = await summarizer.build_messages_with_summary(history=history, window_messages=3)


# ===========================================================================
# 边界
# ===========================================================================


@pytest.mark.asyncio
async def test_window_size_zero_summarizes_all() -> None:
    """window_messages=0 时，所有消息都被摘要。"""
    mock_llm = AsyncMock()
    mock_llm.chat_with_tools = AsyncMock(return_value={
        "content": "全量摘要", "tool_calls": None, "usage": None,
    })
    summarizer = HistorySummarizer(llm=mock_llm, window_size=0)
    history = _history(3)

    out = await summarizer.build_messages_with_summary(history=history, window_messages=0)

    # LLM 调 1 次,摘要 3 条
    assert mock_llm.chat_with_tools.call_count == 1
    # 窗口内 0 条 user
    user_msgs = [m for m in out if m["role"] == "user"]
    assert len(user_msgs) == 0
    # 摘要 system 存在
    assert out[1]["role"] == "system"
    assert "全量摘要" in out[1]["content"]


@pytest.mark.asyncio
async def test_history_with_assistant_and_tool_messages() -> None:
    """history 含 assistant + tool 消息时，摘要能正确序列化。"""
    mock_llm = AsyncMock()
    mock_llm.chat_with_tools = AsyncMock(return_value={
        "content": "摘要含工具调用", "tool_calls": None, "usage": None,
    })
    summarizer = HistorySummarizer(llm=mock_llm, window_size=2)
    history = [
        {"role": "user", "content": "q1"},
        {
            "role": "assistant", "content": None,
            "tool_calls": [{"id": "tc1", "function": {"name": "search", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "tc1", "content": "result1"},
        {"role": "user", "content": "q2"},
        {"role": "user", "content": "q3"},  # 窗口内
    ]

    out = await summarizer.build_messages_with_summary(history=history, window_messages=2)

    # LLM 应被调
    assert mock_llm.chat_with_tools.call_count == 1
    # 摘要存在
    assert out[1]["role"] == "system"
    assert "摘要含工具调用" in out[1]["content"]