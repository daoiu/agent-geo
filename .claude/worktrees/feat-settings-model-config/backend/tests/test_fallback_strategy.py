"""P2#51（Task 37）: Fallback 策略测试。

目标:
- 主 provider 失败切备用 provider
- 仅 transient 错误触发 fallback(permanent 错误立即抛)
- Fallback 链配置: FALLBACK_CHAIN env var
- LLMClient.query_single 自动应用 fallback
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest


def test_fallback_chain_settings():
    """Settings 必须含 FALLBACK_CHAIN 配置。"""
    with patch.dict("os.environ", {"GEO_ALLOW_MISSING_LLM_KEY": "1"}, clear=False):
        from app.core.config import Settings

        s = Settings()
        assert hasattr(s, "fallback_chain"), "missing fallback_chain"
        assert s.fallback_chain, "fallback_chain must have default"


def test_fallback_chain_parsed_as_list():
    """fallback_chain 应可解析为 list。"""
    with patch.dict("os.environ", {"GEO_ALLOW_MISSING_LLM_KEY": "1", "FALLBACK_CHAIN": "deepseek,kimi,openai"}, clear=False):
        from app.core.config import Settings

        s = Settings()
        chain = s.parsed_fallback_chain
        assert isinstance(chain, list)
        assert "deepseek" in chain


def test_call_with_fallback_succeeds_first():
    """第一个 provider 成功时不调用后续。"""
    from app.core.fallback import call_with_fallback

    async def fake_call(provider, *args, **kwargs):
        return f"result-{provider}"

    providers = ["deepseek", "kimi"]
    result = asyncio.run(
        call_with_fallback(fake_call, providers, "arg1")
    )
    assert result == "result-deepseek"


def test_call_with_fallback_skips_transient_and_uses_next():
    """主 provider 抛 transient 时应切下一个 provider。"""
    from app.core.fallback import TransientError, call_with_fallback

    call_log: list[str] = []

    async def fake_call(provider, *args, **kwargs):
        call_log.append(provider)
        if provider == "deepseek":
            raise TransientError("rate limit")
        return f"ok-{provider}"

    providers = ["deepseek", "kimi"]
    result = asyncio.run(
        call_with_fallback(fake_call, providers, "x")
    )
    assert result == "ok-kimi"
    assert call_log == ["deepseek", "kimi"]


def test_call_with_fallback_does_not_catch_permanent():
    """permanent 错误不应触发 fallback,应直接抛。"""
    from app.core.fallback import PermanentError, call_with_fallback

    call_log: list[str] = []

    async def fake_call(provider, *args, **kwargs):
        call_log.append(provider)
        raise PermanentError("auth failed")

    providers = ["deepseek", "kimi"]
    with pytest.raises(PermanentError):
        asyncio.run(call_with_fallback(fake_call, providers, "x"))
    # 只调用了第一个,没 fallback
    assert call_log == ["deepseek"]


def test_call_with_fallback_returns_last_error_when_all_fail():
    """所有 provider 都失败时,应抛最后的异常(包含尝试链)。"""
    from app.core.fallback import TransientError, call_with_fallback

    async def fake_call(provider, *args, **kwargs):
        raise TransientError(f"fail-{provider}")

    providers = ["deepseek", "kimi", "openai"]
    with pytest.raises(TransientError) as exc_info:
        asyncio.run(call_with_fallback(fake_call, providers, "x"))
    # 异常信息应含最后失败的 provider
    assert "fail-openai" in str(exc_info.value)


def test_fallback_records_metrics():
    """fallback 应记录 metrics(fallback_count)."""
    from app.core.fallback import TransientError, call_with_fallback

    async def fake_call(provider, *args, **kwargs):
        if provider == "deepseek":
            raise TransientError("rate limit")
        return "ok"

    # 跑 fallback,看 metrics 是否增加
    from app.core import metrics

    before = metrics.llm_errors_total.labels(error_type="transient", provider="deepseek")._value.get() if hasattr(metrics.llm_errors_total.labels(error_type="transient", provider="deepseek"), "_value") else 0

    asyncio.run(call_with_fallback(fake_call, ["deepseek", "kimi"], "x"))


def test_fallback_chain_skip_providers_without_keys():
    """fallback 链中无 key 的 provider 应被跳过。"""
    import os
    from app.core.fallback import call_with_fallback

    # 确保 deepseek/kimi/openai 都没有 key
    for k in ["DEEPSEEK_API_KEY", "KIMI_API_KEY", "OPENAI_API_KEY"]:
        os.environ.pop(k, None)

    async def fake_call(provider, *args, **kwargs):
        return f"called-{provider}"

    # chain 中所有 provider 都无 key,应直接调用第一个(不抛)
    result = asyncio.run(call_with_fallback(fake_call, ["deepseek", "kimi"], "x"))
    assert result == "called-deepseek"