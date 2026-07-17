"""检索评测纯函数:Recall@k / MRR@k / Precision@k。

约定:relevant_ids 为空时 recall 返回 1.0(无标注不惩罚)。
retrieved_ids 会按首次出现去重后再截断到前 k 个。
"""
from __future__ import annotations


def _top_k_unique(retrieved_ids: list[str], k: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for cid in retrieved_ids:
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
        if len(out) >= k:
            break
    return out


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    rel = set(relevant_ids)
    if not rel:
        return 1.0
    top = set(_top_k_unique(retrieved_ids, k))
    return len(top & rel) / len(rel)


def mrr_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    rel = set(relevant_ids)
    if not rel:
        return 1.0
    for rank, cid in enumerate(_top_k_unique(retrieved_ids, k), start=1):
        if cid in rel:
            return 1.0 / rank
    return 0.0


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    rel = set(relevant_ids)
    top = _top_k_unique(retrieved_ids, k)
    if not top:
        return 0.0
    hits = sum(1 for cid in top if cid in rel)
    return hits / len(top)