"""②b ReflectionAgent 测试(spec agent-orchestrator §6.2.3)。

LLM-as-Judge 多维打分：completeness / faithfulness / tool_appropriateness
加权 0.4 / 0.4 / 0.2 → 综合 0-100。
"""
from app.domain.agent.orchestrator.reflection import (
    ReflectionResult,
    pick_best,
    score_answer,
    should_retry,
)


class _FakeLLM:
    def __init__(self, reply, providers=("p",)):
        self._reply = reply
        self.available_providers = list(providers)

    async def simple_chat(self, prompt):  # noqa: D401
        return self._reply


async def test_score_weighted():
    llm = _FakeLLM('{"completeness": 80, "faithfulness": 90, "tool_appropriateness": 50, "critique": "ok"}')
    r = await score_answer("q", "a", "", llm)
    # 0.4*80 + 0.4*90 + 0.2*50 = 78
    assert r.score == 78.0
    assert r.available is True


async def test_no_provider_passes_through():
    llm = _FakeLLM("x", providers=())
    r = await score_answer("q", "a", "", llm)
    assert r.available is False and r.score == 100.0


async def test_invalid_json_returns_zero_available():
    llm = _FakeLLM("非 JSON")
    r = await score_answer("q", "a", "", llm)
    assert r.available is True and r.score == 0.0


def test_should_retry_logic():
    low = ReflectionResult(50, 0, 0, 0, "c", True)
    high = ReflectionResult(70, 0, 0, 0, "c", True)
    assert should_retry(low, attempts_done=1, min_score=60, max_retries=2) is True
    assert should_retry(low, attempts_done=2, min_score=60, max_retries=2) is False  # 用尽
    assert should_retry(high, attempts_done=1, min_score=60, max_retries=2) is False  # 达标


def test_pick_best_returns_highest():
    assert pick_best([(50.0, "a"), (72.0, "b"), (60.0, "c")]) == "b"
