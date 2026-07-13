# Phase 2 记忆层向量化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 L2 记忆的 `select_relevant` 从 LLM 调用改为 ChromaDB 纯向量 cosine top-k，并给 `extract` 加向量近邻去重与短-turn 门控。

**Architecture:** SQLite `AgentMemoryORM` 保持真相源不加向量列；新建 ChromaDB 单 collection `agent_memories`（scope 存 metadata）作派生索引。`MemoryVectorIndex` 封装 add/query/delete/ids；`MemoryService` 在 write 时双写向量、select 时向量检索（失败降级 recency）、extract 时向量判重（失败降级 exact-name）+ 门控、consolidate 时同步向量。存量无向量记忆由 `_ensure_vectors` 在 select 前 lazy 回填。

**Tech Stack:** Python 3.11 / ChromaDB 0.5.20 / sentence-transformers bge-small-zh-v1.5(512维) / SQLAlchemy async / pytest + unittest.mock

## Global Constraints

- **向量存储 = ChromaDB 单 collection `agent_memories`**，`metadata={"scope", "type"}`，`hnsw:space=cosine`。**不给 `AgentMemoryORM` 加向量列**（无 schema 变更、无 Alembic）。
- **query 用 `query_embeddings=`（预计算 bge 向量）+ `where={"scope": scope}`**，绝不用 `query_texts=`——避免 `VectorIndex.query` 那个 add/query embedding 来源不一致的既有坑。
- **SQLite 权威、ChromaDB 可重建**：任何 ChromaDB / EmbeddingService 失败 → log warning + 降级，不阻塞 turn。select 失败降级 `list_by_scope(scope)[:k]`（recency）；去重失败降级 exact-name only。
- **embed 文本 = `f"{name}。{description}"`**（不含 body_md）。
- **`select_relevant` 零 LLM 调用**（退出标准之一）。`extract` / `consolidate` 仍用 `simple_chat`（LLM），不变。
- **两个新 Settings**：`memory_dedup_max_distance: float = 0.15`、`memory_extract_min_chars: int = 8`。
- **`MemoryService` 公开签名不变**（`write_memory` / `select_relevant` / `load_relevant_memories` / `extract` / `consolidate` / `build_memory_segment`）。
- **测试隔离**：`MemoryService` 单元测试一律 patch 掉 `MemoryVectorIndex` 与 `EmbeddingService`（用假向量），**不碰真实 ChromaDB / 不加载 bge**（沙箱无外网）。只有 `test_memory_vector.py` 用 tmp chroma_path 测真索引。
- **非行为等价**：现有 `test_memory_service.py` 里依赖 LLM select 的用例（`test_select_relevant_uses_llm` / `test_select_relevant_keyword_fallback` / `test_load_relevant_prepends_block`）需**重写**为向量路径。

---

### Task 1: Settings 两个新配置项

**Files:**
- Modify: `backend/app/core/config.py:90`（`memory_consolidate_threshold` 附近）
- Test: `backend/tests/test_memory_service.py`（末尾加一个 Settings 断言）

**Interfaces:**
- Produces: `Settings.memory_dedup_max_distance: float = 0.15`、`Settings.memory_extract_min_chars: int = 8`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_memory_service.py` 末尾追加：

```python
def test_phase2_settings_defaults():
    from app.core.config import Settings
    s = Settings(deepseek_api_key="x")
    assert s.memory_dedup_max_distance == 0.15
    assert s.memory_extract_min_chars == 8
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_memory_service.py::test_phase2_settings_defaults -v`
Expected: FAIL —— `AttributeError: 'Settings' object has no attribute 'memory_dedup_max_distance'`

- [ ] **Step 3: 加配置项**

在 `backend/app/core/config.py` 的 `memory_consolidate_threshold: int = 50` 行下方加：

```python
    memory_dedup_max_distance: float = 0.15  # cosine distance < 此值视为语义重复
    memory_extract_min_chars: int = 8         # 最近 user 文本短于此则跳过 extract
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_memory_service.py::test_phase2_settings_defaults -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/config.py backend/tests/test_memory_service.py
git commit -m "feat(memory): Phase2 新增 dedup 距离阈值 + extract 门控字数配置"
```

---

### Task 2: MemoryVectorIndex（ChromaDB 单 collection 封装）

**Files:**
- Create: `backend/app/domain/agent/memory_vector.py`
- Test: `backend/tests/test_memory_vector.py`

**Interfaces:**
- Produces:
  - `class MemoryVectorIndex` — `__init__(self)`（连 `agent_memories` collection）
  - `add(self, memory_id: str, scope: str, mtype: str, text: str, embedding: list[float]) -> None`
  - `query(self, embedding: list[float], scope: str, top_k: int = 5) -> list[dict]` — 返回 `[{"id": str, "distance": float}]`，距离升序，`where={"scope": scope}`
  - `delete_scope(self, scope: str) -> None`
  - `delete_ids(self, ids: list[str]) -> None`
  - `ids_in_scope(self, scope: str) -> set[str]`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_memory_vector.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_memory_vector.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.domain.agent.memory_vector'`

- [ ] **Step 3: 实现 MemoryVectorIndex**

新建 `backend/app/domain/agent/memory_vector.py`：

```python
"""ChromaDB 单 collection 封装 L2 记忆向量(Phase 2)。

collection "agent_memories":scope 存 metadata,一条记忆一个向量。
真相源是 SQLite AgentMemoryORM;本索引可重建。
"""
from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings

_COLLECTION = "agent_memories"


class MemoryVectorIndex:
    _client = None  # process-singleton

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            settings = get_settings()
            cls._client = chromadb.PersistentClient(
                path=settings.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return cls._client

    def __init__(self) -> None:
        client = self._get_client()
        self._c = client.get_or_create_collection(
            name=_COLLECTION, metadata={"hnsw:space": "cosine"},
        )

    def add(self, memory_id: str, scope: str, mtype: str,
            text: str, embedding: list[float]) -> None:
        self._c.upsert(
            ids=[memory_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[{"scope": scope, "type": mtype}],
        )

    def query(self, embedding: list[float], scope: str,
              top_k: int = 5) -> list[dict]:
        res = self._c.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where={"scope": scope},
        )
        ids = res.get("ids", [[]])[0] if res.get("ids") else []
        dists = res.get("distances", [[]])[0] if res.get("distances") else []
        return [
            {"id": ids[i], "distance": dists[i] if i < len(dists) else None}
            for i in range(len(ids))
        ]

    def delete_scope(self, scope: str) -> None:
        self._c.delete(where={"scope": scope})

    def delete_ids(self, ids: list[str]) -> None:
        if ids:
            self._c.delete(ids=ids)

    def ids_in_scope(self, scope: str) -> set[str]:
        res = self._c.get(where={"scope": scope})
        return set(res.get("ids", []))
```

> 用 `upsert`（非 `add`）：同 id 重复写时覆盖而非报错，便于回填/consolidate 幂等。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_memory_vector.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/domain/agent/memory_vector.py backend/tests/test_memory_vector.py
git commit -m "feat(memory): MemoryVectorIndex — ChromaDB 单 collection + scope 隔离"
```

---

### Task 3: write_memory 双写向量 + _ensure_vectors 回填

**Files:**
- Modify: `backend/app/domain/agent/memory.py`（import；`write_memory` 尾部双写；新增 `_ensure_vectors`）
- Test: `backend/tests/test_memory_service.py`（加双写 + 回填用例）

**Interfaces:**
- Consumes: `MemoryVectorIndex`（Task 2）；`EmbeddingService.embed(texts) -> list[list[float]]`（现有 `app.services.embedding`）
- Produces:
  - `MemoryService._embed_text(name, description) -> str`（= `f"{name}。{description}"`）
  - `MemoryService._ensure_vectors(scope) -> None`（lazy 回填缺失向量，失败静默）
  - `write_memory` 写 SQLite 后 best-effort add 向量

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_memory_service.py` 加（顶部已有 `from unittest.mock import AsyncMock, patch`）：

```python
@pytest.mark.asyncio
async def test_write_memory_double_writes_vector(db_session):
    from app.domain.agent.memory import MemoryService
    svc = MemoryService(db_session)
    with patch("app.domain.agent.memory.EmbeddingService") as MockEmb, \
         patch("app.domain.agent.memory.MemoryVectorIndex") as MockVidx:
        MockEmb.embed.return_value = [[1.0] + [0.0] * 511]
        await svc.write_memory(scope="d", name="简洁", type="user",
                               description="喜欢简洁", body="...")
        MockVidx.return_value.add.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_vectors_backfills_missing(db_session):
    from app.domain.agent.memory import MemoryService
    svc = MemoryService(db_session)
    # 先绕过双写直接写 SQLite（模拟存量无向量记忆）
    with patch("app.domain.agent.memory.MemoryVectorIndex"), \
         patch("app.domain.agent.memory.EmbeddingService"):
        await svc.write_memory(scope="d", name="a", type="user",
                               description="da", body="b")
    with patch("app.domain.agent.memory.EmbeddingService") as MockEmb, \
         patch("app.domain.agent.memory.MemoryVectorIndex") as MockVidx:
        MockVidx.return_value.ids_in_scope.return_value = set()  # 向量库空
        MockEmb.embed.return_value = [[1.0] + [0.0] * 511]
        await svc._ensure_vectors("d")
        MockVidx.return_value.add.assert_called_once()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_memory_service.py::test_write_memory_double_writes_vector tests/test_memory_service.py::test_ensure_vectors_backfills_missing -v`
Expected: FAIL —— `AttributeError`（`EmbeddingService` 未在 memory 模块导入 / 无 `_ensure_vectors`）

- [ ] **Step 3: 实现双写 + 回填**

在 `backend/app/domain/agent/memory.py` 顶部 import 区加：

```python
from app.domain.agent.memory_vector import MemoryVectorIndex
from app.services.embedding import EmbeddingService
```

在 `MemoryService` 类内加助手：

```python
    @staticmethod
    def _embed_text(name: str, description: str) -> str:
        return f"{name}。{description}"

    async def _ensure_vectors(self, scope: str) -> None:
        """lazy 回填:补齐该 scope 在向量库缺失的记忆。失败静默。"""
        try:
            rows = await self.repo.list_by_scope(scope)
            if not rows:
                return
            vidx = MemoryVectorIndex()
            have = vidx.ids_in_scope(scope)
            missing = [r for r in rows if r["id"] not in have]
            if not missing:
                return
            texts = [self._embed_text(r["name"], r["description"]) for r in missing]
            embs = EmbeddingService.embed(texts)
            for r, e in zip(missing, embs):
                vidx.add(r["id"], scope, r["type"],
                         self._embed_text(r["name"], r["description"]), e)
        except Exception as e:  # noqa: BLE001
            logger.warning("ensure_vectors_failed", scope=scope, error=str(e))
```

改 `write_memory`：在 `return await self.repo.create(...)` 之前改为先拿到 created，再 best-effort 双写：

```python
        created = await self.repo.create(
            scope=scope,
            name=name,
            description=description,
            type=type,
            body_md=body,
            session_id=session_id,
        )
        try:
            emb = EmbeddingService.embed([self._embed_text(name, description)])[0]
            MemoryVectorIndex().add(
                created["id"], scope, type,
                self._embed_text(name, description), emb,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("write_memory_vector_failed",
                           scope=scope, name=name, error=str(e))
        return created
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_memory_service.py::test_write_memory_double_writes_vector tests/test_memory_service.py::test_ensure_vectors_backfills_missing -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/domain/agent/memory.py backend/tests/test_memory_service.py
git commit -m "feat(memory): write_memory 双写向量 + _ensure_vectors lazy 回填"
```

---

### Task 4: select_relevant 改向量检索（删 LLM）

**Files:**
- Modify: `backend/app/domain/agent/memory.py`（`select_relevant` 整体重写）
- Test: `backend/tests/test_memory_service.py`（**重写** select 用例）

**Interfaces:**
- Consumes: `_ensure_vectors`（Task 3）；`MemoryVectorIndex.query`（Task 2）；`EmbeddingService.embed`
- Produces: `select_relevant(scope, messages, k=5) -> list[dict]` — 向量 top-k；无 recent → `[]`；向量失败 → `list_by_scope(scope)[:k]`

- [ ] **Step 1: 重写 select 测试（替换旧 LLM 版）**

删除 `test_memory_service.py` 中这三个旧用例：`test_select_relevant_uses_llm`、`test_select_relevant_keyword_fallback`、`test_load_relevant_prepends_block`。替换为：

```python
@pytest.mark.asyncio
async def test_select_relevant_uses_vector_no_llm(db_session):
    from app.domain.agent.memory import MemoryService
    svc = MemoryService(db_session)
    # 两条记忆
    with patch("app.domain.agent.memory.MemoryVectorIndex"), \
         patch("app.domain.agent.memory.EmbeddingService"):
        m1 = await svc.write_memory(scope="d", name="简洁", type="user",
                                    description="喜欢简洁回复", body="x")
        await svc.write_memory(scope="d", name="潮汕", type="project",
                               description="北北云吞潮汕口味", body="y")
    msgs = [{"role": "user", "content": "回复能不能简洁点"}]
    with patch("app.domain.agent.memory.EmbeddingService") as MockEmb, \
         patch("app.domain.agent.memory.MemoryVectorIndex") as MockVidx, \
         patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockVidx.return_value.ids_in_scope.return_value = {m1["id"]}
        MockEmb.embed.return_value = [[1.0] + [0.0] * 511]
        MockVidx.return_value.query.return_value = [{"id": m1["id"], "distance": 0.1}]
        MockLLM.return_value.simple_chat = AsyncMock(
            side_effect=AssertionError("select 不该调 LLM"))
        result = await svc.select_relevant("d", msgs, k=5)
    assert len(result) == 1
    assert result[0]["id"] == m1["id"]


@pytest.mark.asyncio
async def test_select_relevant_empty_recent_returns_empty(db_session):
    from app.domain.agent.memory import MemoryService
    svc = MemoryService(db_session)
    with patch("app.domain.agent.memory.MemoryVectorIndex"), \
         patch("app.domain.agent.memory.EmbeddingService"):
        await svc.write_memory(scope="d", name="a", type="user",
                               description="da", body="b")
    # 无 user 文本
    result = await svc.select_relevant("d", [{"role": "assistant", "content": "hi"}])
    assert result == []


@pytest.mark.asyncio
async def test_select_relevant_vector_fail_recency_fallback(db_session):
    from app.domain.agent.memory import MemoryService
    svc = MemoryService(db_session)
    with patch("app.domain.agent.memory.MemoryVectorIndex"), \
         patch("app.domain.agent.memory.EmbeddingService"):
        await svc.write_memory(scope="d", name="a", type="user",
                               description="da", body="b")
    msgs = [{"role": "user", "content": "随便问点什么"}]
    with patch("app.domain.agent.memory.EmbeddingService") as MockEmb, \
         patch("app.domain.agent.memory.MemoryVectorIndex") as MockVidx:
        MockVidx.return_value.ids_in_scope.return_value = set()
        MockEmb.embed.side_effect = Exception("bge 加载失败")
        result = await svc.select_relevant("d", msgs, k=5)
    assert len(result) == 1  # recency 降级仍返回


@pytest.mark.asyncio
async def test_load_relevant_prepends_block_vector(db_session):
    from app.domain.agent.memory import MemoryService
    svc = MemoryService(db_session)
    with patch("app.domain.agent.memory.MemoryVectorIndex"), \
         patch("app.domain.agent.memory.EmbeddingService"):
        m1 = await svc.write_memory(scope="d", name="简洁", type="user",
                                    description="喜欢简洁", body="正文")
    msgs = [{"role": "user", "content": "简洁"}]
    with patch("app.domain.agent.memory.EmbeddingService") as MockEmb, \
         patch("app.domain.agent.memory.MemoryVectorIndex") as MockVidx:
        MockVidx.return_value.ids_in_scope.return_value = {m1["id"]}
        MockEmb.embed.return_value = [[1.0] + [0.0] * 511]
        MockVidx.return_value.query.return_value = [{"id": m1["id"], "distance": 0.1}]
        block = await svc.load_relevant_memories("d", msgs)
    assert "<relevant_memories>" in block
    assert "简洁" in block
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_memory_service.py -k "select_relevant or load_relevant" -v`
Expected: FAIL（新用例断言向量路径，旧实现走 LLM）

- [ ] **Step 3: 重写 select_relevant**

把 `memory.py` 的 `select_relevant`（`memory.py:135-189`）整体替换为：

```python
    async def select_relevant(
        self,
        scope: str,
        messages: list[dict],
        k: int = 5,
    ) -> list[dict]:
        recent = self._recent_user_text(messages)
        if not recent.strip():
            return []

        await self._ensure_vectors(scope)
        try:
            qv = EmbeddingService.embed([recent])[0]
            hits = MemoryVectorIndex().query(qv, scope, top_k=k)
            out: list[dict] = []
            for h in hits:
                row = await self.repo.get_by_id(h["id"])
                if row:
                    out.append(row)
            return out
        except Exception as e:  # noqa: BLE001
            logger.warning("select_relevant_vector_failed",
                           scope=scope, error=str(e))
            rows = await self.repo.list_by_scope(scope)
            return rows[:k]
```

同时删除 `_recent_user_text` 之外不再使用的 import（若 `re` / `json` 仍被 extract/consolidate 用则保留——**检查后再删**，避免误删）。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_memory_service.py -k "select_relevant or load_relevant" -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/domain/agent/memory.py backend/tests/test_memory_service.py
git commit -m "feat(memory): select_relevant 改纯向量 cosine top-k,删每轮 LLM 调用"
```

---

### Task 5: extract 门控 + 向量近邻去重

**Files:**
- Modify: `backend/app/domain/agent/memory.py`（`extract` 加门控 + 去重）
- Test: `backend/tests/test_memory_service.py`（加门控 + 去重用例）

**Interfaces:**
- Consumes: `Settings.memory_extract_min_chars` / `memory_dedup_max_distance`（Task 1）；`MemoryVectorIndex.query`、`EmbeddingService.embed`
- Produces: `extract` 短-turn 返回 0（不调 LLM）；候选向量近邻 `< memory_dedup_max_distance` 跳过

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_extract_gate_skips_short_turn(db_session):
    from app.domain.agent.memory import MemoryService
    svc = MemoryService(db_session)
    msgs = [{"role": "user", "content": "好"}]  # < 8 字
    with patch("app.domain.agent.memory.LLMClient") as MockLLM:
        MockLLM.return_value.simple_chat = AsyncMock(
            side_effect=AssertionError("短 turn 不该调 LLM"))
        count = await svc.extract("d", msgs, session_id="s1")
    assert count == 0


@pytest.mark.asyncio
async def test_extract_dedup_by_vector_distance(db_session):
    from app.domain.agent.memory import MemoryService
    svc = MemoryService(db_session)
    # 已有一条"喜欢简洁"
    with patch("app.domain.agent.memory.MemoryVectorIndex"), \
         patch("app.domain.agent.memory.EmbeddingService"):
        await svc.write_memory(scope="d", name="简洁", type="user",
                               description="喜欢简洁", body="x")
    # LLM 蒸馏出语义重复的"回复要精炼"
    llm_out = '[{"name":"精炼","type":"user","description":"回复要精炼","body":"z"}]'
    msgs = [{"role": "user", "content": "以后回复都精炼一点谢谢"}]
    with patch("app.domain.agent.memory.LLMClient") as MockLLM, \
         patch("app.domain.agent.memory.EmbeddingService") as MockEmb, \
         patch("app.domain.agent.memory.MemoryVectorIndex") as MockVidx:
        MockLLM.return_value.simple_chat = AsyncMock(return_value=llm_out)
        MockEmb.embed.return_value = [[1.0] + [0.0] * 511]
        # 近邻距离 0.05 < 0.15 阈值 → 判重跳过
        MockVidx.return_value.query.return_value = [{"id": "x", "distance": 0.05}]
        count = await svc.extract("d", msgs, session_id="s1")
    assert count == 0  # 语义重复被拦


@pytest.mark.asyncio
async def test_extract_writes_when_distant(db_session):
    from app.domain.agent.memory import MemoryService
    svc = MemoryService(db_session)
    llm_out = '[{"name":"潮汕","type":"project","description":"北北云吞潮汕口味","body":"z"}]'
    msgs = [{"role": "user", "content": "记住北北云吞是潮汕口味"}]
    with patch("app.domain.agent.memory.LLMClient") as MockLLM, \
         patch("app.domain.agent.memory.EmbeddingService") as MockEmb, \
         patch("app.domain.agent.memory.MemoryVectorIndex") as MockVidx:
        MockLLM.return_value.simple_chat = AsyncMock(return_value=llm_out)
        MockEmb.embed.return_value = [[1.0] + [0.0] * 511]
        MockVidx.return_value.query.return_value = [{"id": "other", "distance": 0.9}]
        count = await svc.extract("d", msgs, session_id="s1")
    assert count == 1  # 距离远,正常写入
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_memory_service.py -k "extract_gate or extract_dedup_by_vector or extract_writes_when_distant" -v`
Expected: FAIL（门控/向量去重未实现）

- [ ] **Step 3: 实现门控 + 去重**

在 `extract` 开头（`dialogue_parts` 构建之前）加门控：

```python
        recent = self._recent_user_text(messages)
        if len(recent.strip()) < get_settings().memory_extract_min_chars:
            return 0
```

在写入循环里，`existing_match = await self.repo.get_by_name(...)` 判重之后、`write_memory` 之前，加向量近邻判重：

```python
            existing_match = await self.repo.get_by_name(scope, name)
            if existing_match:
                continue
            # 向量近邻语义去重(失败降级 exact-name only)
            try:
                cv = EmbeddingService.embed([self._embed_text(name, desc)])[0]
                nearest = MemoryVectorIndex().query(cv, scope, top_k=1)
                if nearest and nearest[0]["distance"] is not None and \
                        nearest[0]["distance"] < get_settings().memory_dedup_max_distance:
                    continue
            except Exception as e:  # noqa: BLE001
                logger.warning("extract_dedup_vector_failed",
                               scope=scope, name=name, error=str(e))
            await self.write_memory(...)  # 原有调用不变
            count += 1
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_memory_service.py -k "extract" -v`
Expected: PASS（含原有 extract 用例不回归）

- [ ] **Step 5: 提交**

```bash
git add backend/app/domain/agent/memory.py backend/tests/test_memory_service.py
git commit -m "feat(memory): extract 短-turn 门控 + 向量近邻语义去重"
```

---

### Task 6: consolidate 同步向量

**Files:**
- Modify: `backend/app/domain/agent/memory.py`（`consolidate` 尾部同步向量）
- Test: `backend/tests/test_memory_service.py`（加同步用例）

**Interfaces:**
- Consumes: `MemoryVectorIndex.delete_scope` / `add`（Task 2）；`replace_all_bulk`（现有）
- Produces: `consolidate` replace 后 delete_scope 旧向量 + 为新记忆 add 向量

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_consolidate_syncs_vectors(db_session):
    from app.domain.agent.memory import MemoryService
    svc = MemoryService(db_session, threshold=2)
    with patch("app.domain.agent.memory.MemoryVectorIndex"), \
         patch("app.domain.agent.memory.EmbeddingService"):
        await svc.write_memory(scope="d", name="a", type="user",
                               description="da", body="b")
        await svc.write_memory(scope="d", name="b", type="user",
                               description="db", body="c")
    merged = '[{"name":"merged","type":"user","description":"合并","body":"z"}]'
    with patch("app.domain.agent.memory.LLMClient") as MockLLM, \
         patch("app.domain.agent.memory.EmbeddingService") as MockEmb, \
         patch("app.domain.agent.memory.MemoryVectorIndex") as MockVidx:
        MockLLM.return_value.simple_chat = AsyncMock(return_value=merged)
        MockEmb.embed.return_value = [[1.0] + [0.0] * 511]
        await svc.consolidate("d")
        MockVidx.return_value.delete_scope.assert_called_once_with("d")
        assert MockVidx.return_value.add.called
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_memory_service.py::test_consolidate_syncs_vectors -v`
Expected: FAIL（consolidate 未同步向量）

- [ ] **Step 3: 实现同步**

在 `consolidate` 的 `await self.repo.replace_all_bulk(scope, new_items)` 之后加：

```python
        await self.repo.replace_all_bulk(scope, new_items)
        # 同步向量:清 scope 旧向量,为新记录回填(失败静默,下次 select 补)
        try:
            vidx = MemoryVectorIndex()
            vidx.delete_scope(scope)
            fresh = await self.repo.list_by_scope(scope)
            if fresh:
                texts = [self._embed_text(r["name"], r["description"]) for r in fresh]
                embs = EmbeddingService.embed(texts)
                for r, e in zip(fresh, embs):
                    vidx.add(r["id"], scope, r["type"],
                             self._embed_text(r["name"], r["description"]), e)
        except Exception as e:  # noqa: BLE001
            logger.warning("consolidate_vector_sync_failed",
                           scope=scope, error=str(e))
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_memory_service.py::test_consolidate_syncs_vectors -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/domain/agent/memory.py backend/tests/test_memory_service.py
git commit -m "feat(memory): consolidate 后同步 ChromaDB 向量(delete_scope + 回填)"
```

---

### Task 7: 集成测试更新 + 全量回归

**Files:**
- Modify: `backend/tests/test_react_loop_memory_integration.py`（select 走向量，不再 mock select 的 LLM）
- Test: 全量

**Interfaces:**
- Consumes: 前 6 个 Task 的成果

- [ ] **Step 1: 审查集成测试是否 mock 了 select 的 LLM**

Run: `grep -n "select_relevant\|simple_chat\|load_relevant\|MemoryVectorIndex\|EmbeddingService" backend/tests/test_react_loop_memory_integration.py`
若某用例通过 mock `simple_chat` 让 select 返回记忆，改为 mock `MemoryVectorIndex` + `EmbeddingService`（参照 Task 4 Step 1 的 patch 模式）。若集成测试只验证"注入格式"而不依赖 select 内部，可能无需改——**按 grep 结果决定**。

- [ ] **Step 2: 跑集成测试（单文件，隔离）**

Run: `python -m pytest tests/test_react_loop_memory_integration.py -v`
Expected: PASS（若失败，按 Task 4 patch 模式修正 mock）

- [ ] **Step 3: 跑记忆相关全量**

Run: `python -m pytest tests/test_memory_service.py tests/test_memory_vector.py tests/test_memory_repo.py tests/test_react_loop_memory_integration.py -v`
Expected: PASS

- [ ] **Step 4: 全量回归**

Run: `python -m pytest -q`
Expected: PASS（全部通过；预计耗时 ~11-12 分钟）

- [ ] **Step 5: 提交**

```bash
git add backend/tests/test_react_loop_memory_integration.py
git commit -m "test(memory): 集成测试 select 走向量路径 + Phase2 全量回归通过"
```

---

## 自查（Self-Review）

**Spec 覆盖：**
- spec §1.2 目标 #2 select 向量 → Task 4 ✓
- spec §1.2 目标 #3 向量去重 → Task 5 ✓
- spec §1.2 目标 #1 extract 门控 → Task 5 ✓
- spec §2.1 双写 + 降级 → Task 3（write）/ Task 6（consolidate）✓
- spec §4.1 MemoryVectorIndex 接口 → Task 2 ✓
- spec §4.3 Settings → Task 1 ✓
- spec §5 _ensure_vectors 回填 → Task 3 ✓
- spec §6 错误处理/降级 → Task 3/4/5/6 各 try/except ✓
- spec §8 测试矩阵 → Task 2-7 ✓
- spec §12 退出标准（select 零 LLM / 去重 / 门控 / 降级 / 回填 / 回归）→ 各 Task ✓

**类型一致性：** `MemoryVectorIndex.query` 恒返回 `[{"id","distance"}]`（Task 2 定义，Task 4/5 消费一致）；`_embed_text(name, description)` / `_ensure_vectors(scope)` 跨 Task 命名一致；`EmbeddingService.embed(list) -> list[list[float]]` 与现有签名一致 ✓

**占位扫描：** 无 TBD/TODO；每个 code step 附完整代码。Task 4 Step 3 提示"检查后再删 import"是防误删的操作指引，非占位 ✓
