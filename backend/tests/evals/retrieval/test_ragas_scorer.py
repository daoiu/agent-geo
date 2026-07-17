"""RAGAS 式三指标(faithfulness / answer_relevancy / context_precision)测试。TDD:Step 1。"""
from evals.retrieval.ragas_scorer import (
    RagasScores, context_precision, faithfulness, answer_relevancy, score,
)


class _FakeLLM:
    def __init__(self, reply: str, providers=("p",)):
        self._reply = reply
        self.available_providers = list(providers)

    async def simple_chat(self, prompt: str) -> str:
        return self._reply


def _fake_embed(texts):
    # "问题"类文本 → [1,0];其它 → [0,1];用于余弦区分
    return [[1.0, 0.0] if "GEO" in t else [0.0, 1.0] for t in texts]


def test_context_precision_pure():
    assert round(context_precision(["a", "b", "x"], ["a", "b"], k=3), 3) == 0.667


async def test_faithfulness_all_supported():
    llm = _FakeLLM('{"supported": 3, "total": 3}')
    assert await faithfulness("答案", ["ctx"], llm) == 1.0


async def test_faithfulness_partial():
    llm = _FakeLLM('{"supported": 1, "total": 2}')
    assert await faithfulness("答案", ["ctx"], llm) == 0.5


async def test_answer_relevancy_cosine():
    llm = _FakeLLM("关于 GEO 的问题")  # 反推问题
    val = await answer_relevancy("GEO 的问题", "GEO 是…", llm, _fake_embed)
    assert val == 1.0


async def test_score_degrades_without_llm():
    llm = _FakeLLM("x", providers=())  # 无 provider
    s = await score("q", "a", ["ctx"], ["a"], ["a"], llm, _fake_embed, k=3)
    assert s.llm_available is False
    assert s.faithfulness == 0.0 and s.answer_relevancy == 0.0
    assert s.context_precision == 1.0  # 纯函数仍可算