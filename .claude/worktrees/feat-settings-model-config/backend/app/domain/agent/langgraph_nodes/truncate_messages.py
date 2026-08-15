"""v0.8 TruncateMessagesNode(spec §4.2.4 + §8.2/§8.3):4 策略自适应压缩 + token 截断可解释。

包既有 adaptive_compression.adaptive_compress(spec §4.2.4),不重写策略。
回流 state.truncation_result = CompressionResult.to_dict() 用于日志与 metrics。
LangChain BaseMessage 列表 → dict(因为 adaptive_compress 是 dict-style 输入)。
"""
from __future__ import annotations

from typing import TypedDict

# 默认 token budget:8K 用于中等上下文(pinned 未在 Settings,实际生产从 Settings 注入)
DEFAULT_TOKEN_BUDGET = 8000


def _lc_messages_to_dicts(messages: list) -> list[dict]:
    """LangChain BaseMessage / dict 混合 → dict-style(role/content)。"""
    out = []
    for m in messages:
        if isinstance(m, dict):
            out.append(m)
            continue
        role = getattr(m, "type", "user") or "user"
        # LangChain: type in {human, ai, system, tool}
        role_map = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}
        role = role_map.get(role, role)
        content = getattr(m, "content", "")
        if not isinstance(content, str):
            content = str(content)
        out.append({"role": role, "content": content})
    return out


def _dicts_to_lc_messages(dicts: list[dict]) -> list:
    """dict → LangChain BaseMessage(按原顺序映射 class,缺失 fallback HumanMessage)。"""
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )

    out = []
    for d in dicts:
        role = d.get("role", "user")
        content = d.get("content", "")
        cls = {
            "system": SystemMessage,
            "user": HumanMessage,
            "assistant": AIMessage,
            "tool": ToolMessage,
        }.get(role, HumanMessage)
        if cls is ToolMessage:
            out.append(cls(content=content, tool_call_id=d.get("tool_call_id", "t")))
        else:
            out.append(cls(content=content))
    return out


async def truncate_messages_node(state: TypedDict, runtime) -> dict:
    """4 策略自适应压缩 + 截断可解释回流。

    Returns:
        dict 含 `messages`(新 BaseMessage 列表)与 `truncation_result`(`CompressionResult.to_dict()`)
    """
    from app.domain.agent.adaptive_compression import adaptive_compress

    settings_budget = None
    try:
        from app.core.config import get_settings
        settings_budget = getattr(get_settings(), "context_token_budget", None)
    except Exception:  # noqa: BLE001
        pass
    token_budget = settings_budget or DEFAULT_TOKEN_BUDGET

    encoder = _get_encoder()
    if encoder is not None:
        def token_counter(s: str) -> int:
            return len(encoder.encode(s))
    else:
        # 字符级 fallback(避免主流程卡死)
        def token_counter(s: str) -> int:
            return len(s) // 4

    dict_messages = _lc_messages_to_dicts(state["messages"])
    result = await adaptive_compress(
        messages=dict_messages,
        token_budget=token_budget,
        token_counter=token_counter,
        summarizer=None,  # 不可用,T11 视情况启用
    )

    new_messages = _dicts_to_lc_messages(result.messages)

    return {
        "messages": new_messages,
        "truncation_result": result.to_dict(),
    }


def _get_encoder():
    """复用 react_loop 懒加载 tiktoken encoder(失败回退字符级)。"""
    try:
        from app.domain.agent.react_loop import _get_tiktoken_encoder
        return _get_tiktoken_encoder()
    except Exception:  # noqa: BLE001
        return None
