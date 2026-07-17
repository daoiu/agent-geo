"""②b 模式路由测试(spec agent-orchestrator §6.2.2 / §6.2.4)。"""
from app.domain.agent.orchestrator.router import (
    MODE_PLAN,
    MODE_REACT,
    choose_mode,
    should_downgrade,
    should_escalate,
)


def test_short_query_is_react():
    assert choose_mode("小米诊断") == MODE_REACT


def test_hint_complex_forces_plan():
    assert choose_mode("短", hint="complex") == MODE_PLAN


def test_long_query_is_plan():
    assert choose_mode("长" * 900) == MODE_PLAN


def test_escalate_on_max_iterations():
    assert should_escalate({"outcome": "max_iterations_reached", "escalated": False}) is True


def test_no_escalate_when_already_escalated():
    assert should_escalate({"outcome": "max_iterations_reached", "escalated": True}) is False


def test_downgrade_when_no_steps():
    assert should_downgrade([]) is True
    assert should_downgrade([{"step": "x"}]) is False
