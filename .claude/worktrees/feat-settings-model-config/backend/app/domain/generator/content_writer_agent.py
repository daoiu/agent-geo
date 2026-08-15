"""ContentWriterAgent: 独立的内容生成 agent（system prompt + RAG chunks + 流式）。

设计定位：
- 与 ReAct agent 平级，但职责单一（只写文章，无工具调用）
- 持有自己的 system prompt（来自 system_prompts.build_content_writer_system_prompt）
- user prompt 由 prompt_builder.build_user_prompt 构造
- LLM 调用走独立 AsyncOpenAI 客户端（_normalize_base_url 自动补 /v1）
- 流式 yield 增量 chunks，调用方可决定是否需要增量落库

调用入口：
- 后台：task_worker._process_one 替换原 ContentWriter.write_article
- 实时：agent tool _execute_generate_article 后续可走这里

占位骨架：system prompt 是 v1，后续根据生成质量迭代。
"""
from __future__ import annotations

import asyncio
import re

import httpx
from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.config import Settings
from app.domain.generator.prompt_builder import build_user_prompt
from app.domain.generator.system_prompts import build_content_writer_system_prompt
from app.domain.llm_client import _normalize_base_url


# Exceptions that should be silently absorbed as "LLM failure" (caller
# marks article as errored). Programming errors propagate so we don't
# hide real bugs.
_LLM_TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    asyncio.TimeoutError,
    APITimeoutError,
    RateLimitError,
    APIError,
    httpx.HTTPError,
)


class ContentWriterAgent:
    """独立的内容生成 agent。

    与 ContentWriter 的本质区别：
    - 拥有独立的 system role 提示词（角色 / 风格 / 反编造 / 兜底规则）
    - 每次构造新客户端（与 worker 并发调用安全）
    - 支持流式 yield chunks
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _strip_think_blocks(content: str) -> str:
        """剥离 LLM 输出的 <think>...</think> 内部推理块。

        DeepSeek/MiniMax 等推理模型会在 reply 开头输出 <think>...，如果不剥，
        会把推理过程当正文存到 ArticleORM 里。匹配多行、跨行、带空白/换行。
        """
        if not content:
            return ""
        # 贪婪匹配非贪婪——一次性剥掉所有 think 块（可能多个）
        return re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL).lstrip()

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

    def _build_messages(
        self,
        brand: str | None,
        topic: str,
        keywords: list[str],
        style: str,
        target_length: int,
        chunks: list[dict],
    ) -> list[dict]:
        """组装 messages: [system, user]."""
        return [
            {
                "role": "system",
                "content": build_content_writer_system_prompt(brand=brand, style=style),
            },
            {
                "role": "user",
                "content": build_user_prompt(
                    topic=topic,
                    keywords=keywords,
                    target_length=target_length,
                    chunks=chunks,
                ),
            },
        ]

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

        On LLM transient failure (timeout, rate-limit, 5xx), returns
        (fallback_title, "") — caller should mark the article as errored.
        Programming errors propagate so they are not silently swallowed.

        与 ContentWriter.write_article 接口一致，便于替换。
        """
        messages = self._build_messages(
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
                base_url=_normalize_base_url(self.settings.deepseek_base_url),
            )
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.settings.deepseek_model,
                    messages=messages,
                    temperature=0.7,
                ),
                timeout=self.settings.llm_call_timeout_s,
            )
            content = self._strip_think_blocks(response.choices[0].message.content or "")
            title = self._extract_title(content)
            return title, content
        except _LLM_TRANSIENT_EXCEPTIONS:
            return self._extract_title(""), ""

    async def stream_article(
        self,
        brand: str | None,
        topic: str,
        keywords: list[str],
        style: str,
        target_length: int,
        chunks: list[dict],
    ):
        """流式生成：每收到一个 chunk 就 yield 增量字符串。

        Yields:
            str: 增量内容片段。调用方负责拼接。

        Raises:
            transient 异常在内部吞掉，yield 不到任何内容后通过空标题 + 空字符串
            表示失败（与 write_article 行为对齐）。
            programming error 透传。
        """
        messages = self._build_messages(
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
                base_url=_normalize_base_url(self.settings.deepseek_base_url),
            )
            stream = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.settings.deepseek_model,
                    messages=messages,
                    temperature=0.7,
                    stream=True,
                ),
                timeout=self.settings.llm_call_timeout_s,
            )
            # 状态机：think 块跨 chunk 边界时需缓冲
            # states: "before_think" → "in_think" → "after_think"
            buf = ""
            state = "before_think"
            THINK_START = "<think>"
            THINK_END = "</think>"
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if not delta:
                    continue
                buf += delta
                if state == "before_think":
                    idx = buf.find(THINK_START)
                    if idx == -1:
                        # 没遇到 <think>，但需要保留最近 7 字符（防止 <think> 跨 chunk 切到一半）
                        if len(buf) > len(THINK_START):
                            yield buf[: -len(THINK_START)]
                            buf = buf[-len(THINK_START):]
                    elif idx > 0:
                        yield buf[:idx]
                        buf = buf[idx:]
                        state = "in_think"
                    else:
                        state = "in_think"
                if state == "in_think":
                    end_idx = buf.find(THINK_END)
                    if end_idx != -1:
                        # 跳过 think 块，剩余部分进入 after_think
                        buf = buf[end_idx + len(THINK_END):].lstrip()
                        state = "after_think"
                        if buf:
                            yield buf
                            buf = ""
                    # else: 继续累积，等下一 chunk
                elif state == "after_think":
                    yield delta
            # 流结束时如果还在 think 状态（异常），丢弃 buf
            if state == "before_think" and buf:
                yield buf
        except _LLM_TRANSIENT_EXCEPTIONS:
            # transient：吞掉，调用方按"流结束但 content 为空"判定失败
            return
        # programming error 不 catch，向上抛