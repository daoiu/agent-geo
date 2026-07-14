"""v0.8 PolicyNode + HITL guard (spec §9 + §4.2.5).

HITL 桥接: HumanConfirmationRequired → interrupt(payload),
恢复走 resume_command(user_decision) → Command(resume=...).
"""
from __future__ import annotations

from langgraph.types import Command, interrupt

from app.domain.exceptions import HumanConfirmationRequired


def hitl_guard(state: dict, tool_fn: callable) -> dict:
    """包 tool_fn 调用，把 HumanConfirmationRequired 转换为 interrupt(payload).

    LangGraph 捕获 interrupt 后会中止当前 turn，持久化到 checkpoint；
    后续 resume 通过 resume_command 注入用户决策。

    Payload 字段对齐 SSEBridge human_confirmation_required handler:
    - kind, message_id, tool_name, arguments — 来自异常属性
    - tool_call_id, resume_token — 在 Task 11 接线时由节点运行时注入
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
