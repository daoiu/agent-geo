"""一次性:生成金标集草稿到 evals/retrieval/golden_set.draft.jsonl。人工抽查后改名为 golden_set.jsonl。"""
import asyncio
from pathlib import Path

from evals.retrieval.dataset import save_golden_set
from evals.retrieval.dataset_builder import build_golden_set


async def main():
    items = await build_golden_set(per_kb=5)
    out = Path("evals/retrieval/golden_set.draft.jsonl")
    save_golden_set(items, out)
    print(f"生成 {len(items)} 条草稿 → {out}")


if __name__ == "__main__":
    asyncio.run(main())