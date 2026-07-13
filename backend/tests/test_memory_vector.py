"""Tests for MemoryVectorIndex (Phase 2) — 用 tmp chroma_path 测真 ChromaDB。"""
from __future__ import annotations

import pytest


@pytest.fixture
def vidx(tmp_path, monkeypatch):
    """隔离的 MemoryVectorIndex:tmp chroma_path + 重置类级 client 单例。"""
    from app.core.config import get_settings
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    get_settings.cache_clear()
    import app.domain.agent.memory_vector as mv
    mv.MemoryVectorIndex._client = None  # 防止跨测试复用别的 path
    idx = mv.MemoryVectorIndex()
    yield idx
    mv.MemoryVectorIndex._client = None


def _vec(seed: float) -> list[float]:
    """确定性 512 维向量,seed 决定方向。"""
    return [seed] + [0.0] * 511


def test_add_and_query_returns_nearest(vidx):
    vidx.add("m1", "scopeA", "user", "喜欢简洁", _vec(1.0))
    vidx.add("m2", "scopeA", "user", "别的", _vec(-1.0))
    hits = vidx.query(_vec(1.0), "scopeA", top_k=1)
    assert hits[0]["id"] == "m1"
    assert "distance" in hits[0]


def test_query_scope_isolation(vidx):
    vidx.add("a1", "scopeA", "user", "x", _vec(1.0))
    vidx.add("b1", "scopeB", "user", "x", _vec(1.0))
    hits = vidx.query(_vec(1.0), "scopeB", top_k=5)
    assert [h["id"] for h in hits] == ["b1"]


def test_delete_scope(vidx):
    vidx.add("a1", "scopeA", "user", "x", _vec(1.0))
    vidx.delete_scope("scopeA")
    assert vidx.query(_vec(1.0), "scopeA", top_k=5) == []


def test_ids_in_scope(vidx):
    vidx.add("a1", "scopeA", "user", "x", _vec(1.0))
    vidx.add("a2", "scopeA", "user", "y", _vec(0.5))
    vidx.add("b1", "scopeB", "user", "z", _vec(1.0))
    assert vidx.ids_in_scope("scopeA") == {"a1", "a2"}
