"""验证 LLM 调用失败的显式降级（P1#9 / Task 10）。

行为契约：
- chat_with_tools 抛 transient 异常（APITimeoutError / RateLimitError / APIError /
  asyncio.TimeoutError / httpx.HTTPError）→ react_loop 捕获并 yield SSE 事件
  ``{"event": "llm_error", "error_type": ..., "message": ...}``，**不**抛异常。
- 编程错误（AttributeError / ValueError）→ 仍然向上抛（不被吞掉）。
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import APIError, APITimeoutError, RateLimitError

from app.repositories.agent_repo import AgentRepository


def _llm_setup(MockLLM, side_effect):
    """让 chat_with_tools 抛指定异常。"""
    MockLLM.return_value.chat_with_tools = AsyncMock(side_effect=side_effect)


@pytest.mark.asyncio
async def test_react_loop_yields_llm_error_event_on_timeout(db_session) -> None:
    """APITimeoutError → 应 yield llm_error 事件，不抛异常。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
        _llm_setup(MockLLM, APITimeoutError("Request timed out."))
        events = [e async for e in rl.run_agent_turn(session.id, "hi")]

    # 末事件应是 llm_error，不是 turn_complete 也不是 max_iterations_reached
    last = events[-1]
    assert last["event"] == "llm_error", f"应 yield llm_error，实际 {last}"
    assert last["error_type"] == "APITimeoutError"
    assert "timed out" in last["message"].lower()


@pytest.mark.asyncio
async def test_react_loop_yields_llm_error_on_rate_limit(db_session) -> None:
    """RateLimitError → 应 yield llm_error 事件。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    fake_response = httpx.Response(429, request=httpx.Request("POST", "https://api.test/v1/chat"))
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
        _llm_setup(MockLLM, RateLimitError("rate limited", response=fake_response, body=None))
        events = [e async for e in rl.run_agent_turn(session.id, "hi")]

    assert events[-1]["event"] == "llm_error"
    assert events[-1]["error_type"] == "RateLimitError"


@pytest.mark.asyncio
async def test_react_loop_yields_llm_error_on_api_error(db_session) -> None:
    """APIError → 应 yield llm_error 事件。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    # APIError 需要 request/response 参数；构造 mock request/response
    fake_request = httpx.Request("POST", "https://api.test/v1/chat")
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
        _llm_setup(MockLLM, APIError("server error", request=fake_request, body=None))
        events = [e async for e in rl.run_agent_turn(session.id, "hi")]

    assert events[-1]["event"] == "llm_error"
    assert events[-1]["error_type"] == "APIError"


@pytest.mark.asyncio
async def test_react_loop_yields_llm_error_on_asyncio_timeout(db_session) -> None:
    """asyncio.TimeoutError → 应 yield llm_error 事件。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
        _llm_setup(MockLLM, asyncio.TimeoutError())
        events = [e async for e in rl.run_agent_turn(session.id, "hi")]

    assert events[-1]["event"] == "llm_error"
    assert events[-1]["error_type"] == "TimeoutError"


@pytest.mark.asyncio
async def test_react_loop_propagates_programming_error(db_session) -> None:
    """编程错误（AttributeError）→ 应向上抛，不被吞掉。"""
    import asyncio
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
        _llm_setup(MockLLM, AttributeError("'NoneType' has no attribute 'x'"))
        with pytest.raises(AttributeError):
            _ = [e async for e in rl.run_agent_turn(session.id, "hi")]


@pytest.mark.asyncio
async def test_react_loop_yields_llm_error_event_then_exits(db_session) -> None:
    """LLM 错误后，react_loop 应 yield llm_error 后退出（不再继续迭代）。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    call_count = 0
    async def _boom(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise APITimeoutError("first call timeout")

    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
        MockLLM.return_value.chat_with_tools = AsyncMock(side_effect=_boom)
        events = [e async for e in rl.run_agent_turn(session.id, "hi")]

    # 应只调 LLM 1 次（错误后立即退出，不重试不继续迭代）
    assert call_count == 1
    # 末事件是 llm_error
    assert events[-1]["event"] == "llm_error"
    # 不应有 max_iterations_reached 或 turn_complete 在 llm_error 之前
    event_types = [e["event"] for e in events]
    assert "max_iterations_reached" not in event_types
    assert "turn_complete" not in event_types