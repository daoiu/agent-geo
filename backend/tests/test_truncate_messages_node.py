"""Task 9 TruncateMessagesNode RED tests — 4 策略自适应压缩 + token 截断回流 TruncationResult。"""
import pytest

from app.domain.agent.langgraph_nodes.truncate_messages import truncate_messages_node


@pytest.mark.asyncio
async def test_truncate_messages_picks_strategy_and_updates_state():
    state = {
        "messages": [{"role": "system", "content": "sys"}]
        + [{"role": "user", "content": f"msg-{i}" * 100} for i in range(20)],
        "session_id": "s1",
        "memory_chunk": None,
        "truncation_result": None,
        "tool_call_log": [],
    }
    # mock LangChain-style messages since adaptive_compress needs dicts
    out = await truncate_messages_node(state, runtime=None)
    assert "messages" in out
    assert "truncation_result" in out
    assert out["truncation_result"]["strategy"] in {"noop", "truncate", "drop", "summarize"}


@pytest.mark.asyncio
async def test_truncate_messages_noop_when_under_budget():
    state = {
        "messages": [{"role": "user", "content": "hi"}],
        "session_id": "s1",
        "memory_chunk": None,
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = await truncate_messages_node(state, runtime=None)
    assert out["truncation_result"]["strategy"] == "noop"
    assert out["truncation_result"]["tokens_saved"] == 0
