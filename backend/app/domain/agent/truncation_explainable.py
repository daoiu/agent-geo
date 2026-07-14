"""截断决策可解释(P2#36 / Task 44)。

把截断过程透明化:返回的 TruncationResult 含:
- kept / dropped / truncated 消息列表
- 每条消息的处理决策(action + reason)
- 总 token 节省
- 使用的策略

设计:
- truncate_explainable(messages, token_budget, token_counter) -> TruncationResult
- token_counter: Callable[[str], int] - 注入式 token 计数(便于单测用 mock)
- strategy: 描述采取的策略组合(window / summarize / drop / truncate)

策略:
1. 预算够 → 不动 (strategy="noop")
2. 预算不够 → 优先 drop 旧 user/assistant 消息
3. 还不够 → 截断大 tool 结果(保留最近 N 个 tool 结果不动)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class TruncationResult:
    __test__ = False  # 防止 pytest 收集

    kept_messages: list[dict]
    dropped_messages: list[dict] = field(default_factory=list)
    truncated_messages: list[dict] = field(default_factory=list)
    original_token_count: int = 0
    final_token_count: int = 0
    tokens_saved: int = 0
    strategy: str = "noop"
    decisions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "kept_count": len(self.kept_messages),
            "dropped_count": len(self.dropped_messages),
            "truncated_count": len(self.truncated_messages),
            "original_token_count": self.original_token_count,
            "final_token_count": self.final_token_count,
            "tokens_saved": self.tokens_saved,
            "strategy": self.strategy,
            "decisions": self.decisions,
        }


def _count_message_tokens(msg: dict, token_counter: Callable[[str], int]) -> int:
    """估算单条消息的 token 数(简化:对 content 计数 + 4 角色 overhead)。"""
    content = msg.get("content", "")
    if isinstance(content, str):
        return token_counter(content) + 4
    return 0


def truncate_explainable(
    messages: list[dict],
    token_budget: int,
    token_counter: Callable[[str], int],
    tool_result_token_cap: int = 800,
    tool_result_keep_recent: int = 3,
) -> TruncationResult:
    """截断消息列表,返回含决策的 TruncationResult。

    策略:
    1. 原始 token 数
    2. tool 结果(保留最近 N 个)超过 cap 的截断
    3. 还超 budget 则 FIFO drop 旧 user/assistant
    """
    original_token = sum(_count_message_tokens(m, token_counter) for m in messages)

    kept: list[dict] = []
    dropped: list[dict] = []
    truncated: list[dict] = []
    decisions: list[dict] = []

    # 1) 先处理 tool 结果(只截断旧的,保留最近 N 个)
    tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    recent_tool_set = set(tool_indices[-tool_result_keep_recent:]) if tool_indices else set()

    strategy_parts: list[str] = []
    for i, msg in enumerate(messages):
        msg_id = msg.get("id", f"msg-{i}")
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "tool" and i not in recent_tool_set:
            # 旧 tool 结果,可能需要截断
            tokens = _count_message_tokens(msg, token_counter)
            if tokens > tool_result_token_cap:
                # 截断
                ratio = tool_result_token_cap / tokens
                cut = max(1, int(len(content) * ratio))
                truncated_msg = {**msg, "content": content[:cut] + "...[truncated]"}
                truncated.append(truncated_msg)
                kept.append(truncated_msg)
                decisions.append({
                    "message_id": msg_id,
                    "action": "truncated",
                    "reason": f"tool result > {tool_result_token_cap} tokens ({tokens})",
                    "original_tokens": tokens,
                    "kept_tokens": tool_result_token_cap,
                })
                strategy_parts.append("truncate")
                continue
        kept.append(msg)
        decisions.append({
            "message_id": msg_id,
            "action": "kept",
            "reason": "within budget" if role != "tool" else "recent tool result",
        })

    # 2) 现在算 kept 的 token,如果还超 budget 则 drop 旧消息
    final_token = sum(_count_message_tokens(m, token_counter) for m in kept)
    if final_token > token_budget:
        # FIFO drop 旧 user/assistant 消息(不动 tool)
        new_kept: list[dict] = []
        to_drop_from_kept: list[dict] = []
        for i, msg in enumerate(kept):
            if msg.get("role") in ("user", "assistant"):
                # 候选 drop
                if final_token > token_budget:
                    to_drop_from_kept.append(msg)
                    final_token -= _count_message_tokens(msg, token_counter)
                    strategy_parts.append("drop")
                    continue
            new_kept.append(msg)
        # 更新 decisions
        dropped_ids = {m.get("id") for m in to_drop_from_kept}
        for d in decisions:
            if d["message_id"] in dropped_ids and d["action"] == "kept":
                d["action"] = "dropped"
                d["reason"] = "over token budget (FIFO)"
        # 重新整理 kept / dropped
        kept = new_kept
        dropped.extend(to_drop_from_kept)

    strategy = "+".join(set(strategy_parts)) if strategy_parts else "noop"

    return TruncationResult(
        kept_messages=kept,
        dropped_messages=dropped,
        truncated_messages=truncated,
        original_token_count=original_token,
        final_token_count=final_token,
        tokens_saved=original_token - final_token,
        strategy=strategy,
        decisions=decisions,
    )


__all__ = [
    "TruncationResult",
    "truncate_explainable",
]