"""Tests for LLMClient.chat_with_tools (v0.4)."""
from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from app.core.config import Settings
from app.domain.llm_client import LLMClient


def _make_response(content: str | None, tool_calls: list[Any] | None) -> mock.AsyncMock:
    """Build a mock openai chat.completions.create response."""
    choice = mock.AsyncMock()
    choice.message.content = content
    choice.message.tool_calls = tool_calls
    response = mock.AsyncMock()
    response.choices = [choice]
    return response


def _make_tool_call(tc_id: str, name: str, arguments: str) -> mock.AsyncMock:
    tc = mock.AsyncMock()
    tc.id = tc_id
    tc.type = "function"
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


@pytest.fixture
def settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        llm_call_timeout_s=10,
    )


@pytest.fixture
def llm(settings: Settings) -> LLMClient:
    return LLMClient(settings)


@pytest.mark.asyncio
async def test_chat_with_tools_returns_text_content_only(llm: LLMClient) -> None:
    """When LLM responds with text only, tool_calls is None."""
    response = _make_response("好的，让我先诊断。", None)

    with mock.patch(
        "app.domain.llm_client.AsyncOpenAI",
        return_value=mock.AsyncMock(),
    ) as mock_cls:
        mock_cls.return_value.chat.completions.create = mock.AsyncMock(
            return_value=response
        )
        result = await llm.chat_with_tools(
            messages=[{"role": "user", "content": "诊断小米"}],
            tools=[{
                "type": "function",
                "function": {
                    "name": "diagnose_brand",
                    "description": "...",
                    "parameters": {},
                },
            }],
        )

    assert result["content"] == "好的，让我先诊断。"
    assert result["tool_calls"] is None


@pytest.mark.asyncio
async def test_chat_with_tools_parses_tool_calls(llm: LLMClient) -> None:
    """When LLM responds with tool_calls, parse id/name/arguments."""
    tc = _make_tool_call(
        "tc_001",
        "diagnose_brand",
        '{"brand_name": "小米", "industry": "手机", "official_url": "https://www.mi.com"}',
    )
    response = _make_response(None, [tc])

    with mock.patch(
        "app.domain.llm_client.AsyncOpenAI",
        return_value=mock.AsyncMock(),
    ) as mock_cls:
        mock_cls.return_value.chat.completions.create = mock.AsyncMock(
            return_value=response
        )
        result = await llm.chat_with_tools(
            messages=[{"role": "user", "content": "诊断"}],
            tools=[{
                "type": "function",
                "function": {"name": "diagnose_brand"},
            }],
        )

    assert result["content"] is None
    assert result["tool_calls"] is not None
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["id"] == "tc_001"
    assert result["tool_calls"][0]["function"]["name"] == "diagnose_brand"
    assert result["tool_calls"][0]["function"]["arguments"] == (
        '{"brand_name": "小米", "industry": "手机", "official_url": "https://www.mi.com"}'
    )


@pytest.mark.asyncio
async def test_chat_with_tools_returns_both_content_and_tool_calls(llm: LLMClient) -> None:
    """LLM can return both text content and tool_calls simultaneously."""
    tc = _make_tool_call(
        "tc_001", "diagnose_brand", '{"brand_name": "小米"}'
    )
    response = _make_response("让我先看小米的分数。", [tc])

    with mock.patch(
        "app.domain.llm_client.AsyncOpenAI",
        return_value=mock.AsyncMock(),
    ) as mock_cls:
        mock_cls.return_value.chat.completions.create = mock.AsyncMock(
            return_value=response
        )
        result = await llm.chat_with_tools(
            messages=[{"role": "user", "content": "诊断"}],
            tools=[{"type": "function", "function": {"name": "diagnose_brand"}}],
        )

    assert result["content"] == "让我先看小米的分数。"
    assert result["tool_calls"] is not None
    assert len(result["tool_calls"]) == 1


@pytest.mark.asyncio
async def test_chat_with_tools_passes_tools_and_tool_choice(llm: LLMClient) -> None:
    """The LLM call should pass tools and tool_choice='auto'."""
    response = _make_response("OK", None)

    tools = [{
        "type": "function",
        "function": {"name": "test_tool", "description": "x", "parameters": {}},
    }]

    with mock.patch(
        "app.domain.llm_client.AsyncOpenAI",
        return_value=mock.AsyncMock(),
    ) as mock_cls:
        mock_cls.return_value.chat.completions.create = mock.AsyncMock(
            return_value=response
        )
        await llm.chat_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=tools,
        )
        mock_cls.return_value.chat.completions.create.assert_called_once()
        call_kwargs = mock_cls.return_value.chat.completions.create.call_args.kwargs
        assert call_kwargs["tools"] == tools
        assert call_kwargs["tool_choice"] == "auto"
        assert call_kwargs["model"] == "deepseek-chat"