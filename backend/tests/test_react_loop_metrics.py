"""Tests for per-turn metrics logging in _drive_react_loop (Phase 1)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.agent_repo import AgentRepository


def _resp(content, tool_calls, usage):
    return {"content": content, "tool_calls": tool_calls, "usage": usage}


def _metrics_calls(mock_log):
    return [
        c for c in mock_log.call_args_list
        if c.args and c.args[0] == "agent_turn_metrics"
    ]


@pytest.mark.asyncio
async def test_metrics_logged_on_turn_complete(db_session):
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM, \
         patch.object(rl.logger, "info") as mock_log:
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value=_resp(
            "好的", None,
            {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        ))
        events = [e async for e in rl.run_agent_turn(session.id, "hi")]

    assert events[-1]["event"] == "turn_complete"
    calls = _metrics_calls(mock_log)
    assert len(calls) == 1
    kw = calls[0].kwargs
    assert kw["outcome"] == "turn_complete"
    assert kw["llm_calls"] == 1
    assert kw["total_tokens"] == 120


@pytest.mark.asyncio
async def test_metrics_token_none_when_usage_absent(db_session):
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM, \
         patch.object(rl.logger, "info") as mock_log:
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value=_resp(
            "好的", None, None))
        _ = [e async for e in rl.run_agent_turn(session.id, "hi")]

    kw = _metrics_calls(mock_log)[0].kwargs
    assert kw["total_tokens"] is None
    assert kw["prompt_tokens"] is None


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
         patch.object(rl.logger, "info") as mock_log, \
         patch("app.domain.agent.tool_executor.ToolExecutor.execute",
               new=AsyncMock(return_value={"x": 1})):
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value=tool_resp)
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    assert events[-1]["event"] == "max_iterations_reached"
    kw = _metrics_calls(mock_log)[0].kwargs
    assert kw["outcome"] == "max_iterations_reached"
    assert kw["iterations"] == 7
    assert kw["tool_calls"] == 7
    assert kw["total_tokens"] == 105  # 7 × 15
