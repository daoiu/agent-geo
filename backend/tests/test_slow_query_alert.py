"""验证慢查询告警（P1#24 / Task 25）。

行为契约：
- llm_client.py 检测 LLM 调用耗时 > Settings.llm_slow_query_threshold_ms(默认 60000)
- 触发 structlog warning 'llm_slow_query_alert',记录 provider/duration_ms/threshold
- 正常耗时(< 60s)不告警
- 阈值可通过 env 覆盖(llm_slow_query_threshold_ms)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_default_slow_query_threshold_is_60s(monkeypatch) -> None:
    """Settings.llm_slow_query_threshold_ms 默认 60000(60 秒)。"""
    from app.core.config import get_settings
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    settings = get_settings()
    assert settings.llm_slow_query_threshold_ms == 60_000, (
        f"默认阈值应为 60000ms,实际 {settings.llm_slow_query_threshold_ms}"
    )


def test_slow_query_threshold_env_override(monkeypatch) -> None:
    """env llm_slow_query_threshold_ms 可覆盖。"""
    from app.core.config import get_settings
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_SLOW_QUERY_THRESHOLD_MS", "10000")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    settings = get_settings()
    assert settings.llm_slow_query_threshold_ms == 10_000


@pytest.mark.asyncio
async def test_llm_over_threshold_logs_warning(monkeypatch) -> None:
    """LLM 调用 > 阈值时记录 warning 事件。"""
    from app.core.config import get_settings
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_SLOW_QUERY_THRESHOLD_MS", "100")  # 100ms 容易触发
    get_settings.cache_clear()  # type: ignore[attr-defined]

    import app.domain.llm_client as llm_mod
    import app.domain.llm_client as rl_module
    settings = get_settings()
    client = llm_mod.LLMClient(settings)

    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = "ok"
    fake_response.choices[0].message.tool_calls = None
    fake_response.usage.prompt_tokens = 1
    fake_response.usage.completion_tokens = 1
    fake_response.usage.total_tokens = 2

    import asyncio
    async def _slow_call(*args, **kwargs):
        await asyncio.sleep(0.2)  # 200ms > 100ms 阈值
        return fake_response

    with patch.object(client, "_make_async_client") as mock_factory:
        # mock_factory 返回一个 MagicMock,有 chat.completions.create
        inner_mock = MagicMock()
        inner_mock.chat.completions.create = _slow_call
        mock_factory.return_value = inner_mock

        with patch.object(rl_module.logger, "warning") as mock_warn:
            await client.chat_with_tools(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
            )

    # 应有 warning('llm_slow_query_alert')
    warn_calls = [
        c for c in mock_warn.call_args_list
        if c.args and c.args[0] == "llm_slow_query_alert"
    ]
    assert len(warn_calls) >= 1, (
        f"LLM 调用 > 阈值应触发 warning,实际 warning calls: {mock_warn.call_args_list}"
    )
    # 警告应记录 duration_ms + threshold
    warn_kw = warn_calls[0].kwargs
    assert "duration_ms" in warn_kw
    assert "threshold_ms" in warn_kw
    assert warn_kw["duration_ms"] >= 100  # 至少阈值
    assert warn_kw["threshold_ms"] == 100


@pytest.mark.asyncio
async def test_llm_under_threshold_no_warning(monkeypatch) -> None:
    """LLM 调用 < 阈值时不告警。"""
    from app.core.config import get_settings
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_SLOW_QUERY_THRESHOLD_MS", "10000")  # 10s 阈值
    get_settings.cache_clear()  # type: ignore[attr-defined]

    import app.domain.llm_client as rl_module
    settings = get_settings()
    client = rl_module.LLMClient(settings)

    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = "ok"
    fake_response.choices[0].message.tool_calls = None
    fake_response.usage.prompt_tokens = 1
    fake_response.usage.completion_tokens = 1
    fake_response.usage.total_tokens = 2

    with patch.object(client, "_make_async_client") as mock_factory:
        inner_mock = MagicMock()
        async def _fast_call(*args, **kwargs):
            return fake_response
        inner_mock.chat.completions.create = _fast_call
        mock_factory.return_value = inner_mock

        with patch.object(rl_module.logger, "warning") as mock_warn:
            await client.chat_with_tools(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
            )

    # 应无 slow_query_alert 警告
    slow_warns = [
        c for c in mock_warn.call_args_list
        if c.args and c.args[0] == "llm_slow_query_alert"
    ]
    assert len(slow_warns) == 0, f"快速 LLM 调用不应告警,实际 {slow_warns}"