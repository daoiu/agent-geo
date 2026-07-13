"""react_loop L2 记忆层集成测试。

3 个端到端场景:
1. 预设 memory,ReAct 跑一轮 → system prompt 出现索引段
2. 预设 memory,LLM side-query 返 [0] → 第一条 user turn 拼上 relevant block
3. turn_complete 后 fire-and-forget 触发 extract(device_id + session_id)
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_memory_vectors():
    """默认 mock 向量依赖,杜绝真加载 bge(沙箱无外网会卡死)/写真 ChromaDB。
    个别用例的 with patch(...) 会在其块内覆盖。"""
    with patch("app.domain.agent.memory.EmbeddingService") as MockEmb, \
         patch("app.domain.agent.memory.MemoryVectorIndex") as MockVidx:
        MockEmb.embed.side_effect = lambda texts: [[1.0] + [0.0] * 511 for _ in texts]
        MockVidx.return_value.ids_in_scope.return_value = set()
        MockVidx.return_value.query.return_value = []
        yield


def _fake_chat_factory(captured: list[list[dict[str, Any]]]):
    """造一个 async fake 捕获 messages 给后续断言,LLM 返回无 tool_calls 直接 turn_complete。"""

    async def fake_chat(messages, tools):
        captured.append(messages)
        return {"content": "stub answer", "tool_calls": []}

    return fake_chat


async def _ensure_session(db_session, session_id: str) -> None:
    """AgentMessageORM 有 session_id FK → 必须先建 AgentSessionORM。"""
    from app.models.orm_v04 import AgentSessionORM

    db_session.add(AgentSessionORM(id=session_id, title=f"session {session_id}"))
    await db_session.commit()


async def _drain_pending_extracts() -> None:
    """清空 _PENDING_EXTRACTS 中遗留任务,避免跨测试污染。

    pytest-asyncio 为每个测试创建新 event loop;如果上个测试的 task 绑在旧 loop 上,
    在新 loop 里 await 会失败。直接 discard(不 await):残留任务的 callback 仍会
    在它的 loop 关闭时尝试 discard 自己,但 set 已空,discard 是 no-op。
    """
    from app.domain.agent.react_loop import _PENDING_EXTRACTS
    _PENDING_EXTRACTS.clear()


# ---------------------------------------------------------------------------
# 1. system prompt 出现索引段
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_includes_memory_index(db_session):
    """预写 1 条 memory → build_memory_segment 拼到 system,ReAct 跑一轮可见。"""
    from app.domain.agent.memory import MemoryService
    await _ensure_session(db_session, "s-int-1")
    await _drain_pending_extracts()
    from app.domain.agent.react_loop import run_agent_turn

    svc = MemoryService(db_session)
    await svc.write_memory(
        scope="device-int", name="bb-wonton", type="project",
        description="wonton brand facts", body="wontons are great",
        session_id="s-int-1",
    )

    captured: list[list[dict[str, Any]]] = []
    fake_chat = _fake_chat_factory(captured)
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
        MockLLM.return_value.chat_with_tools = fake_chat
        with patch("app.domain.agent.memory.LLMClient") as MockMemLLM:
            MockMemLLM.return_value.simple_chat = AsyncMock(return_value="[]")
            events = []
            async for e in run_agent_turn(
                session_id="s-int-1", user_message="?", device_id="device-int"
            ):
                events.append(e)

    sys_content = captured[0][0]["content"]
    assert "Memories available" in sys_content
    assert "bb-wonton — wonton brand facts" in sys_content


# ---------------------------------------------------------------------------
# 2. relevant memory 拼到 user turn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_turn_includes_relevant_memory_block(db_session):
    """side-query LLM 返 [0],对应 memory body 应出现在第一条 user 消息。"""
    from app.domain.agent.memory import MemoryService
    await _ensure_session(db_session, "s-int-2")
    await _drain_pending_extracts()
    from app.domain.agent.react_loop import run_agent_turn

    svc = MemoryService(db_session)
    m = await svc.write_memory(
        scope="device-int", name="bb-wonton", type="project",
        description="wonton brand facts", body="潮汕口味,堂食为主",
        session_id="s-int-2",
    )

    captured: list[list[dict[str, Any]]] = []
    fake_chat = _fake_chat_factory(captured)
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
        MockLLM.return_value.chat_with_tools = fake_chat
        with patch("app.domain.agent.memory.EmbeddingService") as MockEmb, \
             patch("app.domain.agent.memory.MemoryVectorIndex") as MockVidx:
            # 向量 select 命中这条 memory
            MockEmb.embed.side_effect = lambda texts: [[1.0] + [0.0] * 511 for _ in texts]
            MockVidx.return_value.ids_in_scope.return_value = {m["id"]}
            MockVidx.return_value.query.return_value = [{"id": m["id"], "distance": 0.1}]
            events = []
            async for e in run_agent_turn(
                session_id="s-int-2", user_message="see memory", device_id="device-int"
            ):
                events.append(e)

    user_msg = next(m2 for m2 in captured[0] if m2["role"] == "user")
    assert "<relevant_memories>" in user_msg["content"]
    assert "潮汕口味" in user_msg["content"]


# ---------------------------------------------------------------------------
# 3. turn_complete 后 fire-and-forget 触发 extract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_fires_after_turn_complete(db_session):
    """run_agent_turn turn_complete 时调一次 _do_extract_after_turn(device, sid, history)。"""
    from app.domain.agent.react_loop import (
        _PENDING_EXTRACTS,
        run_agent_turn,
    )

    await _ensure_session(db_session, "s-int-3")
    await _drain_pending_extracts()

    fake_chat = _fake_chat_factory([])
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
        MockLLM.return_value.chat_with_tools = fake_chat
        with patch("app.domain.agent.memory.LLMClient") as MockMemLLM:
            MockMemLLM.return_value.simple_chat = AsyncMock(return_value="[]")
            with patch(
                "app.domain.agent.react_loop._do_extract_after_turn",
                new_callable=AsyncMock,
            ) as mock_extract:
                events = []
                async for e in run_agent_turn(
                    session_id="s-int-3",
                    user_message="?",
                    device_id="device-int",
                ):
                    events.append(e)
                # drain pending extracts (fire-and-forget task scheduler)
                for task in list(_PENDING_EXTRACTS):
                    await task

    assert any(e["event"] == "turn_complete" for e in events)
    assert mock_extract.called
    # _do_extract_after_turn(device_id, session_id, history) 是位置参数
    args = mock_extract.call_args.args
    assert args[0] == "device-int"
    assert args[1] == "s-int-3"
    assert isinstance(args[2], list)


# ---------------------------------------------------------------------------
# 4. device_id 缺失时不报错(scope fallback anon:session_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_turn_without_device_id(db_session):
    """不传 device_id → 不报错 → scope = 'anon:<session_id>'。"""
    from app.domain.agent.memory import MemoryService
    await _ensure_session(db_session, "s-int-4")
    await _drain_pending_extracts()
    from app.domain.agent.react_loop import (
        _PENDING_EXTRACTS,
        run_agent_turn,
        scope_key,  # noqa: F401
    )

    captured: list[list[dict[str, Any]]] = []
    fake_chat = _fake_chat_factory(captured)
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
        MockLLM.return_value.chat_with_tools = fake_chat
        with patch("app.domain.agent.memory.LLMClient") as MockMemLLM:
            MockMemLLM.return_value.simple_chat = AsyncMock(return_value="[]")
            events = []
            async for e in run_agent_turn(
                session_id="s-int-4", user_message="?"  # no device_id
            ):
                events.append(e)
            for task in list(_PENDING_EXTRACTS):
                await task

    sys_content = captured[0][0]["content"]
    # 没有 memory → 不应有索引段
    assert "Memories available" not in sys_content
    assert any(e["event"] == "turn_complete" for e in events)


# ---------------------------------------------------------------------------
# 5. scope 隔离 — 不同 device_id 看不同 memory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scope_isolates_memories_per_device(db_session):
    """device-A 的 memory 不会出现在 device-B 的 system prompt。"""
    from app.domain.agent.memory import MemoryService
    await _ensure_session(db_session, "s-int-5")
    await _drain_pending_extracts()
    from app.domain.agent.react_loop import (
        _PENDING_EXTRACTS,
        run_agent_turn,
    )

    svc = MemoryService(db_session)
    await svc.write_memory(
        scope="device-A", name="only-A", type="project",
        description="A secret", body="only for A",
        session_id="s-int-5",
    )

    captured: list[list[dict[str, Any]]] = []
    fake_chat = _fake_chat_factory(captured)
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
        MockLLM.return_value.chat_with_tools = fake_chat
        with patch("app.domain.agent.memory.LLMClient") as MockMemLLM:
            MockMemLLM.return_value.simple_chat = AsyncMock(return_value="[]")
            events = []
            async for e in run_agent_turn(
                session_id="s-int-5", user_message="?", device_id="device-B"
            ):
                events.append(e)
            for task in list(_PENDING_EXTRACTS):
                await task

    sys_content = captured[0][0]["content"]
    assert "A secret" not in sys_content
    assert "only-A" not in sys_content
