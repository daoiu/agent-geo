"""Tests for session manager helpers (v0.4)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.domain.agent.session_manager import auto_generate_title


@pytest.mark.asyncio
async def test_auto_generate_title_uses_llm_response() -> None:
    """LLM 返回短标题时，直接使用。"""
    with patch("app.domain.agent.session_manager.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.simple_chat = AsyncMock(return_value="诊断小米品牌")
        title = await auto_generate_title("帮我诊断一下小米的 GEO 现状")
        assert title == "诊断小米品牌"


@pytest.mark.asyncio
async def test_auto_generate_title_truncates_long_response() -> None:
    """LLM 返回长字符串时截断到 20 字符。"""
    with patch("app.domain.agent.session_manager.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        long = "x" * 100
        mock_instance.simple_chat = AsyncMock(return_value=long)
        title = await auto_generate_title("hi")
        assert len(title) <= 20
        assert title == "x" * 20


@pytest.mark.asyncio
async def test_auto_generate_title_falls_back_on_llm_error() -> None:
    """LLM 抛异常时，fallback 到消息的前 20 字符。"""
    with patch("app.domain.agent.session_manager.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.simple_chat = AsyncMock(side_effect=Exception("LLM down"))
        title = await auto_generate_title("帮我诊断小米的 GEO 现状，目标提升到 80 分以上")
        assert len(title) <= 20
        # fallback 应该包含原消息的前 20 字符
        assert title == "帮我诊断小米的 GEO 现状，目标提升到 80 分以上"[:20]


@pytest.mark.asyncio
async def test_auto_generate_title_strips_whitespace() -> None:
    """LLM 返回带前后空白的标题时 strip。"""
    with patch("app.domain.agent.session_manager.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.simple_chat = AsyncMock(return_value="  标题带空格  \n")
        title = await auto_generate_title("hi")
        assert title == "标题带空格"


@pytest.mark.asyncio
async def test_auto_generate_title_empty_response_falls_back() -> None:
    """LLM 返回空字符串时 fallback 到截断。"""
    with patch("app.domain.agent.session_manager.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.simple_chat = AsyncMock(return_value="")
        title = await auto_generate_title("第一条消息用来取标题")
        assert title == "第一条消息用来取标题"[:20]