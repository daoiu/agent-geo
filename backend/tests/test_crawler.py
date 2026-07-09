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


class TestSchemaExtraction:
    def test_extracts_organization_schema(self) -> None:
        from app.domain.crawler import Crawler
        html = '''
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Organization", "name": "Acme"}
        </script>
        </head><body></body></html>
        '''
        result = Crawler.extract_schema_coverage(html)
        assert result.has_organization is True
        assert "Organization" in result.detected_schemas

    def test_no_schemas_detected(self) -> None:
        from app.domain.crawler import Crawler
        html = "<html><body>plain</body></html>"
        result = Crawler.extract_schema_coverage(html)
        assert result.has_organization is False
        assert result.detected_schemas == []


class TestStructureExtraction:
    def test_single_h1_is_valid(self) -> None:
        from app.domain.crawler import Crawler
        html = "<h1>Title</h1><h2>S1</h2><h3>Sub</h3><p>Text.</p>"
        score = Crawler.extract_structure(html)
        assert score.h1_count_ok is True
        assert score.heading_hierarchy_valid is True

    def test_multiple_h1_invalid(self) -> None:
        from app.domain.crawler import Crawler
        html = "<h1>A</h1><h1>B</h1>"
        score = Crawler.extract_structure(html)
        assert score.h1_count_ok is False


class TestEeatExtraction:
    def test_detects_contact_and_about_links(self) -> None:
        from app.domain.crawler import Crawler
        html = '<a href="/about">About</a><a href="/contact">Contact</a>'
        result = Crawler.extract_eeat_signals(html, "https://example.com")
        assert result.has_about_page is True
        assert result.has_contact_page is True


class TestAiBotWhitelist:
    def test_open_bots_allowed_when_no_robots_txt(self) -> None:
        from app.domain.crawler import Crawler
        result = Crawler.check_ai_bot_whitelist(None)
        # By default (no robots.txt), all bots allowed
        assert result["GPTBot"] is True
        assert result["ClaudeBot"] is True

    def test_specific_bot_disallow(self) -> None:
        from app.domain.crawler import Crawler
        robots = """
User-agent: GPTBot
Disallow: /

User-agent: *
Allow: /
"""
        result = Crawler.check_ai_bot_whitelist(robots)
        assert result["GPTBot"] is False
        # * applies to unspecified bots including ClaudeBot
        assert result["ClaudeBot"] is True

    def test_explicit_allow(self) -> None:
        from app.domain.crawler import Crawler
        robots = """
User-agent: ClaudeBot
Allow: /
"""
        result = Crawler.check_ai_bot_whitelist(robots)
        assert result["ClaudeBot"] is True
