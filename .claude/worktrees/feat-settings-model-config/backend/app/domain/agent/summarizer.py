"""v0.6+ P1#12（Task 13）：窗口 + 摘要双层历史压缩。

策略：
- 窗口内（最近 N 条）消息保留原样
- 窗口外（更早）消息用 LLM 摘要成一段 compact digest
- 摘要作为额外的 system role 插入，紧跟主 system prompt 之后

设计动机：
- 字符截断 / token 截断 都会丢失语义；LLM 摘要保留意图但压缩 token
- 适合"长会话 + LLM 上下文窗口有限"的场景
- LLM 摘要失败用 placeholder 兜底，不阻塞主流程（transient 错误模式）
- 编程错误仍向上抛（不吞 bug）

注入式设计：HistorySummarizer 接受任意 LLM 客户端（duck-typed，
只需有 ``chat_with_tools`` 异步方法）。便于测试 mock + 未来换其他 LLM。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Protocol

import structlog

from app.domain.agent.react_loop import build_messages
from app.domain.exceptions import _LLM_TRANSIENT_EXCEPTIONS


logger = structlog.get_logger()


class _LLMClientLike(Protocol):
    """Summarizer 依赖的 LLM 客户端最小接口（duck typing）。"""
    async def chat_with_tools(self, messages, tools=None): ...  # noqa: ANN001


class HistorySummarizer:
    """窗口 + 摘要双层压缩器。"""

    def __init__(self, llm: _LLMClientLike, window_size: int) -> None:
        self.llm = llm
        self.window_size = window_size

    async def build_messages_with_summary(
        self,
        history: list[dict],
        memory_index_segment: str = "",
        *,
        window_messages: int | None = None,
        tool_result_max_chars: int | None = None,
        tool_result_keep_recent: int = 0,
        token_budget_per_tool_result: int | None = None,
    ) -> list[dict]:
        """构造 LLM 消息列表；窗口外消息先摘要，再插入主 system prompt 之后。

        - history <= 窗口：完全复用 build_messages，不调 LLM
        - history > 窗口：截取窗口外部分调用 LLM 摘要，组装最终消息列表
        """
        effective_window = (
            window_messages if window_messages is not None else self.window_size
        )

        # 快路径：无需摘要
        if effective_window is None or len(history) <= effective_window:
            return build_messages(
                history,
                memory_index_segment=memory_index_segment,
                window_messages=window_messages,
                tool_result_max_chars=tool_result_max_chars,
                tool_result_keep_recent=tool_result_keep_recent,
                token_budget_per_tool_result=token_budget_per_tool_result,
            )

        # 慢路径：拆 older + recent，对 older 做摘要
        # effective_window=0 边界:history[:-0] 返回 full list 而非空，需要特殊处理
        if effective_window > 0:
            older = history[:-effective_window]
            recent = history[-effective_window:]
        else:
            older = list(history)
            recent = []

        summary_text = await self._summarize(older)

        # 构造窗口内消息列表（不含主 system,build_messages 会注入主 system）
        recent_msgs = build_messages(
            recent,
            memory_index_segment="",  # memory_index_segment 由外层主 system 注入
            window_messages=None,    # recent 已是窗口切片，不再二次窗口化
            tool_result_max_chars=tool_result_max_chars,
            tool_result_keep_recent=tool_result_keep_recent,
            token_budget_per_tool_result=token_budget_per_tool_result,
        )

        # recent_msgs[0] 是主 system prompt；注入摘要作为第二条 system
        summary_msg = {
            "role": "system",
            "content": f"[历史摘要]\n{summary_text}",
        }
        # 保留主 system + 摘要 + 余下消息
        return [recent_msgs[0], summary_msg] + recent_msgs[1:]

    async def _summarize(self, messages: list[dict]) -> str:
        """用 LLM 把 messages 摘要成一段文本。

        失败兜底：
        - transient 异常（_LLM_TRANSIENT_EXCEPTIONS）→ 返回 placeholder
        - 编程错误 → 向上抛
        """
        if not messages:
            return ""

        text = _messages_to_text(messages)
        prompt = (
            "请将以下对话历史压缩为一段简洁摘要（保留关键事实、决策、用户偏好），"
            "不超过 200 字：\n\n" + text
        )

        try:
            response = await self.llm.chat_with_tools(
                messages=[{"role": "user", "content": prompt}],
                tools=None,
            )
        except _LLM_TRANSIENT_EXCEPTIONS as exc:
            # 不阻塞主流程，用占位符兜底
            logger.warning(
                "history_summary_fallback",
                error_type=type(exc).__name__,
                message=str(exc),
                n_messages=len(messages),
            )
            return f"[摘要失败: {len(messages)} 条消息,LLM 错误 {type(exc).__name__}]"

        content = (response or {}).get("content") or ""
        return content.strip() or f"[摘要为空: {len(messages)} 条消息]"


def _messages_to_text(messages: list[dict]) -> str:
    """把消息列表序列化为纯文本，供 LLM 摘要。"""
    lines: list[str] = []
    for m in messages:
        role = m.get("role", "unknown")
        content = m.get("content")
        if isinstance(content, str):
            lines.append(f"[{role}] {content}")
        else:
            # tool_calls / None content 等
            lines.append(f"[{role}] {json.dumps(m, ensure_ascii=False)[:200]}")
    return "\n".join(lines)