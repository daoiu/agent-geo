"""自适应压缩(P2#37 / Task 45)。

根据剩余 token 预算自动选择压缩策略:
- noop: 预算够,不处理
- truncate: 截断大 tool 结果(优先保留最近 N 个)
- drop: FIFO 丢旧 user/assistant 消息
- summarize: LLM 摘要旧消息为一段(占位小但信息密度高)

策略决策:
1. current_tokens <= budget → noop
2. truncate 后够(截断 tool 节省) → truncate
3. drop 后够(丢旧 user) → drop
4. 都不够 → summarize 旧消息

summarizer 是 async callable(str) -> str,默认 None 表示不可用,降级到 drop。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .truncation_explainable import _count_message_tokens, truncate_explainable


Summarizer = Callable[[str], Awaitable[str]]


@dataclass
class CompressionResult:
    __test__ = False

    messages: list[dict]
    strategy: str
    original_token_count: int
    final_token_count: int
    tokens_saved: int
    reason: str
    decisions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "original_token_count": self.original_token_count,
            "final_token_count": self.final_token_count,
            "tokens_saved": self.tokens_saved,
            "reason": self.reason,
            "decisions": self.decisions,
            "message_count": len(self.messages),
        }


def _decide_strategy(
    current_tokens: int,
    budget: int,
    has_old_msgs: bool,
    can_truncate: bool = True,
    can_summarize: bool = False,
) -> str:
    """决策策略选择(纯函数,便于单测)。

    优先级:
    1. noop - 预算够
    2. truncate - 大量超预算(优先廉价)
    3. summarize - 有 summarizer 且有旧消息(保信息)
    4. drop - 实在不行才丢
    """
    if current_tokens <= budget:
        return "noop"
    if can_truncate:
        return "truncate"
    if can_summarize and has_old_msgs:
        return "summarize"
    if has_old_msgs:
        return "drop"
    return "noop"  # 无法处理,返回原状


def _has_old_msgs(messages: list[dict]) -> bool:
    """检查是否有可被 drop/summarize 的旧 user/assistant 消息(至少 2 条)。"""
    cnt = sum(1 for m in messages if m.get("role") in ("user", "assistant"))
    return cnt >= 2


async def adaptive_compress(
    messages: list[dict],
    token_budget: int,
    token_counter: Callable[[str], int],
    summarizer: Summarizer | None = None,
    tool_result_token_cap: int = 800,
    tool_result_keep_recent: int = 3,
) -> CompressionResult:
    """自适应压缩入口。"""
    original_token = sum(_count_message_tokens(m, token_counter) for m in messages)

    strategy = _decide_strategy(
        current_tokens=original_token,
        budget=token_budget,
        has_old_msgs=_has_old_msgs(messages),
        can_truncate=True,
        can_summarize=summarizer is not None,
    )

    if strategy == "noop":
        return CompressionResult(
            messages=list(messages),
            strategy="noop",
            original_token_count=original_token,
            final_token_count=original_token,
            tokens_saved=0,
            reason="within budget, no compression needed",
        )

    if strategy == "truncate":
        # 用 truncate_explainable 处理
        trunc_result = truncate_explainable(
            messages,
            token_budget=token_budget,
            token_counter=token_counter,
            tool_result_token_cap=tool_result_token_cap,
            tool_result_keep_recent=tool_result_keep_recent,
        )
        return CompressionResult(
            messages=trunc_result.kept_messages,
            strategy=trunc_result.strategy,
            original_token_count=trunc_result.original_token_count,
            final_token_count=trunc_result.final_token_count,
            tokens_saved=trunc_result.tokens_saved,
            reason=f"tool results > {tool_result_token_cap} tokens, truncated",
            decisions=trunc_result.decisions,
        )

    if strategy == "drop":
        # FIFO drop 旧 user/assistant(保留最后一条 user)
        last_user_idx = max(
            (i for i, m in enumerate(messages) if m.get("role") == "user"),
            default=-1,
        )
        new_msgs: list[dict] = []
        cur_tokens = 0
        decisions: list[dict] = []
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            msg_tokens = _count_message_tokens(msg, token_counter)
            if cur_tokens + msg_tokens <= token_budget or i == last_user_idx:
                new_msgs.insert(0, msg)
                cur_tokens += msg_tokens
                decisions.append({"message_id": msg.get("id", f"msg-{i}"), "action": "kept", "reason": "within budget or last user"})
            else:
                decisions.append({"message_id": msg.get("id", f"msg-{i}"), "action": "dropped", "reason": "FIFO over budget"})
        return CompressionResult(
            messages=new_msgs,
            strategy="drop",
            original_token_count=original_token,
            final_token_count=cur_tokens,
            tokens_saved=original_token - cur_tokens,
            reason="FIFO drop old user/assistant messages",
            decisions=decisions,
        )

    # summarize
    if summarizer is None:
        # summarizer 不可用 → 降级到 drop
        return await adaptive_compress(
            messages, token_budget, token_counter,
            summarizer=None,  # 强制 drop
            tool_result_token_cap=tool_result_token_cap,
            tool_result_keep_recent=tool_result_keep_recent,
        )
    # 提取旧消息文本 → 调 LLM 摘要 → 替换为单条 assistant
    old_texts = [
        m.get("content", "") for m in messages
        if m.get("role") in ("user", "assistant")
    ]
    if not old_texts:
        return CompressionResult(
            messages=list(messages),
            strategy="noop",
            original_token_count=original_token,
            final_token_count=original_token,
            tokens_saved=0,
            reason="no old user/assistant to summarize",
        )
    summary_text = await summarizer("\n".join(old_texts[:20]))
    summary_msg = {
        "role": "assistant",
        "content": f"[之前的对话摘要]: {summary_text}",
        "_is_summary": True,
    }
    # 保留: [summary_msg] + 最后 1 个 user
    last_user = next(
        (m for m in reversed(messages) if m.get("role") == "user"),
        None,
    )
    new_msgs = [summary_msg]
    if last_user is not None:
        new_msgs.append(last_user)
    new_token = sum(_count_message_tokens(m, token_counter) for m in new_msgs)
    return CompressionResult(
        messages=new_msgs,
        strategy="summarize",
        original_token_count=original_token,
        final_token_count=new_token,
        tokens_saved=original_token - new_token,
        reason="summarized old user/assistant messages via LLM",
        decisions=[{"action": "summarized", "count": len(old_texts)}],
    )


__all__ = [
    "CompressionResult",
    "adaptive_compress",
]