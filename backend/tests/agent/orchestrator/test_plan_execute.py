"""②b Plan-Execute 测试(spec agent-orchestrator §6.2.4)。"""
import pytest

from app.domain.agent.orchestrator.plan_execute import _parse_steps, execute, plan


class _FakeLLM:
    def __init__(self, reply):
        self._reply = reply

    async def simple_chat(self, prompt):  # noqa: D401
        return self._reply


def test_parse_steps_ok():
    steps = _parse_steps('[{"step": "查知识库", "tool_hint": "search_knowledge"}, {"step": "写文章"}]')
    assert len(steps) == 2 and steps[0]["tool_hint"] == "search_knowledge"


def test_parse_steps_invalid_returns_empty():
    assert _parse_steps("不是 JSON") == []


async def test_plan_truncates_to_max():
    llm = _FakeLLM('[{"step":"1"},{"step":"2"},{"step":"3"}]')
    steps = await plan("q", llm, max_steps=2)
    assert len(steps) == 2


async def test_execute_accumulates_results():
    calls = []

    async def _runner(step, idx):
        calls.append(idx)
        return f"结果{idx}"

    out = await execute([{"step": "a"}, {"step": "b"}], _runner, max_steps=6)
    assert out["results"] == ["结果0", "结果1"]
    assert out["failed_step"] is None


async def test_execute_records_failure():
    async def _runner(step, idx):
        if idx == 1:
            raise RuntimeError("boom")
        return "ok"

    out = await execute([{"step": "a"}, {"step": "b"}], _runner, max_steps=6)
    assert out["failed_step"] == 1
