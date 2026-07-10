"""LLM client — DeepSeek + Kimi via OpenAI-compatible API.

Each provider is selected at runtime via Settings.enabled_providers.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import Settings
from app.domain.exceptions import LlmError
from app.models.schemas import MentionResult

logger = structlog.get_logger()


class _ProviderConfig(BaseModel):
    """Per-provider config resolved from Settings."""

    api_key: str
    base_url: str
    model: str


def _build_provider_map(settings: Settings) -> dict[str, _ProviderConfig]:
    return {
        "deepseek": _ProviderConfig(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        ),
        "kimi": _ProviderConfig(
            api_key=settings.kimi_api_key,
            base_url=settings.kimi_base_url,
            model=settings.kimi_model,
        ),
    }


class LLMClient:
    """Async client supporting multiple OpenAI-compatible providers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._providers = _build_provider_map(settings)

    def _make_async_client(self, cfg: _ProviderConfig) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout=self.settings.llm_call_timeout_s,
        )

    async def query_single(
        self,
        provider: str,
        question: str,
        brand: str,
        industry: str,
        max_retries: int = 1,
    ) -> MentionResult:
        """Query one provider with one question. Returns MentionResult.

        On failure, retries up to max_retries times. Returns a
        MentionResult with `error` set rather than raising.
        """
        cfg = self._providers.get(provider)
        if cfg is None:
            return MentionResult(
                question=question,
                llm_provider=provider,
                llm_answer="",
                brand_mentioned=False,
                error=f"unknown provider: {provider}",
            )

        prompt = self._build_prompt(question, brand, industry)
        last_error: str | None = None

        for attempt in range(max_retries + 1):
            try:
                client = self._make_async_client(cfg)
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=cfg.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                    ),
                    timeout=self.settings.llm_call_timeout_s,
                )
                answer = response.choices[0].message.content or ""
                return self._parse_answer(question, provider, brand, answer)

            except asyncio.TimeoutError:
                last_error = "timeout"
                logger.warning("llm_timeout", provider=provider, attempt=attempt)
            except LlmError as e:
                last_error = str(e)
                if not e.retryable:
                    break
                logger.warning("llm_error", provider=provider, attempt=attempt, error=e)
            except (httpx.HTTPError, Exception) as e:  # noqa: BLE001
                last_error = f"{type(e).__name__}: {e}"
                logger.warning(
                    "llm_unexpected", provider=provider, attempt=attempt, error=last_error
                )

        return MentionResult(
            question=question,
            llm_provider=provider,
            llm_answer="",
            brand_mentioned=False,
            sentiment="neutral",
            error=last_error,
        )

    async def query_mentions(
        self,
        brand: str,
        industry: str,
        questions: list[str],
        providers: list[str] | None = None,
    ) -> list[MentionResult]:
        """Query all (provider x question) pairs in parallel."""
        active = providers or self.settings.enabled_providers
        tasks: list[asyncio.Task[MentionResult]] = []
        for provider in active:
            for question in questions:
                tasks.append(
                    asyncio.create_task(
                        self.query_single(provider, question, brand, industry)
                    )
                )
        return await asyncio.gather(*tasks)

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> dict:
        """Call LLM with tool use (OpenAI-compatible Function Calling).

        Returns:
            {
                "content": str | None,         # assistant 的文字内容
                "tool_calls": list[dict] | None,  # [{id, function: {name, arguments}}, ...]
            }
        """
        client = self._make_async_client(self._providers["deepseek"])
        response = await client.chat.completions.create(
            model=self.settings.deepseek_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.7,
        )
        message = response.choices[0].message
        tool_calls: list[dict] | None = None
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        return {
            "content": message.content,
            "tool_calls": tool_calls,
        }

    async def simple_chat(self, prompt: str) -> str:
        """简单文本聊天（无工具）。返回 assistant 的内容。

        用于 v0.4 自动生成标题等轻量场景。
        """
        client = self._make_async_client(self._providers["deepseek"])
        response = await client.chat.completions.create(
            model=self.settings.deepseek_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def _build_prompt(question: str, brand: str, industry: str) -> str:
        return (
            f"请像回答用户提问一样回答：\"{question}\"\n"
            f"如果答案涉及 {industry} 行业的产品/品牌/服务，"
            f"请在合适位置提到\"{brand}\"品牌（如果相关）。\n"
            f"只输出答案文本，不要额外说明。"
        )

    @staticmethod
    def _parse_answer(
        question: str, provider: str, brand: str, answer: str
    ) -> MentionResult:
        """Detect brand mention and its position in the answer."""
        mentioned, position = _detect_mention(answer, brand)
        return MentionResult(
            question=question,
            llm_provider=provider,
            llm_answer=answer,
            brand_mentioned=mentioned,
            mention_position=position,
            sentiment="neutral",  # sentiment handled in a later task
        )


def _detect_mention(text: str, brand: str) -> tuple[bool, int | None]:
    """Return (mentioned, 1-based position) for the brand in text."""
    if not brand:
        return False, None
    # Naive substring match; brand names containing regex metachars are
    # escaped. Sentence-based position counter.
    sentences = re.split(r"[.。！？\n]+", text)
    for idx, sentence in enumerate(sentences, start=1):
        if not sentence.strip():
            continue
        if re.search(re.escape(brand), sentence):
            return True, idx
    return False, None
