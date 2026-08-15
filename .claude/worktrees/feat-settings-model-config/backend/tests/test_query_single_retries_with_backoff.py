"""重试 + 指数退避测试 (P0#5)。

依据: docs/review/05-failure-recovery.md §3.2 + upgrade-design §3 P0#5。

断言:
1. max_retries 默认从 1 提升到 3
2. 重试使用指数退避: asyncio.sleep(2 ** (attempt - 1))
3. 重试次数 = max_retries + 1 次 (含首次)
4. 退避序列: 第 1 次重试睡 1s, 第 2 次睡 2s, 第 3 次睡 4s
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.domain.exceptions import LlmError
from app.domain.llm_client import LLMClient, _ProviderConfig


def _fake_cfg() -> _ProviderConfig:
    """构造一个假的 provider 配置,只为通过存在性检查。"""
    return _ProviderConfig(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="test-model",
    )


@pytest.fixture
def client_with_test_provider() -> LLMClient:
    """构造一个 LLMClient,带 "test" provider + mock _make_async_client。"""
    settings = Settings()
    c = LLMClient(settings)
    # 注入 test provider + 替换 _make_async_client(不连真实 API)
    c._providers = {"test": _fake_cfg()}
    c._make_async_client = MagicMock()  # type: ignore[method-assign]
    return c


@pytest.mark.asyncio
async def test_query_single_default_max_retries_is_at_least_three() -> None:
    """query_single 默认 max_retries ≥ 3(SPEC §3 P0#5 要求)。"""
    import inspect

    sig = inspect.signature(LLMClient.query_single)
    default = sig.parameters["max_retries"].default
    assert isinstance(default, int)
    assert default >= 3, f"max_retries default should be ≥3, got {default}"


@pytest.mark.asyncio
async def test_query_single_retries_three_times_with_exponential_backoff(
    client_with_test_provider: LLMClient,
) -> None:
    """连续抛 retryable LlmError → 触发 4 次调用 + 3 次指数退避 (1s, 2s, 4s)。"""
    client_obj = client_with_test_provider
    fake_async_client = MagicMock()
    fake_async_client.chat.completions.create = AsyncMock(
        side_effect=LlmError(provider="test", message="rate limited", retryable=True)
    )
    client_obj._make_async_client.return_value = fake_async_client  # type: ignore[attr-defined]

    with patch("app.domain.llm_client.asyncio.sleep") as mock_sleep:
        result = await client_obj.query_single(
            provider="test",
            question="Q?",
            brand="B",
            industry="I",
            max_retries=3,
        )

    # 1) 调用次数: max_retries(3) + 首次 = 4 次
    assert fake_async_client.chat.completions.create.call_count == 4

    # 2) 退避次数: 3 次 (attempt 1, 2, 3 各睡一次)
    assert mock_sleep.call_count == 3

    # 3) 指数退避序列: 2^0=1, 2^1=2, 2^2=4
    delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert delays == [1, 2, 4], f"expected [1, 2, 4], got {delays}"

    # 4) 返回 MentionResult with error,不抛异常
    assert result.error is not None
    assert "rate limited" in result.error or "LLM error" in result.error


@pytest.mark.asyncio
async def test_query_single_does_not_retry_on_non_retryable(
    client_with_test_provider: LLMClient,
) -> None:
    """非 retryable LlmError → 立即停止,不重试不睡。"""
    client_obj = client_with_test_provider
    fake_async_client = MagicMock()
    fake_async_client.chat.completions.create = AsyncMock(
        side_effect=LlmError(provider="test", message="bad request", retryable=False)
    )
    client_obj._make_async_client.return_value = fake_async_client  # type: ignore[attr-defined]

    with patch("app.domain.llm_client.asyncio.sleep") as mock_sleep:
        result = await client_obj.query_single(
            provider="test", question="Q?", brand="B", industry="I", max_retries=3
        )

    # 仅调 1 次 (首次失败 → 非 retryable → 立即停)
    assert fake_async_client.chat.completions.create.call_count == 1
    # 无 sleep
    assert mock_sleep.call_count == 0
    assert result.error is not None


@pytest.mark.asyncio
async def test_query_single_returns_first_success_without_sleep(
    client_with_test_provider: LLMClient,
) -> None:
    """首次成功 → 不睡,只调 1 次。"""
    client_obj = client_with_test_provider
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content="YES, B is mentioned"))]
    fake_async_client = MagicMock()
    fake_async_client.chat.completions.create = AsyncMock(return_value=fake_response)
    client_obj._make_async_client.return_value = fake_async_client  # type: ignore[attr-defined]

    with patch("app.domain.llm_client.asyncio.sleep") as mock_sleep:
        result = await client_obj.query_single(
            provider="test", question="Q?", brand="B", industry="I", max_retries=3
        )

    assert fake_async_client.chat.completions.create.call_count == 1
    assert mock_sleep.call_count == 0
    assert result.brand_mentioned is True