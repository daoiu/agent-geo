"""LLM 半合成金标构建:从现有 KB chunk 生成 question + 参考答案。

离线一次性脚本,不进热路径。产出交人工抽查后提交 golden_set.jsonl。
"""
from __future__ import annotations

import json
import re

import structlog

from evals.retrieval.dataset import GoldenItem

logger = structlog.get_logger()

_PROMPT = """你是评测数据标注员。基于下面这段知识库文本,提出一个用户最可能问、且答案**完全能由这段文本回答**的中文问题,并给出参考答案。
只输出 JSON,格式:{{"question": "...", "answer": "..."}}

文本:
{content}
"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _parse_qa(reply: str) -> tuple[str, str]:
    # 兼容推理模型(DeepSeek-R1 / QwQ 等):先剥 <think>...</think> 块
    cleaned = _THINK_RE.sub("", reply)
    cleaned = _FENCE_RE.sub("", cleaned).strip()
    try:
        obj = json.loads(cleaned)
        return str(obj["question"]), str(obj["answer"])
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"LLM 返回无法解析为 QA JSON: {reply[:120]}") from e


async def gen_qa_for_chunk(content: str, llm) -> tuple[str, str]:
    reply = await llm.simple_chat(_PROMPT.format(content=content[:1500]))
    return _parse_qa(reply)


async def build_golden_set(per_kb: int = 5, llm=None, repo_factory=None) -> list[GoldenItem]:
    """逐 KB 取前 per_kb 个 chunk 生成金标条目。

    llm=None → 用默认 LLMClient;repo_factory=None → 用 get_session_factory。
    """
    from app.core.config import get_settings
    from app.core.db import get_session_factory
    from app.domain.llm_client import LLMClient
    from app.repositories.knowledge_repo import KnowledgeRepository

    if llm is None:
        llm = LLMClient(get_settings())
    session_factory = repo_factory or get_session_factory()

    items: list[GoldenItem] = []
    async with session_factory() as session:
        repo = KnowledgeRepository(session)
        kbs = await repo.list_kbs()
        for kb in kbs:
            chunks = await repo.list_chunks(kb.id)
            for i, chunk in enumerate(chunks[:per_kb]):
                try:
                    q, a = await gen_qa_for_chunk(chunk.content, llm)
                except ValueError as e:
                    logger.warning("golden_gen_skip", kb_id=kb.id, chunk_id=chunk.id, error=str(e))
                    continue
                items.append(
                    GoldenItem(
                        id=f"{kb.id[:8]}-{i}",
                        kb_id=kb.id,
                        query=q,
                        relevant_chunk_ids=[chunk.id],
                        reference_answer=a,
                    )
                )
    return items