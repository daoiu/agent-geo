"""Tests for the web crawler. Uses unittest.mock.patch to mock HTTP calls."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import Settings
from app.domain.crawler import Crawler, CrawlerResult


@pytest.fixture
def settings() -> Settings:
    return Settings(crawl_timeout_s=5)


@pytest.fixture
def crawler(settings: Settings) -> Crawler:
    return Crawler(settings)


def _make_mock_response(status_code: int, text: str, elapsed_seconds: float = 0.1) -> MagicMock:
    """Create a mock httpx.Response with proper elapsed timing."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = status_code
    mock_response.text = text
    # elapsed is a timedelta in httpx
    mock_response.elapsed = timedelta(seconds=elapsed_seconds)
    return mock_response


@pytest.mark.asyncio
async def test_fetch_returns_html_on_success(crawler: Crawler) -> None:
    """Test that fetch returns HTML on successful HTTP response."""
    mock_response = _make_mock_response(200, "<html><body><h1>Hello</h1></body></html>")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch.object(crawler, "_get_client", return_value=mock_client):
        result = await crawler.fetch("https://example.com")

    assert result.success is True
    assert result.status_code == 200
    assert "<h1>Hello</h1>" in result.html
    assert result.url == "https://example.com"


@pytest.mark.asyncio
async def test_fetch_returns_failure_on_timeout(crawler: Crawler) -> None:
    """Test that fetch returns failure on timeout."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("connection timeout"))

    with patch.object(crawler, "_get_client", return_value=mock_client):
        result = await crawler.fetch("https://slow.example.com")

    assert result.success is False
    assert result.error is not None
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_fetch_robots_txt_returns_text_when_exists(crawler: Crawler) -> None:
    """Test that fetch_robots_txt returns text when robots.txt exists."""
    mock_response = _make_mock_response(200, "User-agent: *\nAllow: /")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch.object(crawler, "_get_client", return_value=mock_client):
        text = await crawler.fetch_robots_txt("https://example.com")

    assert text is not None
    assert "User-agent" in text


@pytest.mark.asyncio
async def test_fetch_robots_txt_returns_none_on_404(crawler: Crawler) -> None:
    """Test that fetch_robots_txt returns None when robots.txt returns 404."""
    mock_response = _make_mock_response(404, "Not Found")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch.object(crawler, "_get_client", return_value=mock_client):
        text = await crawler.fetch_robots_txt("https://example.com")

    assert text is None
