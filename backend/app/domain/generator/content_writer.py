"""Content writer: orchestrates prompt building + LLM call + title extraction."""
from __future__ import annotations

import asyncio
import re

from openai import AsyncOpenAI

from app.core.config import Settings
from app.domain.generator.prompt_builder import build as build_prompt


class ContentWriter:
    """Generate one article per call. Uses the configured LLM provider."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _extract_title(content: str) -> str:
        """Extract H1 from Markdown content. Returns fallback if not found."""
        m = re.search(r"^#\s+(.+?)$", content, re.MULTILINE)
        if m:
            return m.group(1).strip()
        # Fallback: first non-empty line truncated
        for line in content.splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                return line[:60] or "未命名文章"
        return "未命名文章"

    async def write_article(
        self,
        brand: str | None,
        topic: str,
        keywords: list[str],
        style: str,
        target_length: int,
        chunks: list[dict],
    ) -> tuple[str, str]:
        """Generate one article. Returns (title, content).

        On LLM failure, returns (fallback_title, "") — caller should
        mark the article as errored.
        """
        prompt = build_prompt(
            brand=brand,
            topic=topic,
            keywords=keywords,
            style=style,
            target_length=target_length,
            chunks=chunks,
        )

        try:
            client = AsyncOpenAI(
                api_key=self.settings.deepseek_api_key,
                base_url=self.settings.deepseek_base_url,
                timeout=self.settings.llm_call_timeout_s,
            )
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.settings.deepseek_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                ),
                timeout=self.settings.llm_call_timeout_s,
            )
            content = response.choices[0].message.content or ""
            title = self._extract_title(content)
            return title, content
        except Exception:  # noqa: BLE001
            return self._extract_title(""), ""
