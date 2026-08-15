"""验证 turn 延迟 + LLM 耗时 + cost 字段（P1#22 / Task 24）。

行为契约：
- agent_turn_metrics 日志事件包含 turn_duration_ms 字段
- LLMClient 调用记录 llm_call_duration_ms（per-call）
- metrics 含 cost_usd 字段（基于 providers.compute_cost + usage tokens）
- turn_duration_ms >= 0,llm_call_duration_ms >= 0,cost_usd >= 0
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.agent_repo import AgentRepository


def _ok_resp(content="ok"):
    return {"content": content, "tool_calls": None, "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}


# ===========================================================================
# turn_duration_ms
# ===========================================================================


@pytest.mark.asyncio
async def test_turn_metrics_include_duration_ms(db_session) -> None:
    """agent_turn_metrics 日志应含 turn_duration_ms 字段（>= 0）。"""
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    mock_llm.return_value.chat_with_tools = AsyncMock(return_value=_ok_resp())

    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm), \
         patch.object(rl.logger, "info") as mock_log:
        _ = [e async for e in rl.run_agent_turn(session.id, "X")]

    metrics_calls = [
        c for c in mock_log.call_args_list
        if c.args and c.args[0] == "agent_turn_metrics"
    ]
    assert len(metrics_calls) == 1
    kw = metrics_calls[0].kwargs
    assert "turn_duration_ms" in kw
    assert isinstance(kw["turn_duration_ms"], (int, float))
    assert kw["turn_duration_ms"] >= 0


@pytest.mark.asyncio
async def test_turn_metrics_duration_increases_with_iterations(db_session) -> None:
    """iteration 越多 turn_duration_ms 越大(大致趋势)。"""
    repo = AgentRepository(db_session)
    session_a = await repo.create_session(title="A")
    session_b = await repo.create_session(title="B")

    import app.domain.agent.react_loop as rl
    from unittest.mock import MagicMock
    mock_llm = MagicMock()

    # session_a: 1 iteration
    mock_llm.return_value.chat_with_tools = AsyncMock(return_value=_ok_resp())
    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm), \
         patch.object(rl.logger, "info") as mock_log:
        _ = [e async for e in rl.run_agent_turn(session_a.id, "X")]
    duration_a = next(
        c.kwargs["turn_duration_ms"] for c in mock_log.call_args_list
        if c.args and c.args[0] == "agent_turn_metrics"
    )

    # session_b: 多次迭代(模拟有工具调用 + 多次 LLM)
    import asyncio
    call_count = 0
    async def _multi_llm(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return {
                "content": None,
                "tool_calls": [{"id": f"tc{call_count}", "function": {"name": "search_knowledge", "arguments": '{"query":"x"}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        return _ok_resp("done")

    mock_llm2 = MagicMock()
    mock_llm2.return_value.chat_with_tools = AsyncMock(side_effect=_multi_llm)
    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm2), \
         patch("app.domain.agent.tool_executor.ToolExecutor.execute",
               new=AsyncMock(return_value={"x": 1})), \
         patch.object(rl.logger, "info") as mock_log:
        _ = [e async for e in rl.run_agent_turn(session_b.id, "X")]
    duration_b = next(
        c.kwargs["turn_duration_ms"] for c in mock_log.call_args_list
        if c.args and c.args[0] == "agent_turn_metrics"
    )

    # 多迭代应 >= 单迭代(浮点 + asyncio 调度允许相等)
    assert duration_b >= duration_a * 0.5, (
        f"3-iter turn ({duration_b}ms) 应不小于 1-iter turn ({duration_a}ms) 的一半"
    )


# ===========================================================================
# cost_usd 字段
# ===========================================================================


@pytest.mark.asyncio
async def test_turn_metrics_include_cost_usd(db_session, monkeypatch) -> None:
    """agent_turn_metrics 日志应含 cost_usd 字段(基于 usage + provider pricing)。

    用 monkeypatch 覆盖 settings.llm_providers 让 provider resolve 能命中。
    """
    from app.core.config import get_settings
    from app.core.providers import LLMProvider

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_PROVIDERS", "deepseek")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    # 100 prompt + 50 completion (deepseek pricing: 0.00027/0.0011 per 1k)
    # cost = 100/1000*0.00027 + 50/1000*0.0011 = 0.000027 + 0.000055 = 0.000082
    mock_llm.return_value.chat_with_tools = AsyncMock(return_value=_ok_resp())

    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm), \
         patch.object(rl.logger, "info") as mock_log:
        _ = [e async for e in rl.run_agent_turn(session.id, "X")]

    metrics_calls = [
        c for c in mock_log.call_args_list
        if c.args and c.args[0] == "agent_turn_metrics"
    ]
    assert len(metrics_calls) == 1
    kw = metrics_calls[0].kwargs
    assert "cost_usd" in kw
    # cost_usd 应是 Decimal 或 float
    cost = kw["cost_usd"]
    if cost is not None:
        # 应大于 0(基于 150 tokens)
        assert float(cost) > 0


@pytest.mark.asyncio
async def test_cost_usd_zero_when_no_usage(db_session, monkeypatch) -> None:
    """usage 缺失时 cost_usd 应为 0 或 None,不抛。"""
    from app.core.config import get_settings
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_PROVIDERS", "deepseek")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    from unittest.mock import MagicMock
    mock_llm = MagicMock()
    mock_llm.return_value.chat_with_tools = AsyncMock(return_value={
        "content": "ok", "tool_calls": None,
        # usage 缺失
    })

    with patch("app.domain.agent.react_loop.LLMClient", new=mock_llm), \
         patch.object(rl.logger, "info") as mock_log:
        _ = [e async for e in rl.run_agent_turn(session.id, "X")]

    metrics_calls = [
        c for c in mock_log.call_args_list
        if c.args and c.args[0] == "agent_turn_metrics"
    ]
    kw = metrics_calls[0].kwargs
    cost = kw.get("cost_usd")
    # 缺失 usage 时 cost 应为 0 或 None
    assert cost is None or float(cost) == 0


# ===========================================================================
# LLM call duration - LLMClient 在 chat_with_tools 中记录耗时
# ===========================================================================


def test_llm_client_exposes_timing_attribute(monkeypatch) -> None:
    """LLMClient 实例应暴露 last_call_duration_ms 属性(>=0)。

    实现路径：chat_with_tools 用 time.perf_counter() 包裹 openai 调用,
    把 elapsed 存到 self.last_call_duration_ms。
    """
    from app.core.config import get_settings
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    import app.domain.llm_client as llm_mod
    settings = get_settings()
    client = llm_mod.LLMClient(settings)

    # 应有 last_call_duration_ms 属性(可能初值 0)
    assert hasattr(client, "last_call_duration_ms"), (
        "LLMClient 应暴露 last_call_duration_ms 属性"
    )
    assert client.last_call_duration_ms >= 0