"""一次性:跑检索基线并生成报告。"""
import asyncio
from pathlib import Path

from evals.retrieval.dataset import load_golden_set
from evals.retrieval.retrieval_runner import run_baseline, write_report

# 诚实标注当前环境:小数据集 + 1-relevance-per-query 的金标结构。
ENV_NOTE = (
    "环境标注:真混合检索已生效(HybridSearch 不再 fallback);"
    "金标集仅 4 条(1 个 KB / 4 chunks),每条 query 只标注 1 个 relevant chunk,"
    "Recall@5=1.0 受 top_k 完全覆盖影响,context_precision@5=0.25 反映真实精确率(其他 3 个 chunks 不是该 query 的目标)。"
)


async def main():
    items = load_golden_set("evals/retrieval/golden_set.jsonl")
    rep = await run_baseline(items, note=ENV_NOTE)
    md = write_report(rep, Path("../reports/eval"), "2026-07-17")
    print(rep.to_dict())
    print("报告:", md)


if __name__ == "__main__":
    asyncio.run(main())