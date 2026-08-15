"""Tests for the generic OpenAI-compatible provider discovery in LLMClient."""
from __future__ import annotations

import os
from unittest import mock

import pytest

from app.core.config import Settings
from app.domain.llm_client import (
    LLMClient,
    _normalize_base_url,
    _build_provider_map,
)


def test_normalize_base_url_appends_v1_to_bare_host() -> None:
    assert _normalize_base_url("https://api.minimaxi.com") == "https://api.minimaxi.com/v1"
    assert _normalize_base_url("https://api.example.com/") == "https://api.example.com/v1"


def test_normalize_base_url_leaves_existing_path_alone() -> None:
    assert _normalize_base_url("https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert _normalize_base_url("https://api.deepseek.com/v2/chat") == "https://api.deepseek.com/v2/chat"


def test_build_provider_map_reads_arbitrary_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plugging in a brand-new provider name only needs 3 env vars."""
    monkeypatch.setenv("MINIMAX_API_KEY", "test-minimax-key")
    monkeypatch.setenv("MINIMAX_BASE_URL", "https://api.minimaxi.com")
    monkeypatch.setenv("MINIMAX_MODEL", "MiniMax-M2.7")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)

    settings = Settings()  # validator accepts non-DEEPSEEK keys
    providers = _build_provider_map(settings)

    assert "minimax" in providers
    assert providers["minimax"].api_key == "test-minimax-key"
    # base URL was bare host, normalized to /v1
    assert providers["minimax"].base_url == "https://api.minimaxi.com/v1"
    assert providers["minimax"].model == "MiniMax-M2.7"


def test_build_provider_map_keeps_legacy_deepseek_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backward compat: when .env has no DEEPSEEK_API_KEY, fall back to Settings fields."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    # Patch the project .env to also be empty of any provider keys
    fake_env = {"HOME": "C:\\Users\\test"}
    monkeypatch.setattr(
        "app.domain.llm_client._load_env_values",
        lambda: {k: v for k, v in fake_env.items()},
    )
    settings = Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
    )
    providers = _build_provider_map(settings)
    assert "deepseek" in providers
    assert providers["deepseek"].api_key == "sk-test"


def test_primary_provider_name_picks_first_enabled_with_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "x")
    monkeypatch.setenv("MINIMAX_BASE_URL", "https://api.minimaxi.com")
    monkeypatch.setenv("MINIMAX_MODEL", "MiniMax-M2.7")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    settings = Settings(llm_providers="minimax,deepseek")
    client = LLMClient(settings)
    assert client.primary_provider_name() == "minimax"


@pytest.mark.asyncio
async def test_chat_with_tools_uses_minimax_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "x")
    monkeypatch.setenv("MINIMAX_BASE_URL", "https://api.minimaxi.com")
    monkeypatch.setenv("MINIMAX_MODEL", "MiniMax-M2.7")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    settings = Settings(llm_providers="minimax")

    captured_kwargs: list[dict] = []
    fake_create = mock.AsyncMock(
        return_value=_make_chat_response("hi", tool_calls=None)
    )

    class FakeAsyncOpenAI:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured_kwargs.append(kwargs)
            self.chat = mock.Mock()
            self.chat.completions.create = fake_create

    with mock.patch("app.domain.llm_client.AsyncOpenAI", FakeAsyncOpenAI):
        client = LLMClient(settings)
        result = await client.chat_with_tools(messages=[{"role": "user", "content": "hi"}], tools=[])

    assert result["content"] == "hi"
    # The primary's base_url was passed to AsyncOpenAI
    assert captured_kwargs[0]["base_url"] == "https://api.minimaxi.com/v1"
    fake_create.assert_called_once()
    call_kwargs = fake_create.call_args.kwargs
    assert call_kwargs["model"] == "MiniMax-M2.7"


def _make_chat_response(content: str, tool_calls: Any) -> Any:
    choice = mock.AsyncMock()
    choice.message.content = content
    choice.message.tool_calls = tool_calls
    response = mock.AsyncMock()
    response.choices = [choice]
    return response
