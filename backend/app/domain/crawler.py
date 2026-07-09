"""Async web crawler for homepage + robots.txt + sitemap."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from app.core.config import Settings

logger = structlog.get_logger()


@dataclass
class CrawlerResult:
    """Result of fetching a single URL."""

    url: str
    success: bool
    status_code: int | None
    html: str
    elapsed_ms: int | None
    error: str | None = None


class Crawler:
    """Async HTTP fetcher with timeout + UA."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (compatible; GEO-Agent/0.1; +https://example.com/bot)"
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.settings.crawl_timeout_s,
                follow_redirects=True,
                headers={"User-Agent": self.DEFAULT_USER_AGENT},
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch(self, url: str) -> CrawlerResult:
        """Fetch a URL, returning success/failure + html or error."""
        client = self._get_client()
        try:
            response = await client.get(url)
            elapsed_ms = int(response.elapsed.total_seconds() * 1000)
            if response.status_code >= 400:
                return CrawlerResult(
                    url=url,
                    success=False,
                    status_code=response.status_code,
                    html="",
                    elapsed_ms=elapsed_ms,
                    error=f"HTTP {response.status_code}",
                )
            return CrawlerResult(
                url=url,
                success=True,
                status_code=response.status_code,
                html=response.text,
                elapsed_ms=elapsed_ms,
            )
        except httpx.TimeoutException:
            return CrawlerResult(
                url=url, success=False, status_code=None,
                html="", elapsed_ms=None, error="timeout",
            )
        except httpx.HTTPError as e:
            return CrawlerResult(
                url=url, success=False, status_code=None,
                html="", elapsed_ms=None, error=f"{type(e).__name__}: {e}",
            )

    async def fetch_robots_txt(self, base_url: str) -> str | None:
        """Fetch /robots.txt. Returns text or None on 404/error."""
        parsed = urlparse(base_url)
        robots_url = urljoin(base_url, "/robots.txt")
        result = await self.fetch(robots_url)
        if not result.success:
            return None
        return result.html
