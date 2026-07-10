"""Tests for ContentWriter. Mocks LLM via respx."""
import httpx
import pytest
import respx
from httpx import Response

from app.core.config import Settings
from app.domain.generator.content_writer import ContentWriter


@pytest.fixture
def settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        llm_call_timeout_s=10,
    )


@pytest.fixture
def writer(settings: Settings) -> ContentWriter:
    return ContentWriter(settings)


class TestTitleExtraction:
    def test_extracts_h1_title(self, writer: ContentWriter) -> None:
        text = "# 真实标题\n\n内容。"
        title = writer._extract_title(text)
        assert title == "真实标题"

    def test_returns_fallback_for_no_h1(self, writer: ContentWriter) -> None:
        text = "没有标题的内容"
        title = writer._extract_title(text)
        assert title.startswith("未命名") or len(title) > 0

    def test_handles_markdown_prefix(self, writer: ContentWriter) -> None:
        text = "  #  标题带空格  \n\n内容"
        title = writer._extract_title(text)
        assert title == "标题带空格"


@pytest.mark.asyncio
@respx.mock
async def test_write_article_calls_llm(writer: ContentWriter) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "# 我的文章\n\n这是内容。"}}
                ]
            },
        )
    )

    title, content = await writer.write_article(
        brand="Brand",
        topic="Topic",
        keywords=["k1"],
        style="neutral",
        target_length=500,
        chunks=[],
    )
    assert title == "我的文章"
    assert "这是内容" in content


@pytest.mark.asyncio
@respx.mock
async def test_write_article_handles_timeout(writer: ContentWriter) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    title, content = await writer.write_article(
        brand=None, topic="Topic", keywords=[],
        style="neutral", target_length=500, chunks=[],
    )
    # On failure, returns fallback title + empty content
    assert title is not None
    assert content == ""


@pytest.mark.asyncio
@respx.mock
async def test_write_article_handles_400(writer: ContentWriter) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(400, json={"error": "bad key"})
    )

    title, content = await writer.write_article(
        brand=None, topic="Topic", keywords=[],
        style="neutral", target_length=500, chunks=[],
    )
    assert content == ""
    assert title is not None
