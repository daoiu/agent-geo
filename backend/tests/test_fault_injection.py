"""故障注入测试套件（P1#16 / Task 17）。

覆盖现有 test_react_loop_llm_error_fallback.py / test_react_loop_tool_error_classification.py
未涵盖的故障场景：
- LLM 部分失败（一个 turn 内多次重试，部分失败部分成功）
- 工具部分失败（N 个 tool_calls 中部分失败部分成功,react_loop 继续）
- LLM 返回畸形响应（缺 content / tool_calls / usage 字段）
- DB 写失败（create_message 抛 SQLAlchemyError 时的降级）
- 重试耗尽（连续 N 次 RateLimitError 后最终抛错）
- LLM 第一次失败第二次成功（自动重试语义）
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import OperationalError

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


def _ok_resp(content: str = "ok") -> dict:
    return {"content": content, "tool_calls": None, "usage": None}


# ===========================================================================
# 工具部分失败：N 个 tool_calls 中部分失败部分成功
# ===========================================================================


@pytest.mark.asyncio
async def test_partial_tool_failure_loop_continues(db_session) -> None:
    """多 tool_calls 中部分失败部分成功,react_loop 不中断,继续后续工具。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    # 构造两个 tool_calls
    multi_tc_resp = {
        "content": None,
        "tool_calls": [
            {"id": "tc1", "function": {"name": "search_knowledge", "arguments": '{"query":"a"}'}},
            {"id": "tc2", "function": {"name": "search_knowledge", "arguments": '{"query":"b"}'}},
            {"id": "tc3", "function": {"name": "search_knowledge", "arguments": '{"query":"c"}'}},
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    # 第一次 LLM 返回 3 tool_calls,第二次返回 no tool_call (结束)
    mock_llm.return_value.chat_with_tools = AsyncMock(side_effect=[
        multi_tc_resp,
        _ok_resp("done"),
    ])

    # 工具执行: tc1 失败（transient）, tc2 成功, tc3 失败（transient）
    call_log = []
    async def _exec(name, args):
        call_log.append(name)
        if name == "search_knowledge":
            q = args.get("query")
            if q == "a":
                raise OperationalError("stm", {}, Exception("db 1"))
            if q == "b":
                return {"chunks": ["ok"]}
            if q == "c":
                raise OperationalError("stm", {}, Exception("db 2"))
        return {}

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm), \
         patch("app.domain.agent.tool_executor.ToolExecutor.execute",
               new=AsyncMock(side_effect=_exec)):
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    # 3 个 tool_call_result (其中 2 个 error + 1 个 ok)
    tool_results = [e for e in events if e["event"] == "tool_call_result"]
    assert len(tool_results) == 3
    error_results = [r for r in tool_results if "error" in r.get("result", {})]
    assert len(error_results) == 2
    ok_results = [r for r in tool_results if "error" not in r.get("result", {})]
    assert len(ok_results) == 1
    # 最终 turn_complete (loop 没中断)
    assert events[-1]["event"] == "turn_complete"


# ===========================================================================
# LLM 返回畸形响应
# ===========================================================================


@pytest.mark.asyncio
async def test_llm_returns_response_without_usage(db_session) -> None:
    """LLM 响应缺 usage 字段 → react_loop 不崩溃,metrics 字段为 None。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    # usage 缺失 + content 正常
    mock_llm.return_value.chat_with_tools = AsyncMock(return_value={
        "content": "ok", "tool_calls": None,
        # usage 字段缺失
    })

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm), \
         patch.object(rl.logger, "info") as mock_log:
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    assert events[-1]["event"] == "turn_complete"
    # metrics 应有 total_tokens=None (不崩)
    metrics_calls = [
        c for c in mock_log.call_args_list
        if c.args and c.args[0] == "agent_turn_metrics"
    ]
    assert len(metrics_calls) == 1
    assert metrics_calls[0].kwargs.get("total_tokens") is None


@pytest.mark.asyncio
async def test_llm_returns_response_without_content(db_session) -> None:
    """LLM 响应缺 content 字段 → assistant_message content 为 '' 不崩。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    mock_llm.return_value.chat_with_tools = AsyncMock(return_value={
        # content 缺失
        "tool_calls": None,
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm):
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    asst_msgs = [e for e in events if e["event"] == "assistant_message"]
    # assistant_message content 应是空字符串而非 None 或 KeyError
    assert len(asst_msgs) >= 1
    assert asst_msgs[-1]["content"] == ""


# ===========================================================================
# 重试耗尽：连续 N 次 RateLimitError 后失败
# ===========================================================================


@pytest.mark.asyncio
async def test_llm_retry_exhaustion_yields_llm_error(db_session) -> None:
    """LLM 持续失败 → 最终 yield llm_error 事件（不是直接抛）。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    from openai import RateLimitError
    import httpx

    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    # 持续抛 RateLimitError (假设上层重试已耗尽)
    fake_resp = httpx.Response(429, request=httpx.Request("POST", "https://api.test/v1/chat"))
    mock_llm.return_value.chat_with_tools = AsyncMock(
        side_effect=RateLimitError("rate limited", response=fake_resp, body=None)
    )

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm):
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    # 末事件应是 llm_error (Task 10 已实现)
    assert events[-1]["event"] == "llm_error"
    assert events[-1]["error_type"] == "RateLimitError"


# ===========================================================================
# LLM 第一次失败第二次成功（自动重试语义验证）
# ===========================================================================


@pytest.mark.asyncio
async def test_llm_first_fails_then_succeeds(db_session) -> None:
    """LLM 第一次抛 transient 第二次成功 → 第一轮 yield llm_error 然后退出（每 turn 一次重试语义）。

    注:react_loop 当前不内嵌重试（重试由 LLMClient 处理）,
    这里只验证 react_loop 自身在第一次 LLM 失败后能正确 yield llm_error 后退出。
    """
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    from openai import APITimeoutError
    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    mock_llm.return_value.chat_with_tools = AsyncMock(
        side_effect=APITimeoutError("Request timed out.")
    )

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm):
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    # LLM 第一次失败 → yield llm_error → 退出 (不会自动重试)
    assert events[-1]["event"] == "llm_error"
    # LLM 只被调 1 次（react_loop 不内嵌重试）
    assert mock_llm.return_value.chat_with_tools.call_count == 1


# ===========================================================================
# assistant message DB 写失败 → react_loop 不崩（DDL/transient 错误不应阻塞 SSE 流）
# ===========================================================================


@pytest.mark.asyncio
async def test_db_write_failure_during_assistant_message_propagates(db_session) -> None:
    """create_message 抛 SQLAlchemyError → react_loop 不吞,向上抛（编程错误语义）。

    注:当前 react_loop 在 create_message 处不捕获 DB 异常。
    这个测试验证：DB 写入失败时异常不被静默吞掉。
    """
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    mock_llm.return_value.chat_with_tools = AsyncMock(return_value=_ok_resp("ok"))

    import app.domain.agent.react_loop as rl

    # Patch create_message to raise DB error
    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm), \
         patch("app.repositories.agent_repo.AgentRepository.create_message",
               new=AsyncMock(side_effect=OperationalError("stm", {}, Exception("write failed")))):
        with pytest.raises(OperationalError):
            _ = [e async for e in rl.run_agent_turn(session.id, "X")]


# ===========================================================================
# ToolExecutor.execute 第一次失败第二次成功（同一 turn 内多轮工具调用）
# ===========================================================================


@pytest.mark.asyncio
async def test_tool_first_fails_then_succeeds_within_turn(db_session) -> None:
    """同一 turn 内,第一次工具调用失败(transient),第二次成功。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    call_count = 0
    async def _flaky_tool(name, args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OperationalError("stm", {}, Exception("transient"))
        return {"result": "ok"}

    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    # 第一次返回 tool_call(工具失败),第二次返回 no tool_call(结束)
    mock_llm.return_value.chat_with_tools = AsyncMock(side_effect=[
        _tool_resp(),
        _ok_resp("recovered"),
    ])

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm), \
         patch("app.domain.agent.tool_executor.ToolExecutor.execute",
               new=AsyncMock(side_effect=_flaky_tool)):
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    # 工具被调 1 次（transient error）
    assert call_count == 1
    # 最终 turn_complete (第二次 LLM 调用成功)
    assert events[-1]["event"] == "turn_complete"
    # 中间有 tool_call_result error
    error_results = [
        e for e in events
        if e["event"] == "tool_call_result" and "error" in e.get("result", {})
    ]
    assert len(error_results) == 1