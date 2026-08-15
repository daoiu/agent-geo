"""验证 MAX_REACT_ITERATIONS 提取到 Settings（P1#7 / Task 8）。

确保 react_loop 的迭代上限可由 Settings 配置（env 覆盖），而不是硬编码常量。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import get_settings


def test_settings_has_max_react_iterations_field() -> None:
    """Settings 必须暴露 max_react_iterations 字段，默认值 7（与原常量一致）。"""
    settings = get_settings()
    # 字段存在
    assert hasattr(settings, "max_react_iterations"), (
        "Settings 应有 max_react_iterations 字段（Task 8：MAX_REACT_ITERATIONS → Settings）"
    )
    # 默认值 7（与原硬编码常量一致，不破坏现有行为）
    assert settings.max_react_iterations == 7


def test_max_react_iterations_override_via_env(monkeypatch) -> None:
    """通过环境变量可覆盖 max_react_iterations。"""
    monkeypatch.setenv("MAX_REACT_ITERATIONS", "3")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    settings = get_settings()
    assert settings.max_react_iterations == 3


def _tool_resp(tc_id: str = "tc") -> dict:
    """构造一个 LLM 响应：永远返回 tool_call，迫使 react_loop 跑满迭代。"""
    return {
        "content": None,
        "tool_calls": [
            {
                "id": tc_id,
                "function": {
                    "name": "diagnose_brand",
                    "arguments": '{"brand_name":"X","industry":"Y","official_url":"https://x.com"}',
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


@pytest.mark.asyncio
async def test_react_loop_respects_settings_max_react_iterations(
    db_session, monkeypatch
) -> None:
    """把 MAX_REACT_ITERATIONS 设成 3，react_loop 应该跑 3 次就 max_iterations_reached。"""
    from app.repositories.agent_repo import AgentRepository
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    monkeypatch.setenv("MAX_REACT_ITERATIONS", "3")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM, \
         patch("app.domain.agent.tool_executor.ToolExecutor.execute",
               new=AsyncMock(return_value={"x": 1})):
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value=_tool_resp())
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    # 末事件是 max_iterations_reached
    assert events[-1]["event"] == "max_iterations_reached"
    # 统计 assistant_message 数量 = 实际迭代次数
    assistant_msgs = [e for e in events if e["event"] == "assistant_message"]
    assert len(assistant_msgs) == 3, (
        f"应跑 3 次迭代，实际 {len(assistant_msgs)} 次（MAX_REACT_ITERATIONS env 未生效？）"
    )


@pytest.mark.asyncio
async def test_react_loop_default_iterations_unchanged(db_session) -> None:
    """默认 Settings 不变时，迭代上限仍是 7（兼容阶段 1 行为）。"""
    from app.repositories.agent_repo import AgentRepository
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM, \
         patch("app.domain.agent.tool_executor.ToolExecutor.execute",
               new=AsyncMock(return_value={"x": 1})):
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value=_tool_resp())
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    assert events[-1]["event"] == "max_iterations_reached"
    assistant_msgs = [e for e in events if e["event"] == "assistant_message"]
    assert len(assistant_msgs) == 7, (
        f"默认应跑 7 次迭代（与阶段 1 一致），实际 {len(assistant_msgs)} 次"
    )