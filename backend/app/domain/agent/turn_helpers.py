"""agent 共享纯函数模块(zero-behavior-change 抽取自 react_loop.py)。

抽离目的:让 LangGraph 路径与原 react_loop 路径共用同一份消息构造 / 记忆拼接 /
metrics 聚合逻辑,保证两路径行为字节级对齐(对外 8 类 SSE 事件、HITL、降级语义不变)。

v0.6 P1.6 — L2 跨会话偏好:
- ``build_messages`` 接受 ``memory_index_segment``,拼到 system 末尾
- ``_apply_memory_prepend`` 在每个 LLM call 前把相关记忆 prepended 到 user 消息

v0.6+ P1#11(Task 12):tiktoken 编码器懒加载缓存。
v0.6+ P1#22(Task 24):``_emit_metrics`` 增加 turn_duration_ms + cost_usd。
"""
from __future__ import annotations

import json
from decimal import Decimal

import structlog

from app.core.config import get_settings
from app.domain.agent.prompts import AGENT_SYSTEM_PROMPT
from app.models.orm_v04 import AgentMessageORM

logger = structlog.get_logger()

# v0.6+ P1#11(Task 12):tiktoken 编码器懒加载缓存。None 表示未初始化。
_TIKTOKEN_ENCODER: object | None = None
_TIKTOKEN_ENCODING_NAME: str | None = None


def _get_tiktoken_encoder(encoding_name: str | None = None):
    """懒加载 tiktoken 编码器(v0.6+ P1#11 / Task 12)。

    缓存于模块级单例。encoding_name 为 None 时使用 Settings.tiktoken_encoding。
    失败时返回 None(让调用方回退到字符级截断,不阻塞主流程)。
    """
    global _TIKTOKEN_ENCODER, _TIKTOKEN_ENCODING_NAME
    name = encoding_name or get_settings().tiktoken_encoding
    if _TIKTOKEN_ENCODER is not None and _TIKTOKEN_ENCODING_NAME == name:
        return _TIKTOKEN_ENCODER
    try:
        import tiktoken
        enc = tiktoken.get_encoding(name)
        _TIKTOKEN_ENCODER = enc
        _TIKTOKEN_ENCODING_NAME = name
        return enc
    except Exception as exc:  # noqa: BLE001
        logger.warning("tiktoken_load_failed", encoding_name=name, error=str(exc))
        return None


def _truncate_by_tokens(content: str, max_tokens: int, encoder) -> str:
    """按 token 数截断字符串(保留前 max_tokens 个 token)。

    encoder 为 None 时直接返回原 content(回退到字符级)。
    """
    if encoder is None:
        return content
    tokens = encoder.encode(content)
    if len(tokens) <= max_tokens:
        return content
    # decode 前 N 个 token(可能有尾部空格,需 strip)
    truncated = encoder.decode(tokens[:max_tokens]).rstrip()
    return truncated + "…(truncated)"


def build_messages(
    history: list[dict],
    memory_index_segment: str = "",
    *,
    window_messages: int | None = None,
    tool_result_max_chars: int | None = None,
    tool_result_keep_recent: int = 0,
    token_budget_per_tool_result: int | None = None,
) -> list[dict]:
    """把 DB 风格历史转换为 OpenAI chat completion 协议格式。

    输入 history 元素格式:
      {"role": "user"|"assistant"|"tool"|"system", "content": str|None, ...}

    特殊处理:
    - assistant 消息的 tool_calls.arguments 必须是 JSON **字符串**(OpenAI 协议要求,
      DB 也以字符串存储);这里原样透传,dict 则序列化回字符串,绝不发对象。
    - tool 消息必须带 tool_call_id(OpenAI 协议要求)
    - **配对保证**:只保留有对应 tool 结果的 tool_call;丢弃 dangling 的
      (HumanConfirmation / 被中断的流会留下无结果的 tool_call),并跳过孤儿 tool
      结果。否则严格 provider 报 'tool call result does not follow tool call' 400。
    - 系统 prompt 总是作为第一条注入
    - v0.6 P1.6:``memory_index_segment``(L2 索引段)拼到系统 prompt 末尾,
      仅常量部分参与 prompt cache,索引内容改变不需要重建整段 system
    """
    # Phase 3 ①滑动窗口:先裁,配对计算基于窗口后的历史(切断的一侧由 kept_ids 丢弃)
    if window_messages is not None and len(history) > window_messages:
        history = history[-window_messages:]

    # Phase 3 ③截断预算:最近 keep_recent 个 tool 结果保全量,其余超长截断
    tool_positions = [i for i, m in enumerate(history) if m.get("role") == "tool"]
    if tool_result_keep_recent > 0:
        keep_full = set(tool_positions[-tool_result_keep_recent:])
    else:
        keep_full = set()

    # 先扫出「已有结果」的 tool_call_id(存在对应 tool 消息)与「被 assistant 声明」的
    # tool_call_id;只有两者交集(kept_ids)才是可安全重放的配对。
    resolved_ids: set[str] = {
        msg["tool_call_id"]
        for msg in history
        if msg.get("role") == "tool" and msg.get("tool_call_id")
    }
    declared_ids: set[str] = set()
    for msg in history:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tc_raw = msg["tool_calls"]
            if isinstance(tc_raw, str):
                tc_raw = json.loads(tc_raw)
            for tc in tc_raw:
                if tc.get("id"):
                    declared_ids.add(tc["id"])
    kept_ids = resolved_ids & declared_ids

    out: list[dict] = [{
        "role": "system",
        "content": AGENT_SYSTEM_PROMPT + memory_index_segment,
    }]

    for idx, msg in enumerate(history):
        role = msg["role"]
        if role == "user":
            out.append({"role": "user", "content": msg["content"]})
        elif role == "assistant":
            asst: dict = {"role": "assistant", "content": msg.get("content")}
            if msg.get("tool_calls"):
                tc_raw = msg["tool_calls"]
                if isinstance(tc_raw, str):
                    tc_raw = json.loads(tc_raw)
                # 兼容两种格式:
                # 1. OpenAI 风格:{id, function: {name, arguments}}
                # 2. 简化风格:{tool, arguments}
                normalized = []
                for tc in tc_raw:
                    tc_id = tc.get("id", "")
                    # 只保留有对应 tool 结果的 call,避免 dangling tool_call
                    if tc_id not in kept_ids:
                        continue
                    if "function" in tc:
                        args = tc["function"]["arguments"]
                        normalized.append({
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": args
                                if isinstance(args, str)
                                else json.dumps(args, ensure_ascii=False),
                            },
                        })
                    elif "tool" in tc:
                        # 简化风格 → 转换为 OpenAI 风格
                        sargs = tc["arguments"]
                        normalized.append({
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc["tool"],
                                "arguments": sargs
                                if isinstance(sargs, str)
                                else json.dumps(sargs, ensure_ascii=False),
                            },
                        })
                if normalized:
                    asst["tool_calls"] = normalized
            # 跳过既无内容又无有效 tool_calls 的空 assistant(dangling 丢弃后可能出现)
            if asst.get("content") or asst.get("tool_calls"):
                out.append(asst)
        elif role == "tool":
            # 只发能对上 assistant tool_call 的结果;孤儿 tool 跳过
            if msg.get("tool_call_id") in kept_ids:
                content = msg["content"]
                # Phase 3 ③截断:非最近 keep_recent 个且超长 → 截断标记
                # v0.6+ P1#11(Task 12):优先 token 级截断,token_budget 为 None 时回退字符级
                if isinstance(content, str) and idx not in keep_full:
                    if token_budget_per_tool_result is not None:
                        encoder = _get_tiktoken_encoder()
                        content = _truncate_by_tokens(
                            content, token_budget_per_tool_result, encoder
                        )
                    elif (tool_result_max_chars is not None
                            and len(content) > tool_result_max_chars):
                        content = content[:tool_result_max_chars] + "…(truncated)"
                out.append({
                    "role": "tool",
                    "tool_call_id": msg["tool_call_id"],
                    "content": content,
                })
        # 其他 role 忽略(防御性)

    return out


def _orm_to_dict(m: AgentMessageORM) -> dict:
    """ORM 消息转 dict 格式。"""
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "tool_calls": m.tool_calls,
        "tool_call_id": m.tool_call_id,
    }


# ===========================================================================
# v0.6 P1.6 — L2 记忆 helpers
# ===========================================================================


def _apply_memory_prepend(messages: list[dict], prepend: str) -> list[dict]:
    """把 relevant memories 块拼到第一条 user 消息前。

    设计:只对第一个 user role 消息拼接(本次 turn 的用户输入),
    不动后续 assistant / tool / system 消息,也不会重复注入。
    返回新列表(不修改入参),便于多次调用(build_messages 每次返回新列表即可)。
    """
    if not prepend:
        return messages
    out: list[dict] = []
    injected = False
    for m in messages:
        if not injected and m.get("role") == "user" and m.get("content"):
            out.append({**m, "content": prepend + "\n\n" + m["content"]})
            injected = True
        else:
            out.append(m)
    return out


# ===========================================================================
# Phase 1 — 埋点 helpers
# ===========================================================================


def _new_metrics() -> dict:
    return {
        "iterations": 0, "llm_calls": 0, "tool_calls": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "usage_seen": False,
    }


def _accumulate(agg: dict, usage: dict | None) -> None:
    agg["iterations"] += 1
    agg["llm_calls"] += 1
    if not usage:
        return
    agg["usage_seen"] = True
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        v = usage.get(k)
        if v is not None:
            agg[k] += v


def _emit_metrics(
    agg: dict, session_id: str, device_id: str | None, outcome: str,
    turn_duration_ms: float | None = None,
    cost_usd: "Decimal | None" = None,
) -> None:
    """记录 turn 级别指标(v0.6+ P1#22 Task 24 增加 turn_duration_ms + cost_usd)。"""
    logger.info(
        "agent_turn_metrics",
        session_id=session_id, device_id=device_id, outcome=outcome,
        iterations=agg["iterations"], llm_calls=agg["llm_calls"],
        tool_calls=agg["tool_calls"],
        prompt_tokens=agg["prompt_tokens"] if agg["usage_seen"] else None,
        completion_tokens=agg["completion_tokens"] if agg["usage_seen"] else None,
        total_tokens=agg["total_tokens"] if agg["usage_seen"] else None,
        turn_duration_ms=turn_duration_ms,
        cost_usd=str(cost_usd) if cost_usd is not None else None,
    )