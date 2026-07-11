"""Tests for list_knowledge_bases executor (v0.6 P1.4)."""
from __future__ import annotations

import pytest

from app.domain.agent.tool_executor import ToolExecutor


@pytest.mark.asyncio
async def test_list_knowledge_bases_returns_shape(db_session):
    """list_knowledge_bases → [{kb_id, kb_name, doc_count, created_at}] + total_count."""
    from app.repositories.knowledge_repo import KnowledgeRepository

    repo = KnowledgeRepository(db_session)
    kb0 = await repo.create_kb(name="空 KB")
    kb1 = await repo.create_kb(name="北北云吞")
    await repo.add_document(
        kb_id=kb1.id, filename="北北云吞.md", file_path="/tmp/a.md",
        file_type="md", file_size=10,
    )

    executor = ToolExecutor(session_id="s1")
    result = await executor._execute_list_knowledge_bases(None)

    assert result["total_count"] == 2
    by_id = {kb["kb_id"]: kb for kb in result["knowledge_bases"]}
    assert by_id[kb0.id]["kb_name"] == "空 KB"
    assert by_id[kb0.id]["doc_count"] == 0
    assert by_id[kb1.id]["doc_count"] == 1
    # created_at 需可 JSON 序列化（isoformat 字符串）
    assert isinstance(by_id[kb1.id]["created_at"], str)


@pytest.mark.asyncio
async def test_execute_dispatches_list_knowledge_bases(db_session):
    """execute('list_knowledge_bases', {}) 不再抛 Unknown tool（回归 code-review 缺陷）."""
    from app.repositories.knowledge_repo import KnowledgeRepository

    repo = KnowledgeRepository(db_session)
    await repo.create_kb(name="KB")

    executor = ToolExecutor(session_id="s1")
    result = await executor.execute("list_knowledge_bases", {})

    assert result["total_count"] == 1
    assert result["knowledge_bases"][0]["kb_name"] == "KB"
