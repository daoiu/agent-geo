"""Task 7: HITL interrupt bridge — hitl_guard + resume_command.

RED: write failing test first (ImportError before policy.py exists).
GREEN: write minimal policy.py, see tests pass.
"""
import pytest
from langgraph.types import Command

from app.domain.exceptions import HumanConfirmationRequired


def test_hitl_guard_calls_interrupt_when_tool_raises():
    """_execute 抛 HumanConfirmationRequired 时,hitl_guard 必须调 interrupt(payload)."""

    called = {}

    def fake_interrupt(payload):
        called["payload"] = payload
        # Simulate LangGraph __interrupt__ halting the graph
        raise StopIteration("__interrupt__")

    # Monkeypatch: replace module-level `interrupt` binding so hitl_guard uses the fake
    import app.domain.agent.langgraph_nodes.policy as policy_module
    policy_module.interrupt = fake_interrupt  # type: ignore

    from app.domain.agent.langgraph_nodes.policy import hitl_guard

    state = {"messages": [], "session_id": "s1", "tool_call_log": []}

    with pytest.raises(StopIteration):
        hitl_guard(
            state,
            tool_fn=lambda: (
                _ for _ in ()
            ).throw(
                HumanConfirmationRequired(
                    message_id="msg-1",
                    tool_name="generate_article",
                    arguments={"topic": "AI"},
                )
            ),
        )

    # hitl_guard passes exception attributes into interrupt payload
    assert called["payload"]["message_id"] == "msg-1"
    assert called["payload"]["tool_name"] == "generate_article"
    assert called["payload"]["arguments"] == {"topic": "AI"}
    assert called["payload"]["kind"] == "decision"  # HumanConfirmationRequired.kind


def test_resume_command_wraps_decision():
    """resume_command(user_decision) 返回 Command(resume=user_decision)."""
    from app.domain.agent.langgraph_nodes.policy import resume_command

    cmd = resume_command({"decision": "approve", "tool_call_id": "tc1"})
    assert isinstance(cmd, Command)
    # LangGraph 1.x exposes the resume value as .resume
    assert cmd.resume == {"decision": "approve", "tool_call_id": "tc1"}
