"""Higher-level retrieval helpers (v0.2 uses keyword search from repo)."""
from __future__ import annotations

import jieba

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v02 import KnowledgeChunkORM
from app.repositories.knowledge_repo import KnowledgeRepository


def extract_search_keywords(text: str) -> list[str]:
    """Segment Chinese/English text and return searchable keywords.

    Single source of truth: drops single-character tokens (poor search
    signal) and whitespace-only segments. Both api/knowledge.py and
    tasks/task_worker.py call this.
    """
    return [w for w in jieba.cut(text) if len(w.strip()) > 1]


async def search_chunks(
    session: AsyncSession,
    kb_id: str,
    keywords: list[str],
    top_k: int = 5,
) -> list[KnowledgeChunkORM]:
    """Convenience wrapper around KnowledgeRepository.search_chunks_by_keyword."""
    repo = KnowledgeRepository(session)
    return await repo.search_chunks_by_keyword(
        kb_id=kb_id, keywords=keywords, top_k=top_k
    )
