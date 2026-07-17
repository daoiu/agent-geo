"""编排:载入金标 → 跑 HybridSearch → Recall/MRR → 生成答案 → RAGAS → 聚合报告。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from evals.retrieval.dataset import GoldenItem
from evals.retrieval.ragas_scorer import score
from evals.retrieval.retrieval_metrics import mrr_at_k, recall_at_k

logger = structlog.get_logger()


@dataclass
class RetrievalReport:
    total: int
    recall_at_5: float
    mrr_at_5: float
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    llm_available: bool
    by_kb: dict = field(default_factory=dict)
    details: list = field(default_factory=list)
    note: str = ""

    def to_dict(self, include_details: bool = False) -> dict:
        d = {
            "total": self.total,
            "recall_at_5": round(self.recall_at_5, 3),
            "mrr_at_5": round(self.mrr_at_5, 3),
            "faithfulness": round(self.faithfulness, 3),
            "answer_relevancy": round(self.answer_relevancy, 3),
            "context_precision": round(self.context_precision, 3),
            "llm_available": self.llm_available,
            "by_kb": self.by_kb,
            "note": self.note,
        }
        if include_details:
            d["details"] = self.details
        return d


async def _generate_answer(query: str, contexts: list[str], llm) -> str:
    if not getattr(llm, "available_providers", []):
        return ""
    ctx = "\n".join(contexts[:5])
    prompt = f"仅根据下面资料回答问题,不要编造。\n资料:\n{ctx}\n\n问题:{query}"
    return await llm.simple_chat(prompt)


async def run_baseline(items, search=None, llm=None, embed_fn=None, top_k: int = 5) -> RetrievalReport:
    if search is None:
        from app.services.hybrid_search import HybridSearch
        search = HybridSearch()
    if llm is None:
        from app.core.config import get_settings
        from app.domain.llm_client import LLMClient
        llm = LLMClient(get_settings())

    details: list[dict] = []
    for it in items:
        hits = await search.search(kb_id=it.kb_id, query=it.query, top_k=top_k)
        retrieved_ids = [h["id"] for h in hits]
        contexts = [h.get("content", "") for h in hits]
        recall = recall_at_k(retrieved_ids, it.relevant_chunk_ids, top_k)
        mrr = mrr_at_k(retrieved_ids, it.relevant_chunk_ids, top_k)
        answer = await _generate_answer(it.query, contexts, llm)
        rag = await score(
            it.query, answer, contexts, retrieved_ids, it.relevant_chunk_ids,
            llm, embed_fn, k=top_k,
        )
        details.append({
            "id": it.id, "kb_id": it.kb_id, "query": it.query,
            "recall": recall, "mrr": mrr,
            "faithfulness": rag.faithfulness,
            "answer_relevancy": rag.answer_relevancy,
            "context_precision": rag.context_precision,
        })

    n = len(details) or 1

    def _avg(key: str) -> float:
        return sum(d[key] for d in details) / n

    by_kb: dict[str, dict] = {}
    for d in details:
        b = by_kb.setdefault(d["kb_id"], {"count": 0, "recall": 0.0})
        b["count"] += 1
        b["recall"] += d["recall"]
    for kb_id, b in by_kb.items():
        b["recall"] = round(b["recall"] / b["count"], 3)

    llm_available = any(d["faithfulness"] or d["answer_relevancy"] for d in details) or \
        bool(getattr(llm, "available_providers", []))

    return RetrievalReport(
        total=len(details),
        recall_at_5=_avg("recall"),
        mrr_at_5=_avg("mrr"),
        faithfulness=_avg("faithfulness"),
        answer_relevancy=_avg("answer_relevancy"),
        context_precision=_avg("context_precision"),
        llm_available=bool(getattr(llm, "available_providers", [])),
        by_kb=by_kb,
        details=details,
        note="检索基线;LLM 指标在无 key 时为 0",
    )


def write_report(report: RetrievalReport, out_dir, date_str: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"retrieval-baseline-{date_str}.json").write_text(
        json.dumps(report.to_dict(include_details=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md = out / f"retrieval-baseline-{date_str}.md"
    d = report.to_dict()
    md.write_text(
        f"""# 检索评测基线 {date_str}

| 指标 | 值 |
|---|---|
| 样本数 | {d['total']} |
| Recall@5 | {d['recall_at_5']} |
| MRR@5 | {d['mrr_at_5']} |
| faithfulness | {d['faithfulness']} |
| answer_relevancy | {d['answer_relevancy']} |
| context_precision | {d['context_precision']} |
| LLM 指标可用 | {d['llm_available']} |

> {d['note']}
""",
        encoding="utf-8",
    )
    return md