"""Tests for ReAct loop (v0.4)."""
from __future__ import annotations

import json

import pytest

from app.domain.agent.react_loop import build_messages


def test_build_messages_starts_with_system_prompt() -> None:
    """第一条是 system prompt。"""
    messages = build_messages(history=[])
    assert messages[0]["role"] == "system"
    assert "GEO" in messages[0]["content"]


def test_build_messages_passes_through_user() -> None:
    """user 消息直接传递。"""
    history = [{"role": "user", "content": "诊断小米"}]
    messages = build_messages(history=history)
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "诊断小米"


def test_build_messages_passes_through_assistant_text() -> None:
    """assistant 纯文本消息传递。"""
    history = [
        {"role": "user", "content": "诊断"},
        {"role": "assistant", "content": "好的，让我先看分数。"},
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    assert asst["content"] == "好的，让我先看分数。"
    assert "tool_calls" not in asst


def test_build_messages_converts_tool_role_messages() -> None:
    """'tool' role 消息 + tool_call_id 被正确转换（OpenAI 协议要求）。"""
    history = [
        {"role": "user", "content": "诊断"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "tc1", "function": {"name": "diagnose_brand", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "tc1", "content": "result"},
    ]
    messages = build_messages(history=history)
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "tc1"
    assert tool_msgs[0]["content"] == "result"


def test_build_messages_serializes_tool_call_arguments_from_json_string() -> None:
    """DB 存储的 tool_calls.arguments 是 JSON 字符串；LLM 需要对象。"""
    history = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "tc1",
                    "function": {
                        "name": "diagnose_brand",
                        "arguments": '{"brand_name": "小米"}',
                    },
                }
            ],
        },
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    args = asst["tool_calls"][0]["function"]["arguments"]
    assert isinstance(args, dict)
    assert args["brand_name"] == "小米"


def test_build_messages_passes_dict_arguments_unchanged() -> None:
    """如果 arguments 已经是 dict，直接用。"""
    history = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "tc1",
                    "function": {
                        "name": "diagnose_brand",
                        "arguments": {"brand_name": "小米"},
                    },
                }
            ],
        },
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    args = asst["tool_calls"][0]["function"]["arguments"]
    assert args == {"brand_name": "小米"}


def test_build_messages_skips_unknown_role() -> None:
    """未知 role 消息被忽略（防御性）。"""
    history = [
        {"role": "user", "content": "hi"},
        {"role": "system", "content": "old system msg"},
    ]
    messages = build_messages(history=history)
    # 系统 prompt 在前；旧的 system 消息被忽略
    assert len(messages) == 2  # system + user
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"