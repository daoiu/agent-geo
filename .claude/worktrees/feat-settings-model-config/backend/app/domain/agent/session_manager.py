"""v0.4 会话管理辅助函数：标题自动生成等。"""
from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.domain.llm_client import LLMClient

logger = structlog.get_logger()

_MAX_TITLE_LENGTH = 20


async def auto_generate_title(first_user_message: str) -> str:
    """用 LLM 从首条 user 消息提取短标题。

    返回最长 20 字符的标题。LLM 失败时 fallback 到消息截断。

    Args:
        first_user_message: 用户首条消息原文。

    Returns:
        不超过 20 字符的标题字符串。
    """
    settings = get_settings()
    fallback = first_user_message[:_MAX_TITLE_LENGTH]

    try:
        llm = LLMClient(settings)
        response = await llm.simple_chat(
            prompt=(
                "请从以下用户消息中提取一个不超过 15 字的对话标题。"
                "只输出标题本身，不要其他内容、标点或引号：\n\n"
                f"{first_user_message[:200]}"
            )
        )
        title = response.strip()[:_MAX_TITLE_LENGTH]
        return title if title else fallback
    except Exception as e:  # noqa: BLE001
        logger.warning("auto_generate_title_failed", error=str(e))
        return fallback