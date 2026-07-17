"""LLM 半合成金标构建测试。TDD:Step 1。"""
import pytest

from evals.retrieval.dataset_builder import gen_qa_for_chunk


class _FakeLLM:
    def __init__(self, reply: str):
        self._reply = reply

    async def simple_chat(self, prompt: str) -> str:
        return self._reply


async def test_gen_qa_parses_json():
    llm = _FakeLLM('{"question": "什么是 GEO?", "answer": "GEO 是生成式引擎优化。"}')
    q, a = await gen_qa_for_chunk("GEO 指生成式引擎优化…", llm)
    assert q == "什么是 GEO?"
    assert "生成式引擎优化" in a


async def test_gen_qa_strips_code_fence():
    llm = _FakeLLM('```json\n{"question": "Q?", "answer": "A"}\n```')
    q, a = await gen_qa_for_chunk("内容", llm)
    assert q == "Q?" and a == "A"


async def test_gen_qa_invalid_json_raises():
    llm = _FakeLLM("这不是 JSON")
    with pytest.raises(ValueError):
        await gen_qa_for_chunk("内容", llm)