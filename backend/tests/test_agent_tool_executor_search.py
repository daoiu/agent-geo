"""Tests for ToolExecutor._execute_search_knowledge branching (v0.6 P1.4)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.domain.agent.tool_executor import ToolExecutor
from app.domain.agent.tools import SearchKnowledgeArgs


@pytest.mark.asyncio
async def test_search_with_kb_id_uses_single_kb_hybrid():
    """kb_id 传入时走 HybridSearch().search（单库路径，P0#3 后由 tool_executor 直接调）."""
    executor = ToolExecutor(session_id="s1")
    args = SearchKnowledgeArgs(kb_id="kb-1", query="云吞", limit=5)

    fake_result = [
        {"id": "c1", "content": "陈皮云吞皮", "metadata":
            {"doc_id": "d1", "chunk_index": 0, "kb_id": "kb-1"},
         "_rrf_score": 0.05, "_sources": ["keyword"]},
    ]

    with patch("app.services.hybrid_search.HybridSearch") as MockHS:
        MockHS.return_value.search = AsyncMock(return_value=fake_result)
        # 让 kb_name 回查降级为 None（避免依赖真实 DB session）
        with patch(
            "app.repositories.knowledge_repo.KnowledgeRepository.get_kb",
            new=AsyncMock(side_effect=SQLAlchemyError("mock: no db")),
        ):
            result = await executor._execute_search_knowledge(args)

    MockHS.return_value.search.assert_called_once_with(
        kb_id="kb-1", query="云吞", top_k=5
    )
    assert result["kb_id"] == "kb-1"
    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["id"] == "c1"


@pytest.mark.asyncio
async def test_search_without_kb_id_uses_cross_kb_hybrid():
    """kb_id 不传时走 HybridSearch.search_across_kbs（跨库，P1.3 路径）."""
    executor = ToolExecutor(session_id="s1")
    args = SearchKnowledgeArgs(kb_id=None, query="云吞")  # ← 新行为：可选

    fake_across = [
        {"id": "c2", "content": "陈皮马蹄捶打",
         "metadata": {
             "doc_id": "d2", "chunk_index": 0, "kb_id": "kb-2",
             "kb_name": "北北云吞", "doc_filename": "北北云吞.md",
         },
         "_rrf_score": 0.054, "_sources": ["keyword"]},
    ]

    # Patch the HybridSearch class imported inside tool_executor
    with patch("app.services.hybrid_search.HybridSearch") as MockHS:
        MockHS.return_value.search_across_kbs = AsyncMock(return_value=fake_across)
        result = await executor._execute_search_knowledge(args)

    MockHS.return_value.search_across_kbs.assert_called_once()
    assert result["kb_id"] is None
    assert result["query"] == "云吞"
    assert len(result["chunks"]) == 1
    chunk = result["chunks"][0]
    assert chunk["kb_name"] == "北北云吞"
    assert chunk["doc_filename"] == "北北云吞.md"


@pytest.mark.asyncio
async def test_search_chunks_have_unified_shape():
    """两种分支返的 chunks shape 必须一致 — kb_name / doc_filename 可为 None 但 key 必须存在."""
    executor = ToolExecutor(session_id="s1")
    args = SearchKnowledgeArgs(kb_id="kb-1", query="x")

    fake = [
        {"id": "c1", "content": "abc",
         "metadata": {"doc_id": "d1", "chunk_index": 0, "kb_id": "kb-1"},
         "_rrf_score": 0.1, "_sources": ["keyword"]},
    ]
    with patch("app.services.hybrid_search.HybridSearch") as MockHS:
        MockHS.return_value.search = AsyncMock(return_value=fake)
        with patch(
            "app.repositories.knowledge_repo.KnowledgeRepository.get_kb",
            new=AsyncMock(side_effect=SQLAlchemyError("mock")),
        ):
            result = await executor._execute_search_knowledge(args)
    chunk = result["chunks"][0]
    # 缺省字段当 None，但 keys 必须存在，便于 LLM 一致处理
    for key in ("kb_name", "doc_filename"):
        assert key in chunk


@pytest.mark.asyncio
async def test_search_truncates_content_at_500_chars():
    executor = ToolExecutor(session_id="s1")
    args = SearchKnowledgeArgs(kb_id="kb-1", query="x")
    long_content = "x" * 1000
    fake = [{
        "id": "c1", "content": long_content,
        "metadata": {"doc_id": "d1", "chunk_index": 0, "kb_id": "kb-1"},
        "_rrf_score": 0.1, "_sources": ["keyword"]},
    ]
    with patch("app.services.hybrid_search.HybridSearch") as MockHS:
        MockHS.return_value.search = AsyncMock(return_value=fake)
        with patch(
            "app.repositories.knowledge_repo.KnowledgeRepository.get_kb",
            new=AsyncMock(side_effect=SQLAlchemyError("mock")),
        ):
            result = await executor._execute_search_knowledge(args)
    assert len(result["chunks"][0]["content"]) == 500
