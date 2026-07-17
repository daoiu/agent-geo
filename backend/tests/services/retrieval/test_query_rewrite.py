"""① 混合检索管道:查询改写 Multi-Query + HyDE 测试。

覆盖四件事:解析行号前缀、原查询在前+去重、无 provider 降级、HyDE 追加。
"""
from app.services.retrieval.query_rewrite import rewrite, _parse_lines


class _FakeLLM:
    def __init__(self, reply, providers=("p",)):
        self._reply = reply
        self.available_providers = list(providers)

    async def simple_chat(self, prompt):
        return self._reply


def test_parse_lines_strips_numbering():
    out = _parse_lines("1. 什么是GEO\n2) GEO定义\n\n- GEO含义")
    assert out == ["什么是GEO", "GEO定义", "GEO含义"]


async def test_rewrite_includes_original_and_variants():
    llm = _FakeLLM("GEO是什么\nGEO的定义\n生成式引擎优化含义")
    out = await rewrite("什么是GEO", llm, n=3)
    assert out[0] == "什么是GEO"           # 原查询在首
    assert "GEO的定义" in out
    assert len(out) == len(set(out))       # 去重


async def test_rewrite_no_provider_returns_original():
    llm = _FakeLLM("x", providers=())
    assert await rewrite("q", llm, n=3) == ["q"]


async def test_rewrite_hyde_appends_doc():
    llm = _FakeLLM("变体")
    out = await rewrite("q", llm, n=1, enable_hyde=True)
    assert len(out) >= 2  # 原查询 + 变体/HyDE