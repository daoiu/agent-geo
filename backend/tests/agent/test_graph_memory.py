"""T3 验证:图记忆预热节点填充 memory_chunk + memory_index_segment。

react_loop._drive_react_loop 在循环开始前一次性调 MemoryService.build_memory_segment
+ load_relevant_memories;react_graph 需要等价节点以保证两路径行为字节级对齐。

测试设计:patch MemoryService 类(预热节点在函数体内 import),patch
get_session_factory 返回 fake factory,验证节点产出两个字段正确。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest


class _FakeFactory:
    """最小 fake factory:`async with f() as session` 产出任意对象。"""

    def __call__(self):
        return _FakeSessionCtx()


class _FakeSessionCtx:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *a):
        return False


@pytest.mark.asyncio
async def test_preheat_populates_memory_chunk_and_index(monkeypatch):
    """预热节点同时产出 memory_chunk(关联记忆)与 memory_index_segment(索引段)。"""
    from app.domain.agent.langgraph_nodes import memory_preheat

    class _Svc:
        def __init__(self, _s):
            pass

        async def build_memory_segment(self, scope):
            return "【L2 索引】brandX"

        async def load_relevant_memories(self, scope, history):
            return {"items": [{"text": "偏好A", "score": 0.9}]}

    monkeypatch.setattr(memory_preheat, "MemoryService", _Svc)
    monkeypatch.setattr(memory_preheat, "get_session_factory", lambda: _FakeFactory())

    state = {
        "messages": [],
        "session_id": "s1",
        "device_id": "dev1",
    }
    out = await memory_preheat.memory_preheat_node(state, None)

    # 两字段都填充
    assert out["memory_index_segment"].startswith("【L2")
    assert out["memory_index_segment"] == "【L2 索引】brandX"
    assert out["memory_chunk"]["items"][0]["text"] == "偏好A"


@pytest.mark.asyncio
async def test_preheat_returns_empty_on_failure(monkeypatch):
    """预热失败时降级为空,不阻塞主流程(react_loop 等价行为)。"""
    from app.domain.agent.langgraph_nodes import memory_preheat

    class _SvcBoom:
        def __init__(self, _s):
            pass

        async def build_memory_segment(self, scope):
            raise RuntimeError("db down")

        async def load_relevant_memories(self, scope, history):
            raise RuntimeError("db down")

    monkeypatch.setattr(memory_preheat, "MemoryService", _SvcBoom)
    monkeypatch.setattr(memory_preheat, "get_session_factory", lambda: _FakeFactory())

    state = {"messages": [], "session_id": "s2", "device_id": None}
    out = await memory_preheat.memory_preheat_node(state, None)

    # 失败静默,字段为空
    assert out["memory_index_segment"] == ""
    assert out["memory_chunk"] is None