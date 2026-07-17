"""Tests for per-turn metrics logging in _drive_react_loop (Phase 1)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.agent_repo import AgentRepository


def _resp(content, tool_calls, usage):
    return {"content": content, "tool_calls": tool_calls, "usage": usage}


def _emit_calls(mock_emit):
    """T1 重构后,_emit_metrics 现位于 turn_helpers,react_loop 通过模块顶部
    import 拿到同一函数对象。测试 mock 该函数即可拦截调用并拿到入参 kwargs。
    """
    return mock_emit.call_args_list


@pytest.mark.asyncio
async def test_metrics_logged_on_turn_complete(db_session):
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    # T1 重构:_emit_metrics 现位于 turn_helpers.py,但 react_loop 通过
    # ``from app.domain.agent.turn_helpers import _emit_metrics`` 在自己
    # 命名空间里保存了引用。patch 必须走 react_loop 命名空间路径才能拦截。
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM, \
         patch("app.domain.agent.react_loop._emit_metrics") as mock_emit:
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value=_resp(
            "好的", None,
            {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        ))
        events = [e async for e in rl.run_agent_turn(session.id, "hi")]

    assert events[-1]["event"] == "turn_complete"
    calls = _emit_calls(mock_emit)
    assert len(calls) == 1
    # 位置参数顺序:(agg, session_id, device_id, outcome, turn_duration_ms, cost_usd)
    args = calls[0].args
    agg = args[0]
    assert args[2] is None or args[2] == session.id  # device_id
    assert args[3] == "turn_complete"
    assert agg["llm_calls"] == 1
    assert agg["total_tokens"] == 120


@pytest.mark.asyncio
async def test_metrics_token_none_when_usage_absent(db_session):
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM, \
         patch("app.domain.agent.react_loop._emit_metrics") as mock_emit:
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value=_resp(
            "好的", None, None))
        _ = [e async for e in rl.run_agent_turn(session.id, "hi")]

    agg = _emit_calls(mock_emit)[0].args[0]
    assert agg["total_tokens"] == 0
    assert agg["prompt_tokens"] == 0
    assert agg["usage_seen"] is False


@pytest.mark.asyncio
async def test_metrics_logged_on_max_iterations(db_session):
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    tool_resp = _resp(None, [{
        "id": "tc",
        "function": {
            "name": "diagnose_brand",
            "arguments": '{"brand_name":"X","industry":"Y","official_url":"https://x.com"}',
        },
    }], {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM, \
         patch("app.domain.agent.react_loop._emit_metrics") as mock_emit, \
         patch("app.domain.agent.tool_executor.ToolExecutor.execute",
               new=AsyncMock(return_value={"x": 1})):
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value=tool_resp)
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    assert events[-1]["event"] == "max_iterations_reached"
    args = _emit_calls(mock_emit)[0].args
    agg = args[0]
    assert args[3] == "max_iterations_reached"
    assert agg["iterations"] == 7
    assert agg["tool_calls"] == 7
    assert agg["total_tokens"] == 105  # 7 × 15
