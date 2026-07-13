"""Tests for LLMClient usage passthrough (Phase 1)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from app.core.config import Settings
from app.domain.llm_client import LLMClient, _extract_usage


def _make_response(content, tool_calls, usage):
    """Mock openai response;usage 显式设置(AsyncMock 会自动造子 mock,故必须显式赋值)。"""
    choice = mock.AsyncMock()
    choice.message.content = content
    choice.message.tool_calls = tool_calls
    response = mock.AsyncMock()
    response.choices = [choice]
    response.usage = usage
    return response


@pytest.fixture(autouse=True)
def _isolate_provider_env(monkeypatch):
    from app.domain import llm_client as lc
    monkeypatch.setattr(lc, "_load_env_values", lambda: {
        "DEEPSEEK_API_KEY": "sk-test",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
        "DEEPSEEK_MODEL": "deepseek-chat",
    })


@pytest.fixture
def llm():
    return LLMClient(Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        llm_call_timeout_s=10,
    ))


def test_extract_usage_none_when_absent():
    assert _extract_usage(SimpleNamespace(usage=None)) is None
    assert _extract_usage(SimpleNamespace()) is None


def test_extract_usage_reads_three_fields():
    resp = SimpleNamespace(usage=SimpleNamespace(
        prompt_tokens=10, completion_tokens=5, total_tokens=15))
    assert _extract_usage(resp) == {
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


@pytest.mark.asyncio
async def test_chat_with_tools_returns_usage(llm):
    response = _make_response("ok", None, SimpleNamespace(
        prompt_tokens=100, completion_tokens=20, total_tokens=120))
    with mock.patch("app.domain.llm_client.AsyncOpenAI",
                    return_value=mock.AsyncMock()) as mock_cls:
        mock_cls.return_value.chat.completions.create = mock.AsyncMock(
            return_value=response)
        result = await llm.chat_with_tools(
            messages=[{"role": "user", "content": "hi"}], tools=[])
    assert result["usage"] == {
        "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}


@pytest.mark.asyncio
async def test_chat_with_tools_usage_none_when_provider_omits(llm):
    response = _make_response("ok", None, None)
    with mock.patch("app.domain.llm_client.AsyncOpenAI",
                    return_value=mock.AsyncMock()) as mock_cls:
        mock_cls.return_value.chat.completions.create = mock.AsyncMock(
            return_value=response)
        result = await llm.chat_with_tools(
            messages=[{"role": "user", "content": "hi"}], tools=[])
    assert result["usage"] is None
