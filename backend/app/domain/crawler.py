"""Async web crawler for homepage + robots.txt + sitemap."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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

    # ---- Extraction methods (pure functions of html) ----

    @staticmethod
    def extract_schema_coverage(html: str) -> "SchemaCoverage":
        """Detect JSON-LD schema types in the page."""
        from app.models.schemas import SchemaCoverage

        detected: list[str] = []
        # Find all JSON-LD script blocks
        pattern = re.compile(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            try:
                data = json.loads(match.group(1))
                types = _extract_schema_types(data)
                detected.extend(types)
            except (json.JSONDecodeError, ValueError):
                continue

        detected = list(dict.fromkeys(detected))  # dedupe, preserve order
        return SchemaCoverage(
            has_organization="Organization" in detected,
            has_website="WebSite" in detected,
            has_faq="FAQPage" in detected,
            has_article="Article" in detected or "NewsArticle" in detected,
            has_breadcrumb="BreadcrumbList" in detected,
            has_product="Product" in detected,
            detected_schemas=detected,
        )

    @staticmethod
    def extract_eeat_signals(html: str, base_url: str) -> "EeatSignals":
        """Detect author bio, contact page, about page, etc."""
        from app.models.schemas import EeatSignals

        lowered = html.lower()
        has_author_bio = bool(re.search(r'class=["\'][^"\']*author[^"\']*["\']', lowered))
        has_contact = bool(re.search(r'href=["\'][^"\']*contact', lowered))
        has_about = bool(re.search(r'href=["\'][^"\']*(about|关于)', lowered))
        return EeatSignals(
            has_author_bio=has_author_bio,
            has_contact_page=has_contact,
            has_about_page=has_about,
            third_party_mentions=0,  # computed later via backlink analysis
            has_expert_attribution=has_author_bio,
        )

    @staticmethod
    def extract_structure(html: str) -> "StructureScore":
        """Score heading hierarchy + paragraph length."""
        from app.models.schemas import StructureScore

        h1_matches = re.findall(r"<h1[^>]*>", html, re.IGNORECASE)
        h2_matches = re.findall(r"<h2[^>]*>", html, re.IGNORECASE)
        h3_matches = re.findall(r"<h3[^>]*>", html, re.IGNORECASE)

        h1_ok = len(h1_matches) == 1
        # Hierarchy: at least one H2 if H3s exist
        hierarchy_valid = len(h3_matches) == 0 or len(h2_matches) >= 1

        has_lists = bool(re.search(r"<(ul|ol|table)[^>]*>", html, re.IGNORECASE))

        # Avg paragraph length (Chinese-aware via chars)
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL | re.IGNORECASE)
        if paragraphs:
            # Strip tags from paragraph content
            stripped = [re.sub(r"<[^>]+>", "", p) for p in paragraphs]
            avg_len = sum(len(p) for p in stripped) // max(len(stripped), 1)
        else:
            avg_len = 0

        # BLUF heuristic: first 30% of body has a "summary" sentence
        # For MVP, simple proxy: presence of a TL;DR / 简介 / 概述 keyword
        body_text = re.sub(r"<[^>]+>", "", html)[:1000]
        bluf_keywords = ["总结", "概述", "简介", "TL;DR", "Conclusion", "Summary"]
        bluf = 1.0 if any(kw in body_text for kw in bluf_keywords) else 0.5

        return StructureScore(
            h1_count_ok=h1_ok,
            heading_hierarchy_valid=hierarchy_valid,
            has_lists_or_tables=has_lists,
            avg_paragraph_length=avg_len,
            bluf_score=bluf,
        )

    @staticmethod
    def extract_freshness(
        html: str, last_modified_header: str | None
    ) -> "FreshnessScore":
        """Score content freshness from headers + meta tags."""
        from datetime import datetime, timezone, timedelta

        from app.models.schemas import FreshnessScore

        last_modified = _parse_http_date(last_modified_header)

        # Try to find datePublished in JSON-LD
        match = re.search(
            r'"datePublished"\s*:\s*"([^"]+)"', html, re.IGNORECASE
        )
        if match and last_modified is None:
            last_modified = _parse_iso8601(match.group(1))

        days_since = None
        if last_modified is not None:
            now = datetime.now(timezone.utc)
            days_since = max((now - last_modified).days, 0)

        has_publish_date = last_modified is not None
        recent_mention = bool(
            re.search(r"2024|2025|2026", html)
        )

        return FreshnessScore(
            last_modified=last_modified,
            days_since_update=days_since,
            has_publish_date=has_publish_date,
            has_recent_mention_in_content=recent_mention,
        )


def _extract_schema_types(data: object) -> list[str]:
    """Recursively collect @type values from a JSON-LD object/array."""
    types: list[str] = []
    if isinstance(data, dict):
        t = data.get("@type")
        if isinstance(t, str):
            types.append(t)
        elif isinstance(t, list):
            types.extend(t for t in t if isinstance(t, str))
        for v in data.values():
            if isinstance(v, (dict, list)):
                types.extend(_extract_schema_types(v))
    elif isinstance(data, list):
        for item in data:
            types.extend(_extract_schema_types(item))
    return types


def _parse_http_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _parse_iso8601(value: str) -> datetime | None:
    try:
        # Handle Z suffix
        v = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None
