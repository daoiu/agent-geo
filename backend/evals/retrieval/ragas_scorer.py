"""RAGAS 式三指标(自研,离线可跑):faithfulness / answer_relevancy / context_precision。

接口按 ragas 语义命名,日后可无缝替换为官方 ragas 包。
- faithfulness:LLM 判定答案被 context 支撑的句子占比(反幻觉)
- answer_relevancy:LLM 反推问题 → 与原问题 embedding 余弦
- context_precision:纯函数,复用 Recall/Precision 家族(结合金标 relevant_ids)
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

from evals.retrieval.retrieval_metrics import precision_at_k

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass
class RagasScores:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    llm_available: bool


def context_precision(retrieved_ids: list[str], relevant_ids: list[str], k: int = 5) -> float:
    return precision_at_k(retrieved_ids, relevant_ids, k)


async def faithfulness(answer: str, contexts: list[str], llm) -> float:
    ctx = "\n".join(contexts)
    prompt = (
        "判断下面【答案】中的每个陈述是否能被【上下文】支撑。"
        '只输出 JSON:{"supported": 支撑句数, "total": 总句数}。\n\n'
        f"【上下文】\n{ctx}\n\n【答案】\n{answer}"
    )
    reply = _FENCE_RE.sub("", await llm.simple_chat(prompt)).strip()
    try:
        obj = json.loads(reply)
        total = int(obj["total"])
        return float(obj["supported"]) / total if total > 0 else 0.0
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def answer_relevancy(question: str, answer: str, llm, embed_fn) -> float:
    prompt = f"根据下面这段答案,反推用户最可能问的一个问题,只输出问题本身:\n{answer}"
    reverse_q = await llm.simple_chat(prompt)
    vecs = embed_fn([question, reverse_q])
    if len(vecs) < 2:
        return 0.0
    return max(0.0, _cosine(vecs[0], vecs[1]))


async def score(
    question: str,
    answer: str,
    contexts: list[str],
    retrieved_ids: list[str],
    relevant_ids: list[str],
    llm,
    embed_fn=None,
    k: int = 5,
) -> RagasScores:
    cp = context_precision(retrieved_ids, relevant_ids, k)
    llm_available = bool(getattr(llm, "available_providers", []))
    if not llm_available:
        return RagasScores(0.0, 0.0, cp, False)
    if embed_fn is None:
        from app.services.embedding import EmbeddingService
        embed_fn = EmbeddingService.embed
    f = await faithfulness(answer, contexts, llm)
    ar = await answer_relevancy(question, answer, llm, embed_fn)
    return RagasScores(f, ar, cp, True)