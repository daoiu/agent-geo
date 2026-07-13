"""LLM client — pluggable OpenAI-compatible providers.

Providers are **discovered automatically** from environment variables:

    <NAME>_API_KEY=<key>             # required to register <name>
    <NAME>_BASE_URL=<url>            # optional, defaults to OpenAI
    <NAME>_MODEL=<model-name>        # optional, defaults to a sensible value

Set ``LLM_PROVIDERS=foo,bar,baz`` to declare which providers are active.
Any name with an ``<NAME>_API_KEY`` env var becomes available; ordering
follows ``LLM_PROVIDERS`` so the first one is the agent's primary.

Examples for one-off providers:

    DEEPSEEK_API_KEY=sk-...
    DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
    DEEPSEEK_MODEL=deepseek-chat
    LLM_PROVIDERS=deepseek

    MINIMAX_API_KEY=eyJ...
    MINIMAX_BASE_URL=https://api.minimaxi.com/v1
    MINIMAX_MODEL=MiniMax-M2.7
    LLM_PROVIDERS=minimax          # now `chat_with_tools` uses minimax
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from dotenv import dotenv_values
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import Settings
from app.domain.exceptions import LlmError
from app.models.schemas import MentionResult

logger = structlog.get_logger()

# Project root: backend/app/domain/llm_client.py → 3 parents up.
# Matches backend/app/core/config.py so we read the same .env file.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PROJECT_ENV_FILE = _PROJECT_ROOT / ".env"
_DELIMITER_RE = re.compile(r"^[A-Z][A-Z0-9_]*_API_KEY$")
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"


class _ProviderConfig(BaseModel):
    """Per-provider config resolved from env + Settings."""

    api_key: str
    base_url: str
    model: str


def _extract_usage(response) -> dict | None:
    """从 OpenAI 兼容响应提取 token usage;provider 不返回时 None。"""
    u = getattr(response, "usage", None)
    if u is None:
        return None
    return {
        "prompt_tokens": getattr(u, "prompt_tokens", None),
        "completion_tokens": getattr(u, "completion_tokens", None),
        "total_tokens": getattr(u, "total_tokens", None),
    }


def _normalize_base_url(url: str) -> str:
    """Auto-append ``/v1`` when the user supplied a bare host.

    OpenAI / DeepSeek / Kimi / MiniMax / OpenRouter all expose chat
    completions under ``<host>/v1/chat/completions``. Forgetting the
    trailing path produces a 404 because nginx (or the provider's edge)
    has no route at the bare root.
    """
    if not url:
        return url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return url
    if parsed.path in ("", "/"):
        return url.rstrip("/") + "/v1"
    return url


def _load_env_values() -> dict[str, str]:
    """Merge .env file values with the live process env. Process env wins."""
    values: dict[str, str] = {}
    if _PROJECT_ENV_FILE.exists():
        values.update({k: v for k, v in dotenv_values(_PROJECT_ENV_FILE).items() if v is not None})
    values.update({k: v for k, v in os.environ.items()})
    return values


def _provider_from_env(values: dict[str, str]) -> dict[str, _ProviderConfig]:
    """Scan env for ``<X>_API_KEY`` entries and build a provider map."""
    providers: dict[str, _ProviderConfig] = {}
    for key, value in values.items():
        if not _DELIMITER_RE.match(key):
            continue
        if not value:
            continue
        prefix = key[: -len("_API_KEY")]
        name = prefix.lower()
        base_url = _normalize_base_url(values.get(f"{prefix}_BASE_URL", "") or _DEFAULT_BASE_URL)
        model = values.get(f"{prefix}_MODEL") or _DEFAULT_MODEL
        providers[name] = _ProviderConfig(
            api_key=value, base_url=base_url, model=model
        )
    return providers


def _build_provider_map(settings: Settings) -> dict[str, _ProviderConfig]:
    """Resolve providers from env; back-fill any legacy Settings fields."""
    providers = _provider_from_env(_load_env_values())

    # Legacy fields kept for tests that construct Settings(deepseek_*=...).
    # If the legacy key is non-empty and the env didn't already register it,
    # we still want the test path to reach LLMClient.query_single(...).
    if "deepseek" not in providers and settings.deepseek_api_key:
        providers["deepseek"] = _ProviderConfig(
            api_key=settings.deepseek_api_key,
            base_url=_normalize_base_url(settings.deepseek_base_url),
            model=settings.deepseek_model,
        )
    if "kimi" not in providers and settings.kimi_api_key:
        providers["kimi"] = _ProviderConfig(
            api_key=settings.kimi_api_key,
            base_url=_normalize_base_url(settings.kimi_base_url),
            model=settings.kimi_model,
        )
    return providers


class LLMClient:
    """Async client supporting multiple OpenAI-compatible providers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._providers = _build_provider_map(settings)

    def has_provider(self, name: str) -> bool:
        return name in self._providers

    @property
    def available_providers(self) -> list[str]:
        return list(self._providers.keys())

    def primary_provider_name(self) -> str:
        """First enabled provider that the client actually has a config for.

        Falls back to the first provider with a registered config when the
        user's ``LLM_PROVIDERS`` list references names we have no key for,
        so the wrong-named variable in env doesn't crash the agent.
        """
        for name in self.settings.enabled_providers:
            if name in self._providers:
                return name
        # No overlap: prefer the first provider that actually has a key
        if self._providers:
            return next(iter(self._providers))
        return "deepseek"

    def _make_async_client(self, cfg: _ProviderConfig) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout=self.settings.llm_call_timeout_s,
        )

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
        primary_name = self.primary_provider_name()
        cfg = self._providers.get(primary_name)
        if cfg is None:
            raise LlmError(
                provider=primary_name,
                message=f"no provider config registered for '{primary_name}'",
                retryable=False,
            )
        client = self._make_async_client(cfg)
        response = await client.chat.completions.create(
            model=cfg.model,
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
            "usage": _extract_usage(response),
        }

    async def simple_chat(self, prompt: str) -> str:
        """简单文本聊天（无工具）。返回 assistant 的内容。

        用于 v0.4 自动生成标题等轻量场景。
        """
        primary_name = self.primary_provider_name()
        cfg = self._providers.get(primary_name)
        if cfg is None:
            raise LlmError(
                provider=primary_name,
                message=f"no provider config registered for '{primary_name}'",
                retryable=False,
            )
        client = self._make_async_client(cfg)
        response = await client.chat.completions.create(
            model=cfg.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        logger.info("simple_chat_usage", usage=_extract_usage(response))
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
