"""验证 build_messages 的 token 级截断（P1#11 / Task 12）。

行为契约：
- 引入 tiktoken 做 token 级截断（替代字符截断，精度更高）
- build_messages 接受 ``token_budget_per_tool_result`` 参数
- 当设置 token budget 时，超长 tool result 按 token 数截断（不是字符数）
- 当 token budget 为 None 时，回退到原有的字符级截断（向后兼容）
- 最近 ``tool_result_keep_recent`` 个 tool 结果仍然保留完整内容
- 添加 truncated 标记，便于 LLM 理解
"""
from __future__ import annotations

import tiktoken

from app.domain.agent.turn_helpers import build_messages


def _make_long_tool_result(char_count: int = 5000) -> dict:
    """构造一个超长 tool 结果消息。"""
    long_content = "x" * char_count  # 纯 ASCII,token ≈ char/4
    return {
        "role": "tool",
        "tool_call_id": "tc1",
        "content": long_content,
    }


def _enc() -> tiktoken.Encoding:
    """cl100k_base 编码器（gpt-4 / deepseek-chat 等都用这个或类似）。"""
    return tiktoken.get_encoding("cl100k_base")


def test_token_budget_truncates_long_tool_result() -> None:
    """token_budget_per_tool_result 设为 50 时，tool result 应被截断到 ~50 token。"""
    msg = _make_long_tool_result(5000)  # ~1250 token
    history = [
        {"role": "user", "content": "查"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "tc1", "function": {"name": "search_knowledge", "arguments": "{}"}}
            ],
        },
        msg,
    ]
    out = build_messages(
        history=history,
        token_budget_per_tool_result=50,
        tool_result_keep_recent=0,
    )
    tool_msgs = [m for m in out if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    truncated_content = tool_msgs[0]["content"]

    # 实际 token 数 <= 50 + 几个 truncated marker token
    enc = _enc()
    token_count = len(enc.encode(truncated_content))
    assert token_count <= 60, (
        f"截断后 token 数应 <= 60（50 + truncated 标记），实际 {token_count}"
    )
    # 必须含 truncated 标记
    assert "truncated" in truncated_content.lower() or "…" in truncated_content


def test_token_budget_none_falls_back_to_char_truncation() -> None:
    """token_budget=None 时回退到 tool_result_max_chars（向后兼容）。"""
    history = [
        {"role": "user", "content": "查"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "tc1", "function": {"name": "search_knowledge", "arguments": "{}"}}
            ],
        },
        _make_long_tool_result(5000),
    ]
    out = build_messages(
        history=history,
        tool_result_max_chars=100,  # 字符上限 100
        tool_result_keep_recent=0,
    )
    tool_msgs = [m for m in out if m.get("role") == "tool"]
    content = tool_msgs[0]["content"]
    # 字符级截断：约 100 字符 + truncated 标记
    assert len(content) <= 120
    assert "truncated" in content.lower() or "…" in content


def test_short_tool_result_not_truncated_with_token_budget() -> None:
    """短的 tool result 即使设了 token budget，也不应被截断。"""
    short_msg = {
        "role": "tool",
        "tool_call_id": "tc1",
        "content": "ok",
    }
    history = [
        {"role": "user", "content": "查"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "tc1", "function": {"name": "search_knowledge", "arguments": "{}"}}
            ],
        },
        short_msg,
    ]
    out = build_messages(
        history=history,
        token_budget_per_tool_result=50,
        tool_result_keep_recent=0,
    )
    tool_msgs = [m for m in out if m.get("role") == "tool"]
    assert tool_msgs[0]["content"] == "ok"


def test_recent_tool_results_kept_full_with_token_budget() -> None:
    """最近 keep_recent 个 tool 结果即使超长也不截断。"""
    long_msg = _make_long_tool_result(5000)
    history = [
        {"role": "user", "content": "查"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "tc1", "function": {"name": "search_knowledge", "arguments": "{}"}}
            ],
        },
        long_msg,
    ]
    out = build_messages(
        history=history,
        token_budget_per_tool_result=10,  # 很紧的预算
        tool_result_keep_recent=1,  # 但最近 1 个保留全量
    )
    tool_msgs = [m for m in out if m.get("role") == "tool"]
    assert tool_msgs[0]["content"] == "x" * 5000, (
        "最近 keep_recent=1 个 tool 结果应保留全量，未被截断"
    )


def test_chinese_content_token_count_accurate() -> None:
    """中文内容：token 级截断应基于实际 token 数（不是字符数）。"""
    # 中文每字符 ≈ 1.5 token (cl100k_base)
    # 200 个汉字 ≈ 300 token
    chinese_content = "小米" * 200  # 400 字符
    msg = {"role": "tool", "tool_call_id": "tc1", "content": chinese_content}
    history = [
        {"role": "user", "content": "查"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "tc1", "function": {"name": "search_knowledge", "arguments": "{}"}}
            ],
        },
        msg,
    ]
    enc = _enc()
    full_token_count = len(enc.encode(chinese_content))
    # token budget 设为 50，应被截断
    out = build_messages(
        history=history,
        token_budget_per_tool_result=50,
        tool_result_keep_recent=0,
    )
    tool_msgs = [m for m in out if m.get("role") == "tool"]
    truncated = tool_msgs[0]["content"]
    truncated_token_count = len(enc.encode(truncated))
    # 中文不应被过度截断（基于 token 不是字符）
    assert truncated_token_count <= 70, (
        f"中文 token 截断应保留 <= 70 token，实际 {truncated_token_count}"
    )
    # 完整内容 token 数应明显大于截断后
    assert full_token_count > truncated_token_count, (
        f"完整内容 token {full_token_count} 应大于截断后 {truncated_token_count}"
    )