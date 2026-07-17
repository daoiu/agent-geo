"""评测编排 runner 测试。TDD:Step 1。"""
from evals.retrieval.dataset import GoldenItem
from evals.retrieval.retrieval_runner import RetrievalReport, run_baseline, write_report


class _FakeSearch:
    async def search(self, kb_id, query, top_k):
        # 第一条命中金标 c1;第二条全 miss
        # 用 query 首字区分,避免 "命中" 子串同时匹配 "未命中"
        if query.startswith("命中"):
            return [{"id": "c1", "content": "相关内容"}, {"id": "z", "content": "x"}]
        return [{"id": "z", "content": "x"}]


class _FakeLLM:
    available_providers = []  # 触发降级,runner 不需要真 LLM

    async def simple_chat(self, prompt):
        return ""


def _fake_embed(texts):
    return [[1.0, 0.0] for _ in texts]


async def test_run_baseline_aggregates():
    items = [
        GoldenItem(id="q1", kb_id="kb1", query="命中问题", relevant_chunk_ids=["c1"], reference_answer="a"),
        GoldenItem(id="q2", kb_id="kb1", query="未命中问题", relevant_chunk_ids=["c1"], reference_answer="a"),
    ]
    rep = await run_baseline(items, search=_FakeSearch(), llm=_FakeLLM(), embed_fn=_fake_embed, top_k=5)
    assert rep.total == 2
    assert rep.recall_at_5 == 0.5      # 一条命中一条 miss
    assert rep.llm_available is False
    assert "kb1" in rep.by_kb


async def test_write_report_creates_files(tmp_path):
    rep = RetrievalReport(
        total=1, recall_at_5=0.5, mrr_at_5=0.5, faithfulness=0.0,
        answer_relevancy=0.0, context_precision=1.0, llm_available=False,
        by_kb={}, details=[], note="test",
    )
    md = write_report(rep, tmp_path, "2026-07-17")
    assert md.exists()
    assert (tmp_path / "retrieval-baseline-2026-07-17.json").exists()