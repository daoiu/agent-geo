"""T1 重构验证:turn_helpers.py 8 个共享纯函数的行为对齐 react_loop 原实现。

零行为变化是本任务的硬约束,以下三个用例覆盖最高频路径:
- ``build_messages``:system 注入 + dangling tool_call 丢弃(配对保证)
- ``_accumulate`` / ``_new_metrics``:metrics 聚合
"""
from __future__ import annotations

from app.domain.agent.turn_helpers import (
    _accumulate,
    _apply_memory_prepend,
    _emit_metrics,
    _get_tiktoken_encoder,
    _new_metrics,
    _orm_to_dict,
    _truncate_by_tokens,
    build_messages,
)


def test_build_messages_injects_system_first():
    """第一条必须是 system,user 原样跟随其后。"""
    out = build_messages([{"role": "user", "content": "你好"}])
    assert out[0]["role"] == "system"
    assert out[1] == {"role": "user", "content": "你好"}


def test_build_messages_drops_dangling_tool_call():
    """assistant 声明 tool_call 但无对应 tool 结果 → 丢弃,避免 provider 400。

    HumanConfirmation / 被中断的流会留下无结果的 tool_call,
    必须丢弃而不是原样透传给 LLM,否则 provider 报
    'tool call result does not follow tool call' 400。
    """
    history = [
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "t1", "function": {"name": "f", "arguments": "{}"}}
            ],
        },
    ]
    out = build_messages(history)
    # 所有 assistant 消息都不应带 tool_calls(dangling 已丢弃)
    assert all("tool_calls" not in m for m in out if m["role"] == "assistant")


def test_accumulate_sums_usage():
    """_accumulate 单次调用把 usage 累加到聚合结构,llm_calls/iterations 各 +1。"""
    agg = _new_metrics()
    _accumulate(agg, {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8})
    assert agg["llm_calls"] == 1
    assert agg["iterations"] == 1
    assert agg["total_tokens"] == 8
    assert agg["usage_seen"] is True