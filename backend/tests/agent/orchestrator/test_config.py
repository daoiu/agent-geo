"""②b 配置项冒烟测试(spec agent-orchestrator §6.2.1)。"""
from app.core.config import get_settings


def test_orchestrator_defaults():
    s = get_settings()
    assert s.agent_orchestrator_enabled is False
    assert s.reflection_enabled is True
    assert s.reflection_min_score == 60
    assert s.reflection_max_retries == 2
    assert s.plan_execute_max_steps == 6
