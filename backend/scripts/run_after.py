"""一次性:跑检索「升级后」基线 — 走 search_pipeline(改写+BM25+重排+缓存)。

用法:cd backend && python -m scripts.run_after
输出:reports/eval/retrieval-after-pipeline-2026-07-17.{json,md}
"""
import asyncio
from pathlib import Path

from evals.retrieval.dataset import load_golden_set
from evals.retrieval.retrieval_runner import run_baseline, write_report
from app.services.hybrid_search import HybridSearch


class _PipelineSearch:
    """把 HybridSearch.search_pipeline 适配成 retrieval_runner 期望的 search 协议。"""

    def __init__(self) -> None:
        self._hs = HybridSearch()

    async def search(self, kb_id: str, query: str, top_k: int) -> list[dict]:
        return await self._hs.search_pipeline(kb_id, query, top_k)


# 升级后环境标注:① 全管道(缓存→改写→双路→RRF→重排);无 Redis / 无 reranker 模型时
# 缓存与重排降级为 no-op / 恒等,BM25 与改写在 LLM 可用时生效。
ENV_NOTE = (
    "① 混合检索管道升级后基线:"
    "查询改写(Multi-Query+HyDE) → 向量+BM25 双路召回 → RRF 融合 → Cross-Encoder 重排,配 Redis 语义缓存。"
    "无 reranker 模型时退化为恒等重排;无 Redis 时缓存 no-op;无 LLM key 时跳过改写。"
    "金标集 4 条样本,Recall@5 / context_precision 与 baseline 同口径对比。"
)


async def main():
    items = load_golden_set("evals/retrieval/golden_set.jsonl")
    rep = await run_baseline(items, search=_PipelineSearch(), note=ENV_NOTE)
    md = write_report(rep, Path("../reports/eval"), "after-pipeline-2026-07-17")
    print(rep.to_dict())
    print("报告:", md)


if __name__ == "__main__":
    asyncio.run(main())