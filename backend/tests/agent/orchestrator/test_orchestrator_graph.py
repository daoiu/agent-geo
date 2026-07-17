"""②b orchestrator 编排图测试(spec agent-orchestrator §6.2.5)。

deps 注入：runner/reflector/llm 全部 stub，验证控制流而非真实 LLM 调用。
"""
import json

from app.domain.agent.orchestrator.graph import run_orchestrated
from app.domain.agent.orchestrator.reflection import ReflectionResult


def _decode(b):
    return json.loads(b.decode("utf-8"))


class _Deps:
    def __init__(self, scores):
        self._scores = list(scores)
        self.answers = []

    async def react_runner(self, session_id, message, critique=None):
        ans = f"答案-{len(self.answers)}"
        self.answers.append(ans)
        yield ("answer", ans)

    async def plan_runner(self, session_id, message, critique=None):
        yield ("answer", "plan答案")

    async def reflector(self, query, answer, trace, llm):
        return ReflectionResult(self._scores.pop(0), 0, 0, 0, "改进点", True)

    llm = type("L", (), {"available_providers": ["p"]})()


async def test_retry_until_pass_returns_best():
    deps = _Deps(scores=[50.0, 75.0])   # 第一次 50 触发重试，第二次 75 达标
    outs = [_decode(x) async for x in run_orchestrated("s1", "短问题", deps=deps)]
    events = [o["event"] for o in outs]
    assert "reflection_score" in events
    # 返回的 assistant_message 应是高分那次
    final = [o for o in outs if o["event"] == "assistant_message"][-1]
    assert final["content"] == "答案-1"


async def test_low_score_exhausts_returns_best():
    deps = _Deps(scores=[40.0, 50.0, 45.0])  # 都不达标，用尽后返回最高 50 那次
    outs = [_decode(x) async for x in run_orchestrated("s1", "短问题", deps=deps)]
    final = [o for o in outs if o["event"] == "assistant_message"][-1]
    assert final["content"] == "答案-1"  # score 50 对应第二次
