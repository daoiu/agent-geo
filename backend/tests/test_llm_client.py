"""Tests for LLM client. Uses unittest.mock to mock AsyncOpenAI responses."""
from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest import mock

import pytest

from app.core.config import Settings
from app.domain.llm_client import LLMClient


def make_mock_response(content: str) -> mock.AsyncMock:
    """Build an AsyncMock that mimics openai.chat.completions.create response."""
    choice = mock.AsyncMock()
    choice.message.content = content
    response = mock.AsyncMock()
    response.choices = [choice]
    return response


@pytest.fixture
def settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        llm_call_timeout_s=10,
    )


@pytest.fixture
def client(settings: Settings) -> LLMClient:
    return LLMClient(settings)


@pytest.mark.asyncio
async def test_query_single_finds_mention(client: LLMClient) -> None:
    """When LLM mentions brand, brand_mentioned is True."""
    mock_response = make_mock_response(
        "在国产手机中，小米是不错的选择，品质可靠。"
    )
    with mock.patch(
        "app.domain.llm_client.AsyncOpenAI",
        return_value=mock.AsyncMock(),
    ) as mock_client_cls:
        mock_instance = mock_client_cls.return_value
        mock_instance.chat.completions.create = mock.AsyncMock(
            return_value=mock_response
        )
        result = await client.query_single(
            provider="deepseek",
            question="国产手机推荐",
            brand="小米",
            industry="手机",
        )

    assert result.brand_mentioned is True
    assert result.mention_position is not None
    assert result.llm_provider == "deepseek"


@pytest.mark.asyncio
async def test_query_single_no_mention(client: LLMClient) -> None:
    """When LLM does not mention brand, brand_mentioned is False."""
    mock_response = make_mock_response("苹果和华为是常见选择。")
    with mock.patch(
        "app.domain.llm_client.AsyncOpenAI",
        return_value=mock.AsyncMock(),
    ) as mock_client_cls:
        mock_instance = mock_client_cls.return_value
        mock_instance.chat.completions.create = mock.AsyncMock(
            return_value=mock_response
        )
        result = await client.query_single(
            provider="deepseek", question="手机推荐", brand="小米", industry="手机",
        )

    assert result.brand_mentioned is False
    assert result.mention_position is None


@pytest.mark.asyncio
async def test_query_single_handles_timeout(client: LLMClient) -> None:
    """API connection error results in brand_mentioned=False with error set."""
    import openai

    with mock.patch(
        "app.domain.llm_client.AsyncOpenAI",
        return_value=mock.AsyncMock(),
    ) as mock_client_cls:
        mock_instance = mock_client_cls.return_value
        mock_instance.chat.completions.create = mock.AsyncMock(
            side_effect=openai.APIConnectionError(
                message="Connection error.", request=None
            )
        )
        result = await client.query_single(
            provider="deepseek", question="q", brand="b", industry="i",
        )

    assert result.brand_mentioned is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_query_mentions_runs_in_parallel(client: LLMClient) -> None:
    """Multiple questions should be queried concurrently."""
    call_count = 0

    async def mock_create(*args: Any, **kwargs: Any) -> mock.AsyncMock:
        nonlocal call_count
        call_count += 1
        return make_mock_response("小米不错")

    with mock.patch(
        "app.domain.llm_client.AsyncOpenAI",
        return_value=mock.AsyncMock(),
    ) as mock_client_cls:
        mock_instance = mock_client_cls.return_value
        mock_instance.chat.completions.create = mock.AsyncMock(
            side_effect=mock_create
        )
        start = time.monotonic()
        results = await client.query_mentions(
            brand="小米",
            industry="手机",
            questions=["q1", "q2", "q3"],
            providers=["deepseek"],
        )
        elapsed = time.monotonic() - start

    assert len(results) == 3
    assert call_count == 3
    assert elapsed < 5  # generous bound — parallel execution should be fast
