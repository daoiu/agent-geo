"""MemoryService 测试 — 7 函数 + threshold + Settings。

LLM 调用全部 mock,沿用 v0.5 `patch("...LLMClient")` 模式。
"""
import json
from unittest.mock import AsyncMock, patch

import pytest


LLM_NEW_EXTRACT = json.dumps([
    {"name": "bb-cloud", "type": "project",
     "description": "北北云吞 品牌", "body": "潮汕口味"},
    {"name": "style", "type": "feedback",
     "description": "用户偏好简洁", "body": "no emoji"},
])

LLM_CONSOLIDATE = json.dumps([
    {"name": "bb-cloud-merged", "type": "project",
     "description": "北北云吞", "body": "潮汕堂食"},
])


# ============================================================================
# 基础 CRUD:write_memory + read_memory_index + list_memories + read_memory
# ============================================================================


@pytest.mark.asyncio
async def test_write_and_read_index(db_session):
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    await svc.write_memory(
        scope="d", name="a", type="user",
        description="x", body="body", session_id="s1",
    )
    idx = await svc.read_memory_index("d")
    assert "- a — x" in idx
    assert len(idx.splitlines()) == 1


@pytest.mark.asyncio
async def test_list_memories(db_session):
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    await svc.write_memory(scope="d", name="a", type="user", description="x", body="")
    await svc.write_memory(scope="d", name="b", type="project", description="y", body="")
    rows = await svc.list_memories("d")
    assert {r["name"] for r in rows} == {"a", "b"}


@pytest.mark.asyncio
async def test_read_memory_returns_dict(db_session):
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    m = await svc.write_memory(
        scope="d", name="a", type="user",
        description="x", body="content", session_id="s1",
    )
    fetched = await svc.read_memory(m["id"])
    assert fetched is not None
    assert fetched["body_md"] == "content"


@pytest.mark.asyncio
async def test_write_rejects_unknown_type(db_session):
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    with pytest.raises(ValueError):
        await svc.write_memory(
            scope="d", name="a", type="bogus",
            description="x", body="",
        )


# ============================================================================
# build_memory_segment(给 system prompt 用)
# ============================================================================


@pytest.mark.asyncio
async def test_build_segment_empty(db_session):
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    assert await svc.build_memory_segment("d") == ""


@pytest.mark.asyncio
async def test_build_segment_format(db_session):
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    await svc.write_memory(scope="d", name="a", type="user", description="x", body="...")
    seg = await svc.build_memory_segment("d")
    assert "Memories available" in seg
    assert "a — x" in seg


# ============================================================================
# select_relevant + load_relevant_memories
# ============================================================================


@pytest.mark.asyncio
async def test_select_relevant_uses_llm(db_session):
    """LLM 选 index → 返回对应 row。"""
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    await svc.write_memory(scope="d", name="bb", type="project",
                            description="wonton brand", body="...")
    await svc.write_memory(scope="d", name="style", type="feedback",
                            description="writing style", body="...")
    msgs = [{"role": "user", "content": "I want to write about the wonton brand"}]

    # list_by_scope 按 updated_at DESC,所以最后一次写入的 style 在 index 0
    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(return_value="[0]")
        result = await svc.select_relevant("d", msgs, k=5)

    assert len(result) == 1
    # selected row 是 index 0,即"最新写入的那条"
    assert result[0]["name"] in {"bb", "style"}


@pytest.mark.asyncio
async def test_select_relevant_keyword_fallback(db_session):
    """LLM 失败时降级关键词匹配 — 英文 token 可命中。"""
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    await svc.write_memory(
        scope="d", name="bcloud", type="project",
        description="wonton brand info", body="",
    )
    msgs = [{"role": "user", "content": "Tell me about the wonton brand please"}]

    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(side_effect=Exception("API down"))
        result = await svc.select_relevant("d", msgs, k=5)

    assert any(m["name"] == "bcloud" for m in result)


@pytest.mark.asyncio
async def test_select_relevant_empty_index_returns_empty(db_session):
    """scope 没记忆 → 立即返回 []。"""
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    msgs = [{"role": "user", "content": "问点什么"}]
    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(side_effect=AssertionError("should not call"))
        result = await svc.select_relevant("empty-scope", msgs)
    assert result == []


@pytest.mark.asyncio
async def test_load_relevant_prepends_block(db_session):
    """load_relevant_memories 返回 <relevant_memories>...</> 格式。"""
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    await svc.write_memory(scope="d", name="a", type="user", description="x", body="内容")
    msgs = [{"role": "user", "content": "问"}]

    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(return_value="[0]")
        block = await svc.load_relevant_memories("d", msgs)

    assert "<relevant_memories>" in block
    assert "内容" in block


@pytest.mark.asyncio
async def test_load_relevant_empty_returns_empty_string(db_session):
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    msgs = [{"role": "user", "content": "问"}]
    with patch("app.domain.agent.memory.LLMClient"):
        block = await svc.load_relevant_memories("empty", msgs)
    assert block == ""


# ============================================================================
# extract
# ============================================================================


@pytest.mark.asyncio
async def test_extract_writes_new(db_session):
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    msgs = [{"role": "user", "content": "记住北北云吞是潮汕口味"}]

    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(return_value=LLM_NEW_EXTRACT)
        count = await svc.extract("d", msgs, session_id="s1")

    assert count == 2
    rows = await svc.list_memories("d")
    assert {r["name"] for r in rows} == {"bb-cloud", "style"}


@pytest.mark.asyncio
async def test_extract_dedup_by_name(db_session):
    """同名已经在 → 跳过。"""
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    await svc.write_memory(scope="d", name="bb-cloud", type="project",
                            description="北北云吞", body="...")
    msgs = [{"role": "user", "content": "..."}]

    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(return_value=LLM_NEW_EXTRACT)
        count = await svc.extract("d", msgs, session_id="s1")

    assert count == 1  # bb-cloud 跳过,只剩 style
    rows = await svc.list_memories("d")
    assert {r["name"] for r in rows} == {"bb-cloud", "style"}


@pytest.mark.asyncio
async def test_extract_invalid_json_noop(db_session):
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    msgs = [{"role": "user", "content": "..."}]
    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(return_value="not json")
        count = await svc.extract("d", msgs, session_id="s1")
    assert count == 0


@pytest.mark.asyncio
async def test_extract_empty_messages_noop(db_session):
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(side_effect=AssertionError("should not"))
        count = await svc.extract("d", [], session_id="s1")
    assert count == 0


@pytest.mark.asyncio
async def test_extract_records_session_id(db_session):
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session)
    msgs = [{"role": "user", "content": "..."}]
    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(return_value=LLM_NEW_EXTRACT)
        await svc.extract("d", msgs, session_id="sess-origin")
    rows = await svc.list_memories("d")
    assert all(r.get("session_id") == "sess-origin" for r in rows)


# ============================================================================
# consolidate
# ============================================================================


@pytest.mark.asyncio
async def test_consolidate_under_threshold_noop(db_session):
    """行数 < 阈值 → 不触发,不动数据。"""
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session, threshold=50)
    for i in range(10):
        await svc.write_memory(scope="d", name=f"m{i}", type="user",
                                description="x", body="")
    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(
            side_effect=AssertionError("should not call LLM below threshold")
        )
        new_count = await svc.consolidate("d")
    assert new_count == 10


@pytest.mark.asyncio
async def test_consolidate_triggers_above_threshold(db_session):
    """行数 ≥ 阈值 → LLM 返新列表,replace_all_bulk 之后行数变更。"""
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session, threshold=5)
    for i in range(6):
        await svc.write_memory(scope="d", name=f"old{i}", type="user",
                                description="x", body="")
    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(return_value=LLM_CONSOLIDATE)
        new_count = await svc.consolidate("d")

    assert new_count == 1
    rows = await svc.list_memories("d")
    assert {r["name"] for r in rows} == {"bb-cloud-merged"}


@pytest.mark.asyncio
async def test_consolidate_invalid_response_keeps_old(db_session):
    """LLM 返非 JSON → 不动数据,返原行数。"""
    from app.domain.agent.memory import MemoryService

    svc = MemoryService(db_session, threshold=3)
    for i in range(3):
        await svc.write_memory(scope="d", name=f"k{i}", type="user",
                                description="x", body="")
    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(return_value="garbage")
        new_count = await svc.consolidate("d")
    assert new_count == 3
    rows = await svc.list_memories("d")
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_consolidate_triggers_via_extract(db_session):
    """extract 后若超过阈值,自动触发 consolidate。"""
    from app.domain.agent.memory import MemoryService

    # 阈值调到 1:第一篇写入后立即触发
    svc = MemoryService(db_session, threshold=1)
    msgs = [{"role": "user", "content": "..."}]
    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        # 第一次调:extract 返 LLM_NEW_EXTRACT;第二次调:consolidate
        # 因为 threshold=1,extract 后立即 consolidate
        MockLLM.return_value.simple_chat = AsyncMock(
            side_effect=[LLM_NEW_EXTRACT, LLM_CONSOLIDATE]
        )
        count = await svc.extract("d", msgs, session_id="s1")

    # extract 写出 2 条,consolidate 缩为 1 条
    rows = await svc.list_memories("d")
    assert len(rows) == 1
    assert rows[0]["name"] == "bb-cloud-merged"


# ============================================================================
# Settings
# ============================================================================


@pytest.mark.asyncio
async def test_settings_has_threshold():
    from app.core.config import get_settings

    settings = get_settings()
    assert hasattr(settings, "memory_consolidate_threshold")
    assert isinstance(settings.memory_consolidate_threshold, int)


@pytest.mark.asyncio
async def test_default_threshold_is_50():
    from app.core.config import get_settings

    settings = get_settings()
    assert settings.memory_consolidate_threshold == 50


def test_phase2_settings_defaults():
    from app.core.config import Settings
    s = Settings(deepseek_api_key="x")
    assert s.memory_dedup_max_distance == 0.15
    assert s.memory_extract_min_chars == 8
