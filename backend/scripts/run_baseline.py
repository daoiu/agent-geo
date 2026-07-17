"""一次性:跑检索基线并生成报告。"""
import asyncio
from pathlib import Path

from evals.retrieval.dataset import load_golden_set
from evals.retrieval.retrieval_runner import run_baseline, write_report

# 诚实标注当前环境:embedding 维度不匹配(384 vs 512),HybridSearch fallback 到 keyword-only。
ENV_NOTE = (
    "环境标注:embedding 维度不匹配(384 vs 512),HybridSearch 实际 fallback 到 keyword-only;"
    "金标集仅 4 条(1 个 KB / 4 chunks),Recall@5 受 top_k 完全覆盖影响严重;"
    "context_precision=0.25 是当前最可信的精确率信号。"
)


async def main():
    items = load_golden_set("evals/retrieval/golden_set.jsonl")
    rep = await run_baseline(items, note=ENV_NOTE)
    md = write_report(rep, Path("../reports/eval"), "2026-07-17")
    print(rep.to_dict())
    print("报告:", md)


if __name__ == "__main__":
    asyncio.run(main())