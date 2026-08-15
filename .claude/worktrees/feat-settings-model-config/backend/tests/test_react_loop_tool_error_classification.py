"""验证 react_loop 工具失败路径的 transient/programming 区分（P1#15 / Task 16）。

行为契约：
- 工具执行抛 transient 异常（SQLAlchemy OperationalError / asyncio.TimeoutError /
  httpx.HTTPError）→ react_loop 捕获,转换为 tool_call_result 错误事件,
  LLM 看到错误可决定下一步(继续 / 重试 / 改方案)
- 工具执行抛 programming 异常（ValueError / AttributeError / KeyError / TypeError）→ 向上抛
- HumanConfirmationRequired 仍然优先捕获并 yield human_confirmation_required 事件
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.domain.exceptions import HumanConfirmationRequired
from app.repositories.agent_repo import AgentRepository


def _tool_resp(tc_id: str = "tc1") -> dict:
    return {
        "content": None,
        "tool_calls": [{
            "id": tc_id,
            "function": {
                "name": "search_knowledge",
                "arguments": '{"query":"test"}',
            },
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _patch_llm_and_tool(MockLLM, exc):
    """返回两个 patch context manager。"""
    return (
        patch("app.domain.agent.react_loop.LLMClient", new=MockLLM),
        patch(
            "app.domain.agent.tool_executor.ToolExecutor.execute",
            new=AsyncMock(side_effect=exc),
        ),
    )


def _mock_llm_class():
    """构造 mock LLMClient 类(替换 react_loop.LLMClient)。"""
    from unittest.mock import MagicMock
    mock_cls = MagicMock()
    mock_cls.return_value.chat_with_tools = AsyncMock(return_value=_tool_resp())
    return mock_cls


# ===========================================================================
# transient 异常 → 捕获并降级为 tool_call_result error
# ===========================================================================


@pytest.mark.asyncio
async def test_react_loop_catches_db_operational_error(db_session) -> None:
    """工具抛 SQLAlchemy OperationalError → react_loop 捕获,返回 error tool_call_result。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    mock_llm = _mock_llm_class()
    p_llm, p_tool = _patch_llm_and_tool(
        mock_llm, OperationalError("statement", {}, Exception("db lost"))
    )

    import app.domain.agent.react_loop as rl
    with p_llm, p_tool:
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    tool_results = [e for e in events if e["event"] == "tool_call_result"]
    assert len(tool_results) >= 1
    assert "error" in tool_results[0]["result"]
    assert "OperationalError" in tool_results[0]["result"]["error"]


@pytest.mark.asyncio
async def test_react_loop_catches_asyncio_timeout(db_session) -> None:
    """工具抛 asyncio.TimeoutError → react_loop 捕获。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    mock_llm = _mock_llm_class()
    p_llm, p_tool = _patch_llm_and_tool(mock_llm, asyncio.TimeoutError())

    import app.domain.agent.react_loop as rl
    with p_llm, p_tool:
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    tool_results = [e for e in events if e["event"] == "tool_call_result"]
    assert len(tool_results) >= 1
    assert "TimeoutError" in tool_results[0]["result"]["error"]


@pytest.mark.asyncio
async def test_react_loop_catches_httpx_error(db_session) -> None:
    """工具抛 httpx.HTTPError → react_loop 捕获。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    mock_llm = _mock_llm_class()
    p_llm, p_tool = _patch_llm_and_tool(mock_llm, httpx.ConnectError("network"))

    import app.domain.agent.react_loop as rl
    with p_llm, p_tool:
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    tool_results = [e for e in events if e["event"] == "tool_call_result"]
    assert len(tool_results) >= 1
    assert "ConnectError" in tool_results[0]["result"]["error"]


# ===========================================================================
# programming 异常 → 向上抛，不被吞
# ===========================================================================


@pytest.mark.asyncio
async def test_react_loop_propagates_value_error(db_session) -> None:
    """工具抛 ValueError → 向上抛(编程错误,不应被吞)。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    mock_llm = _mock_llm_class()
    p_llm, p_tool = _patch_llm_and_tool(mock_llm, ValueError("bad arg"))

    import app.domain.agent.react_loop as rl
    with p_llm, p_tool:
        with pytest.raises(ValueError, match="bad arg"):
            _ = [e async for e in rl.run_agent_turn(session.id, "X")]


@pytest.mark.asyncio
async def test_react_loop_propagates_attribute_error(db_session) -> None:
    """工具抛 AttributeError → 向上抛。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    mock_llm = _mock_llm_class()
    p_llm, p_tool = _patch_llm_and_tool(
        mock_llm, AttributeError("'NoneType' has no attribute 'x'")
    )

    import app.domain.agent.react_loop as rl
    with p_llm, p_tool:
        with pytest.raises(AttributeError):
            _ = [e async for e in rl.run_agent_turn(session.id, "X")]


@pytest.mark.asyncio
async def test_react_loop_propagates_type_error(db_session) -> None:
    """工具抛 TypeError → 向上抛。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    mock_llm = _mock_llm_class()
    p_llm, p_tool = _patch_llm_and_tool(mock_llm, TypeError("expected str, got int"))

    import app.domain.agent.react_loop as rl
    with p_llm, p_tool:
        with pytest.raises(TypeError):
            _ = [e async for e in rl.run_agent_turn(session.id, "X")]


# ===========================================================================
# HumanConfirmationRequired 仍然走确认路径
# ===========================================================================


@pytest.mark.asyncio
async def test_human_confirmation_required_still_yields_event(db_session) -> None:
    """HumanConfirmationRequired 仍然 yield human_confirmation_required,不归类为 error。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    mock_llm = _mock_llm_class()
    p_llm, p_tool = _patch_llm_and_tool(
        mock_llm,
        HumanConfirmationRequired(
            message_id="msg-x", tool_name="search_knowledge", arguments={}
        ),
    )

    import app.domain.agent.react_loop as rl
    with p_llm, p_tool:
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    confirm_events = [e for e in events if e["event"] == "human_confirmation_required"]
    assert len(confirm_events) == 1
    error_results = [
        e for e in events if e["event"] == "tool_call_result" and "error" in e.get("result", {})
    ]
    assert len(error_results) == 0


# ===========================================================================
# error 后 LLM 继续（不被中断）
# ===========================================================================


@pytest.mark.asyncio
async def test_react_loop_continues_after_transient_error(db_session) -> None:
    """transient error 后,LLM 继续下次迭代(不被中断 SSE 流)。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    call_count = 0

    async def _llm_then_end(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _tool_resp()
        return {"content": "done", "tool_calls": None, "usage": None}

    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    mock_llm.return_value.chat_with_tools = AsyncMock(side_effect=_llm_then_end)

    p_llm = patch("app.domain.agent.react_loop.LLMClient", new=mock_llm)
    p_tool = patch(
        "app.domain.agent.tool_executor.ToolExecutor.execute",
        new=AsyncMock(side_effect=OperationalError("x", {}, Exception("y"))),
    )

    import app.domain.agent.react_loop as rl
    with p_llm, p_tool:
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    assert events[-1]["event"] == "turn_complete"
    error_results = [
        e for e in events if e["event"] == "tool_call_result" and "error" in e.get("result", {})
    ]
    assert len(error_results) >= 1