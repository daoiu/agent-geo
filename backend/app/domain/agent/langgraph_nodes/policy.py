"""v0.8 PolicyNode + HITL guard (spec §9 + §4.2.5)。

HITL 桥接: HumanConfirmationRequired → interrupt(payload),
恢复走 resume_command(user_decision) → Command(resume=...)。

PolicyNode (Task 10): retry 包装 LLM 路径,transient retry,programming 直接抛。

实现选择:不使用 tenacity `stop_after_attempt` 装饰器 — 因为该 stop 参数在
import 时求值,test monkeypatch Settings.max_retries 不生效。改为内联 while loop,
每次调用动态读取 max_retries。
"""
from __future__ import annotations

import time

from langgraph.types import Command, interrupt

from app.domain.exceptions import (
    HumanConfirmationRequired,
    _LLM_TRANSIENT_EXCEPTIONS,
)


def hitl_guard(state: dict, tool_fn: callable) -> dict:
    """包 tool_fn 调用，把 HumanConfirmationRequired 转换为 interrupt(payload).

    LangGraph 捕获 interrupt 后会中止当前 turn，持久化到 checkpoint；
    后续 resume 通过 resume_command 注入用户决策。
    """
    try:
        result = tool_fn()
        return {
            "tool_call_log": state.get("tool_call_log", [])
            + [{"status": "ok", "result": result}]
        }
    except HumanConfirmationRequired as exc:
        interrupt({
            "kind": exc.kind,
            "message_id": exc.message_id,
            "tool_name": exc.tool_name,
            "arguments": exc.arguments,
            "tool_call_id": None,  # filled by node runtime in Task 11
            "resume_token": None,  # filled by node runtime in Task 11
        })


def resume_command(user_decision: dict) -> Command:
    """用户决策 → LangGraph Command(resume=...) 注入。"""
    return Command(resume=user_decision)


# ===========================================================================
# v0.8 PolicyNode — Task 10
# ===========================================================================


def _call_llm(state: dict, llm_client) -> dict:
    """实际 LLM 调用(可被测试 monkeypatch)。"""
    return llm_client.chat(state["messages"])


def _call_tool(state: dict, tool_executor, tool_call: dict) -> dict:
    """实际 tool 调用(可被测试 monkeypatch)。"""
    return tool_executor.execute(tool_call["name"], tool_call["args"])


def _get_max_retries() -> int:
    """懒加载 Settings.max_retries,缺省 3。"""
    try:
        from app.core.config import get_settings
        s = get_settings()
        return getattr(s, "max_retries", 3)
    except Exception:  # noqa: BLE001
        return 3


def policy_llm_call(state: dict, runtime, llm_client) -> dict:
    """包 _call_llm 的 retry/transient 区分。

    transient → 指数退避重试直到 Settings.max_retries(运行时读取)
    programming / 其他 → 不重试,直接 reraise
    """
    max_retries = max(1, _get_max_retries())
    attempt = 0
    while True:
        try:
            return _call_llm(state, llm_client)
        except _LLM_TRANSIENT_EXCEPTIONS:
            attempt += 1
            if attempt >= max_retries:
                raise
            time.sleep(min(2 ** attempt, 10))


def policy_tool_call(state: dict, runtime, tool_executor, tool_call: dict) -> dict:
    """包 _call_tool;编程错误不重试,直接抛(由 PolicyNode 转 llm_error SSE)。

    note: 不包 retry 装饰器 — tool 调用若失败按 react_loop 既有降级路径走。
    """
    return _call_tool(state, tool_executor, tool_call)
