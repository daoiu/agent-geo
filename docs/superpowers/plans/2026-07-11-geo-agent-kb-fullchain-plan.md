# Agent KB 全链路 v0.6 P1.4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 v0.4 agent 工具集从 3 个扩到 5 个 — 新增 `list_knowledge_bases` + `create_generation_task`，放宽 `search_knowledge` 的 `kb_id` 为可选；让 LLM 在会话里能"列 KB → 召回 → 触发生成任务"完成"北北云吞 5 篇"场景，**不在 agent 会话循环**。

**Architecture:** 一切走 Python 函数 / Pydantic，不引新 HTTP endpoint，不动 DB schema，不上 LangGraph。`list` 工具包装 `KnowledgeRepository.list_kbs`（已存在，但加 `doc_count` 通过 LEFT JOIN + GROUP BY 一查到底，避免 N+1）。`search` 工具走双分支：传 kb_id → 现有 v0.5 hybrid；不传 → P1.3 跨库 hybrid。`create_generation_task` 包装 `TaskRepository.create_task`（v0.2 已有），不进 `HumanConfirmationRequired` 流程 — agent 创建后即返 task_id。

**Tech Stack:** Python 3.11 / FastAPI / pydantic v2 / SQLAlchemy (async) / pytest / respx / OpenAI function-calling

**Spec:** `docs/superpowers/specs/2026-07-11-geo-agent-kb-fullchain-design.md` (commit `3132b29`)

## Global Constraints

- 后端 repo 不允许对 KB 数量做 N+1 — `doc_count` 走单 SQL `LEFT JOIN knowledge_documents GROUP BY knowledge_bases.id`
- agent 工具命名 shortverb_noun 风格（已在用）
- tool schema 描述 + 在 `AGENT_SYSTEM_PROMPT` 同步写入，避免 LLM 看到 schema 不会用
- 既有测试零回归 — `test_three_tools_registered` 等需要按升级后数量更新
- 不动 `frontend/` 任何文件（spec §7）
- 中文 git commit

---

## File Map

```
backend/
├── app/
│   ├── models/
│   │   └── knowledge.py                       # 改 — KnowledgeBase.doc_count
│   ├── repositories/
│   │   └── knowledge_repo.py                  # 改 — list_kbs JOIN GROUP BY
│   ├── domain/agent/
│   │   ├── tools.py                           # 改 — 加 list / create schema + enum + TOOLS 注册
│   │   ├── tool_executor.py                   # 改 — search_knowledge 分支; 加 _execute_create_generation_task
│   │   ├── prompts.py                         # 改 — 加"知识库使用策略"段
│   │   └── react_loop.py                      # 改 — MAX_REACT_ITERATIONS 5 → 7
│   └── services/
│       └── content_writer.py                  # 读 — create_generation_task executor 引用
└── tests/
    ├── test_knowledge_repo.py                 # 改 — 加 list_kbs(含 doc_count) 2 case
    ├── test_agent_tools.py                    # 改 — 加新工具 validator; 旧 3-tools 改 5-tools
    ├── test_agent_tool_executor_search.py     # 新 — search 分支 4 case
    └── test_agent_tool_executor_create_task.py# 新 — create_generation_task 2 case

docs/
├── CHANGELOG.md                               # 改 — v0.6 P1.4 节
├── HANDOFF_V0.6.md                            # 改 — P1.4 子节
└── (其他文档同步在 Task 6 一次性处理)
```

---

## Task 1: `KnowledgeBase` schema 加 `doc_count` + repo `list_kbs` 走 JOIN

**Files:**
- Modify: `backend/app/models/knowledge.py:14-19`
- Modify: `backend/app/repositories/knowledge_repo.py:43-47`
- Modify: `backend/tests/test_knowledge_repo.py` (add 2 cases)

**Interfaces:**
- Consumes: existing `KnowledgeBaseORM` + `KnowledgeDocumentORM`
- Produces: `KnowledgeBase` Pydantic with `doc_count: int = 0`; `repo.list_kbs() -> list[KnowledgeBaseORM]` returning ORM rows with eager-loaded `.doc_count` attr via SQL aggregation

### Step 1: 写失败测试

Append to `backend/tests/test_knowledge_repo.py`:

```python
@pytest.mark.asyncio
async def test_list_kbs_returns_doc_count(db_session) -> None:
    """list_kbs 返回结果带 doc_count 字段（LEFT JOIN GROUP BY 单 SQL）。"""
    repo = KnowledgeRepository(db_session)
    kb0 = await repo.create_kb(name="空 KB")          # 0 docs
    kb1 = await repo.create_kb(name="单文档 KB")       # 1 doc
    doc = await repo.add_document(
        kb_id=kb1.id, filename="a.md", file_path="/tmp/a.md",
        file_type="md", file_size=10,
    )
    kbs = await repo.list_kbs()
    by_id = {kb.id: kb for kb in kbs}
    assert by_id[kb0.id].doc_count == 0
    assert by_id[kb1.id].doc_count == 1


@pytest.mark.asyncio
async def test_list_kbs_doc_count_n_plus_one_safe(db_session) -> None:
    """3 个 KB × 各 2 个 doc — list 一次 SQL（无 N+1）。"""
    from sqlalchemy import event
    from app.core.db import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        repo = KnowledgeRepository(session)
        for n in range(3):
            kb = await repo.create_kb(name=f"KB{n}")
            for d in range(2):
                await repo.add_document(
                    kb_id=kb.id, filename=f"d{d}.md", file_path=f"/tmp/d{d}.md",
                    file_type="md", file_size=10,
                )

    # 用 fresh session + 事件探针
    async with factory() as session:
        statements: list[str] = []
        @event.listens_for(session.sync_session, "before_cursor_execute")
        def _capture(conn, cursor, statement, params, ctx, executemany):  # noqa: ANN001
            statements.append(statement)

        repo = KnowledgeRepository(session)
        kbs = await repo.list_kbs()
        for kb in kbs:
            assert kb.doc_count == 2

        # 应当只有 1 个 SELECT（含 JOIN + GROUP BY）；不允许对每个 KB 多发一个 SELECT
        select_count = sum(1 for s in statements if "SELECT" in s.upper())
        assert select_count == 1, f"expected 1 SELECT, got {select_count}: {statements}"
```

### Step 2: 跑看 FAIL

Run: `cd backend && python -m pytest -q tests/test_knowledge_repo.py -x`
Expected: FAIL with `AttributeError: 'KnowledgeBaseORM' object has no attribute 'doc_count'`

### Step 3: 改 schema

Modify `backend/app/models/knowledge.py`:

```python
class KnowledgeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    created_at: datetime
    doc_count: int = 0  # v0.6 P1.4 — 由 LEFT JOIN docs GROUP BY 一次性给出
```

### Step 4: 改 repo

Modify `backend/app/repositories/knowledge_repo.py` — replace `list_kbs` body:

```python
    async def list_kbs(self) -> list[KnowledgeBaseORM]:
        """v0.6 P1.4: 通过 LEFT JOIN 一次性拿 doc_count。

        单 SQL：SELECT kb.*, COUNT(doc.id) FROM knowledge_bases
        LEFT JOIN knowledge_documents ON kb.id = doc.kb_id
        GROUP BY kb.id ORDER BY kb.created_at DESC
        """
        from sqlalchemy import func, select

        stmt = (
            select(
                KnowledgeBaseORM,
                func.count(KnowledgeDocumentORM.id).label("doc_count"),
            )
            .outerjoin(
                KnowledgeDocumentORM,
                KnowledgeDocumentORM.kb_id == KnowledgeBaseORM.id,
            )
            .group_by(KnowledgeBaseORM.id)
            .order_by(KnowledgeBaseORM.created_at.desc())
        )
        rows = await self.session.execute(stmt)
        result: list[KnowledgeBaseORM] = []
        for kb, doc_count in rows.all():
            kb.doc_count = doc_count  # 动态属性，pydantic from_attributes 拿到
            result.append(kb)
        return result
```

### Step 5: 跑看 PASS

Run: `cd backend && python -m pytest -q tests/test_knowledge_repo.py -x`
Expected: PASS（2 new case）。全量：`pytest -q tests/test_knowledge_repo.py`

### Step 6: Commit

```bash
git add backend/app/models/knowledge.py \
        backend/app/repositories/knowledge_repo.py \
        backend/tests/test_knowledge_repo.py
git commit -m "feat(backend/v0.6/P1.4): KnowledgeBase.doc_count 单 SQL JOIN

list_kbs 把 doc_count 由 N+1 改成单 LEFT JOIN docs + GROUP BY 一次性拿；
KnowledgeBase schema 加 doc_count: int = 0 (default)。
2 新 test case: 0/1 doc KB 返回 + 多 KB × 多 doc 验证 select_count == 1。"
```

---

## Task 2: `list_knowledge_bases` 工具 + TOOLS 注册

**Files:**
- Modify: `backend/app/domain/agent/tools.py:18-23` (enum + schema + TOOLS + VALIDATORS)
- Modify: `backend/tests/test_agent_tools.py` (add 2 cases + update 2 existing)

**Interfaces:**
- Consumes: 现有 `KnowledgeRepository.list_kbs()` 已在 Task 1 返回 `doc_count`
- Produces:
  - `ToolName.LIST_KNOWLEDGE_BASES = "list_knowledge_bases"`
  - `_LIST_SCHEMA` OpenAI function-calling schema (no parameters)
  - `TOOLS` 列表新增一项 → 总 5 件
  - `_VALIDATORS["list_knowledge_bases"] = BaseModel` （空模型）

### Step 1: 写失败测试

Append to `backend/tests/test_agent_tools.py` (end of file):

```python
class TestListKnowledgeBasesTool:
    def test_five_tools_registered(self) -> None:
        """After P1.4, exactly 5 tools are exposed."""
        assert len(TOOLS) == 5

    def test_tool_names_match_enum(self) -> None:
        """TOOL_NAMES contains 5 entries incl list_knowledge_bases + create_generation_task."""
        from app.domain.agent.tools import TOOL_NAMES as TN
        assert TN == {
            "diagnose_brand", "search_knowledge", "generate_article",
            "list_knowledge_bases", "create_generation_task",
        }

    def test_list_schema_has_no_params(self) -> None:
        """list_knowledge_bases 函数没有参数，但保留空 properties 给 LLM 看."""
        from app.domain.agent.tools import get_tool_schema
        schema = get_tool_schema("list_knowledge_bases")
        assert schema["name"] == "list_knowledge_bases"
        assert "description" in schema
        assert schema["parameters"]["type"] == "object"
        assert schema["parameters"]["properties"] == {}
        assert schema["parameters"].get("required", []) == []

    def test_list_validator_accepts_empty(self) -> None:
        """validator 接受空 dict（list 工具没有必填参数）."""
        from app.domain.agent.tools import validate_tool_args
        validated = validate_tool_args("list_knowledge_bases", {})
        assert validated is not None
```

### Step 2: 跑看 FAIL

Run: `cd backend && python -m pytest -q tests/test_agent_tools.py::TestListKnowledgeBasesTool -x`
Expected: FAIL — `test_five_tools_registered` says `len(TOOLS) == 3` (mismatch)

### Step 3: 改 `tools.py`

**Important:** 同时更新 `tests/test_agent_tools.py` 里的 `test_three_tools_registered` 和 `test_tool_names_match_enum`：
- `test_three_tools_registered` → `assert len(TOOLS) == 5`，并 rename → `test_five_tools_registered`
- `test_tool_names_match_enum` → set 增至 5 个

（这一步合在 Step 4 一起做。）

Modify `backend/app/domain/agent/tools.py`:

A. 加 enum (lines 18-23):

```python
class ToolName(str, Enum):
    """五个工具的稳定名称。"""

    DIAGNOSE_BRAND = "diagnose_brand"
    SEARCH_KNOWLEDGE = "search_knowledge"
    GENERATE_ARTICLE = "generate_article"
    LIST_KNOWLEDGE_BASES = "list_knowledge_bases"
    CREATE_GENERATION_TASK = "create_generation_task"
```

B. 在三个 Pydantic 模型之后追加空模型：

```python
class ListKnowledgeBasesArgs(BaseModel):
    """list_knowledge_bases 工具的参数（无参，工具签名占位）."""

    # Pydantic model 必须继承 BaseModel 但允许 0 字段（OpenAI schema 的空 properties）。
    model_config = {"extra": "forbid"}
```

C. 在 `_DIAGNOSE_SCHEMA` 段后 / 之前追加 `_LIST_SCHEMA`：

```python
_LIST_SCHEMA: dict = {
    "name": "list_knowledge_bases",
    "description": (
        "列出所有已创建的知识库，返回 [{kb_id, kb_name, doc_count, created_at}]。"
        "在用户模糊提问（如「我有哪些品牌资料库」「有哪些品牌」）或 LLM 不知道该查哪个 KB 时调用。"
        "调用 search_knowledge 之前也应该先调这个工具确认 kb_id 存在。"
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
```

D. 在 `TOOLS` 列表追加（两处：`TOOLS` + `TOOL_NAMES`）：

```python
TOOLS: list[dict] = [
    {"type": "function", "function": _DIAGNOSE_SCHEMA},
    {"type": "function", "function": _SEARCH_SCHEMA},
    {"type": "function", "function": _GENERATE_SCHEMA},
    {"type": "function", "function": _LIST_SCHEMA},
    {"type": "function", "function": _CREATE_TASK_SCHEMA},  # Task 4 加
]
```

（Task 2 只加 list 这一项；Task 4 完成后再加 create task。）

E. `TOOL_NAMES` 同步：

```python
TOOL_NAMES: set[str] = {
    ToolName.DIAGNOSE_BRAND.value,
    ToolName.SEARCH_KNOWLEDGE.value,
    ToolName.GENERATE_ARTICLE.value,
    ToolName.LIST_KNOWLEDGE_BASES.value,
    ToolName.CREATE_GENERATION_TASK.value,
}
```

F. `_VALIDATORS` 加 list 工具：

```python
_VALIDATORS: dict[str, type[BaseModel]] = {
    "diagnose_brand": DiagnoseBrandArgs,
    "search_knowledge": SearchKnowledgeArgs,
    "generate_article": GenerateArticleArgs,
    "list_knowledge_bases": ListKnowledgeBasesArgs,
    "create_generation_task": CreateGenerationTaskArgs,  # Task 4 加
}
```

### Step 4: 同步更新既有测试

In `backend/tests/test_agent_tools.py`:

- `test_three_tools_registered`：
  - rename → `test_five_tools_registered`
  - body: `assert len(TOOLS) == 5`
- `test_tool_names_match_enum`：
  - body:
    ```python
    assert TOOL_NAMES == {
        "diagnose_brand", "search_knowledge", "generate_article",
        "list_knowledge_bases", "create_generation_task",
    }
    ```

> 这些修改在没有 Task 4 完成时会 fail；为避免 Task 2 卡住，**暂不更新 `TOOLS` 列表里的 create task 行**，把 Task 2 的步骤改为只注册 `list_knowledge_bases`，等 Task 4 再加 create task。修订：

- 本 Task 2 的 Step 3.f 中：**先不加 create task schema 行和 enum**，仅加 list；`TOOL_NAMES` 加 list 那一条
- 等 Task 4 完成后再做一次原子 commit 更新 `test_three_tools_registered` → 5
- 见 Task 4 末 Step

### Step 5: 跑看 PASS

Run: `cd backend && python -m pytest -q tests/test_agent_tools.py -x`
Expected: PASS — 4 个 list 工具 case 全过；既有 17 case 仍全过

### Step 6: Commit

```bash
git add backend/app/domain/agent/tools.py \
        backend/tests/test_agent_tools.py
git commit -m "feat(backend/v0.6/P1.4): list_knowledge_bases agent 工具

新增 ToolName.LIST_KNOWLEDGE_BASES + 空 args 模型 + function-calling schema；
list_knowledge_bases 描述告诉 LLM '模糊问品牌/不知道查哪个 KB 时先调这个'。
零代码副作用：仅注册 schema，executor 实际 dispatch 在 Task 4 加（与 search 改写合并）。"
```

---

## Task 3: `search_knowledge` kb_id 可选 + executor 双分支

**Files:**
- Modify: `backend/app/domain/agent/tools.py:39-44` (SearchKnowledgeArgs)
- Modify: `backend/app/domain/agent/tools.py:93-119` (_SEARCH_SCHEMA 描述 + required)
- Modify: `backend/app/domain/agent/tool_executor.py:138-173` (_execute_search_knowledge 分支)
- Modify: `backend/tests/test_agent_tools.py` (update TestValidateSearchArgs 既有 5 个)
- Create: `backend/tests/test_agent_tool_executor_search.py` (4 new cases)

**Interfaces:**
- Consumes: `repo.search_chunks_hybrid(kb_id, query, top_k)` (现有); `HybridSearch().search_across_kbs(query, top_k)` (P1.3 已存在, 返 dict 形状)
- Produces:
  - `SearchKnowledgeArgs` with `kb_id: str | None = None`
  - `_SEARCH_SCHEMA` kb_id 改成可选 (从 required list 移除)
  - executor 分支:
    - `kb_id` 传：走 `repo.search_chunks_hybrid` (现有路径)
    - `kb_id` 不传：走 `HybridSearch().search_across_kbs`，normalize dict → 同 schema (id, content, doc_id, chunk_index, kb_id, kb_name, doc_filename, sources)

### Step 1: 写失败测试（executor 分支）

Create `backend/tests/test_agent_tool_executor_search.py`:

```python
"""Tests for ToolExecutor._execute_search_knowledge branching (v0.6 P1.4)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.domain.agent.tool_executor import ToolExecutor
from app.domain.agent.tools import SearchKnowledgeArgs


@pytest.mark.asyncio
async def test_search_with_kb_id_uses_single_kb_hybrid():
    """kb_id 传入时走 repo.search_chunks_hybrid（单库路径，保持原行为）."""
    executor = ToolExecutor(session_id="s1")
    args = SearchKnowledgeArgs(kb_id="kb-1", query="云吞", limit=5)

    fake_result = [
        {"id": "c1", "content": "陈皮云吞皮", "metadata":
            {"doc_id": "d1", "chunk_index": 0, "kb_id": "kb-1"},
         "_rrf_score": 0.05, "_sources": ["keyword"]},
    ]

    with patch("app.repositories.knowledge_repo.KnowledgeRepository.search_chunks_hybrid",
               return_value=fake_result) as MockRepoSearch:
        result = await executor._execute_search_knowledge(args)

    MockRepoSearch.assert_called_once_with(kb_id="kb-1", query="云吞", top_k=5)
    assert result["kb_id"] == "kb-1"
    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["id"] == "c1"


@pytest.mark.asyncio
async def test_search_without_kb_id_uses_cross_kb_hybrid():
    """kb_id 不传时走 HybridSearch.search_across_kbs（跨库，P1.3 路径）."""
    from app.domain.knowledge.retriever import ...  # noqa
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
        MockHS.return_value.search_across_kbs = \
            __import__("asyncio").coroutine(lambda self, query, top_k: fake_across)

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
    with patch("app.repositories.knowledge_repo.KnowledgeRepository.search_chunks_hybrid",
               return_value=fake):
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
    with patch("app.repositories.knowledge_repo.KnowledgeRepository.search_chunks_hybrid",
               return_value=fake):
        result = await executor._execute_search_knowledge(args)
    assert len(result["chunks"][0]["content"]) == 500
```

### Step 2: 跑看 FAIL

Run: `cd backend && python -m pytest -q tests/test_agent_tool_executor_search.py -x`
Expected: FAIL — `SearchKnowledgeArgs.__init__` 不接受 `kb_id=None`，或 executor 仍走单一路径

### Step 3: 改 `tools.py` — kb_id 改 optional

Modify `backend/app/domain/agent/tools.py`:

A. `SearchKnowledgeArgs` (line 39-44):

```python
class SearchKnowledgeArgs(BaseModel):
    """search_knowledge 工具的参数 (v0.6 P1.4: kb_id 可选)."""

    kb_id: str | None = Field(None, min_length=1)  # 不传=跨库 (P1.3)
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(5, ge=1, le=10)
```

B. `_SEARCH_SCHEMA` 描述 + required (line 93-119):

```python
_SEARCH_SCHEMA: dict = {
    "name": "search_knowledge",
    "description": (
        "在指定知识库或全局搜索与查询相关的资料片段。"
        "kb_id 不传或 null 时，跨所有知识库做 hybrid 召回（向量 + 关键词 + RRF）。"
        "kb_id 传时则限定该 KB 召回。返回最相关的几个资料片段 "
        "（含 KB 名称、来源文档、向量/关键词命中来源标签）。"
        "agent 只能查询已存在的知识库，不能创建/修改/删除。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kb_id": {
                "type": "string",
                "description": (
                    "知识库 ID（UUID）；不传则跨所有知识库全局检索。"
                ),
            },
            "query": {
                "type": "string",
                "description": "搜索关键词或问题",
            },
            "limit": {
                "type": "integer",
                "description": "返回几个片段，默认 5，最大 10",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}
```

### Step 4: 改 `tool_executor.py` — 双分支

Modify `_execute_search_knowledge` in `backend/app/domain/agent/tool_executor.py` (line 138-173). Replace entire method:

```python
    async def _execute_search_knowledge(self, args: SearchKnowledgeArgs) -> dict:
        """搜索知识库（v0.6 P1.4 双分支）.

        kb_id 不传 → HybridSearch.search_across_kbs（跨库, P1.3）
        kb_id 传   → KnowledgeRepository.search_chunks_hybrid（单库, v0.5）

        chunk content 截断到 500 字符，避免 LLM 上下文爆炸。
        """
        truncated: list[dict] = []

        if args.kb_id is None:
            from app.services.hybrid_search import HybridSearch

            hits = await HybridSearch().search_across_kbs(
                query=args.query, top_k=args.limit,
            )
            for h in hits:
                meta = h.get("metadata", {}) or {}
                content = (h.get("content") or "")[:500]
                truncated.append({
                    "id": h["id"],
                    "doc_id": meta.get("doc_id"),
                    "chunk_index": meta.get("chunk_index"),
                    "content": content,
                    "content_length": len(content),
                    "kb_id": meta.get("kb_id"),
                    "kb_name": meta.get("kb_name"),
                    "doc_filename": meta.get("doc_filename"),
                    "rrf_score": h.get("_rrf_score"),
                    "sources": h.get("_sources", []),
                })
            return {
                "kb_id": None,
                "kb_name": None,
                "query": args.query,
                "chunks": truncated,
                "total_found": len(truncated),
                "scope": "all_knowledge_bases",
            }

        # kb_id 传：单库路径（v0.5 hybrid, 行为不变）
        from app.core.db import get_session_factory
        from app.repositories.knowledge_repo import KnowledgeRepository

        async with get_session_factory()() as session:
            repo = KnowledgeRepository(session)
            chunks = await repo.search_chunks_hybrid(
                kb_id=args.kb_id,
                query=args.query,
                top_k=args.limit,
            )
            # 回查 KB name 用于 LLM 上下文
            kb = await repo.get_kb(args.kb_id)
            kb_name = kb.name if kb else None

        for c in chunks:
            content = c["content"][:500]
            meta = c.get("metadata", {})
            truncated.append({
                "id": c["id"],
                "doc_id": meta.get("doc_id"),
                "chunk_index": meta.get("chunk_index"),
                "content": content,
                "content_length": len(content),
                "kb_id": args.kb_id,
                "kb_name": kb_name,
                "doc_filename": None,
                "rrf_score": c.get("_rrf_score"),
                "sources": c.get("_sources", []),
            })

        return {
            "kb_id": args.kb_id,
            "kb_name": kb_name,
            "query": args.query,
            "chunks": truncated,
            "total_found": len(truncated),
            "scope": f"kb:{args.kb_id}",
        }
```

### Step 5: 同步更新既有 SearchKnowledge 测试

In `backend/tests/test_agent_tools.py`, update `TestValidateSearchArgs`:

```python
class TestValidateSearchArgs:
    def test_valid_args(self) -> None:
        """kb_id + query accepted, kb_id 可选."""
        args = validate_tool_args(
            "search_knowledge",
            {"kb_id": "kb-123", "query": "产品功能"},
        )
        assert isinstance(args, SearchKnowledgeArgs)
        assert args.kb_id == "kb-123"
        assert args.limit == 5

    def test_kb_id_optional(self) -> None:
        """kb_id 不传时默认为 None（跨库路径）."""
        args = validate_tool_args(
            "search_knowledge",
            {"query": "云吞"},
        )
        assert args.kb_id is None
        assert args.query == "云吞"

    def test_custom_limit(self) -> None:
        args = validate_tool_args(
            "search_knowledge",
            {"kb_id": "kb-123", "query": "X", "limit": 10},
        )
        assert args.limit == 10

    def test_limit_too_high(self) -> None:
        with pytest.raises(ValidationError):
            validate_tool_args(
                "search_knowledge",
                {"kb_id": "kb-123", "query": "X", "limit": 100},
            )

    def test_limit_zero(self) -> None:
        with pytest.raises(ValidationError):
            validate_tool_args(
                "search_knowledge",
                {"kb_id": "kb-123", "query": "X", "limit": 0},
            )

    def test_missing_query(self) -> None:
        with pytest.raises(ValidationError):
            validate_tool_args("search_knowledge", {"kb_id": "kb-123"})
```

### Step 6: 跑看 PASS

Run: `cd backend && python -m pytest -q tests/test_agent_tools.py tests/test_agent_tool_executor_search.py`
Expected: PASS — 既有 17 + 新 4（list）+ 新 4（search executor）+ 1（search validator）全过

### Step 7: Commit

```bash
git add backend/app/domain/agent/tools.py \
        backend/app/domain/agent/tool_executor.py \
        backend/tests/test_agent_tools.py \
        backend/tests/test_agent_tool_executor_search.py
git commit -m "feat(backend/v0.6/P1.4): search_knowledge kb_id 可选 + 双分支

SearchKnowledgeArgs.kb_id 改 Field(None)，required list 去掉 kb_id；
executor 分支：args.kb_id None → HybridSearch.search_across_kbs(P1.3 跨库)，
否则走现有 repo.search_chunks_hybrid（v0.5 单库）。
返回 shape 统一：chunks[] 含 kb_name + doc_filename，result 带 scope 字段。
kb_id 缺的 chunk 也补全 kb_name（用 repo.get_kb 单查）。
4 新 executor 测试 + 1 validator 更新。"
```

---

## Task 4: `create_generation_task` 工具 + 包装 v0.2 TaskRepository

**Files:**
- Modify: `backend/app/domain/agent/tools.py` (加 CreateGenerationTaskArgs + _CREATE_TASK_SCHEMA + TOOLS / VALIDATORS)
- Modify: `backend/app/domain/agent/tool_executor.py` (加 _execute_create_generation_task + dispatch)
- Create: `backend/tests/test_agent_tool_executor_create_task.py` (2 cases)
- Modify: `backend/tests/test_agent_tools.py` (更新 test_three_tools_registered → test_five_tools_registered + test_tool_names_match_enum → 5 项)

**Interfaces:**
- Consumes: `TaskRepository.create_task(name, kb_id, brand, topic, keywords, article_count, style, target_length)` (v0.2 已有); 调用方需要 factory `get_session_factory()`
- Produces:
  - `CreateGenerationTaskArgs`: `kb_id, brand, topic, article_count, keywords, style, target_length` — 字段与 `app.models.task.TaskCreate` 大体对齐
  - `_CREATE_TASK_SCHEMA` OpenAI function-calling
  - executor 方法：调 `TaskRepository.create_task` 落库 + `schedule_task(task.id)` 触发 worker；**不抛 HumanConfirmationRequired**
  - 返回 shape: `{task_id, status, article_count, next_step: "/tasks/<task_id> 详情页审核"}`

### Step 1: 写失败测试

Create `backend/tests/test_agent_tool_executor_create_task.py`:

```python
"""Tests for create_generation_task executor (v0.6 P1.4)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.domain.agent.tool_executor import ToolExecutor
from app.domain.agent.tools import CreateGenerationTaskArgs


@pytest.mark.asyncio
async def test_create_generation_task_happy_path(db_session):
    """正常路径 → 调 TaskRepository.create_task + schedule_task → 返 task_id."""
    from app.repositories.task_repo import TaskRepository
    from app.repositories.knowledge_repo import KnowledgeRepository

    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    await db_session.commit()

    executor = ToolExecutor(session_id="s1")
    args = CreateGenerationTaskArgs(
        kb_id=kb.id,
        brand="北北云吞",
        topic="玉林老字号云吞店介绍",
        article_count=5,
        keywords=["云吞", "皮薄", "马蹄"],
        style="professional",
    )

    with patch.object(TaskRepository, "create_task",
                      return_value=None) as MockCreate, \
         patch("app.domain.agent.tool_executor.schedule_task") as MockSched:
        # 模拟真实 repo 返回带 id 的 task
        MockCreate.return_value = type("T", (), {
            "id": "task-fake-123",
            "status": "pending",
            "article_count": 5,
        })()
        result = await executor._execute_create_generation_task(args)

    MockCreate.assert_called_once()
    call_kwargs = MockCreate.call_args.kwargs
    assert call_kwargs["kb_id"] == kb.id
    assert call_kwargs["brand"] == "北北云吞"
    assert call_kwargs["article_count"] == 5

    MockSched.assert_called_once_with("task-fake-123")

    assert result["task_id"] == "task-fake-123"
    assert result["status"] == "pending"
    assert result["article_count"] == 5
    assert "/tasks/task-fake-123" in result["next_step"]


@pytest.mark.asyncio
async def test_create_generation_task_unknown_kb_returns_404(db_session):
    """kb_id 不存在时返 404-like error，不抛 HumanConfirmation."""
    from app.repositories.knowledge_repo import KnowledgeRepository

    executor = ToolExecutor(session_id="s1")
    args = CreateGenerationTaskArgs(
        kb_id="bogus-kb-id",
        brand="X",
        topic="足够长的 topic 内容",
        article_count=1,
        keywords=["x"],
    )

    with pytest.raises(Exception) as excinfo:  # HTTPException 422 或 python ValueError
        await executor._execute_create_generation_task(args)
    # 不应该是 HumanConfirmationRequired
    from app.domain.exceptions import HumanConfirmationRequired
    assert not isinstance(excinfo.value, HumanConfirmationRequired)
```

### Step 2: 跑看 FAIL

Run: `cd backend && python -m pytest -q tests/test_agent_tool_executor_create_task.py -x`
Expected: FAIL — `CreateGenerationTaskArgs` 不存在 / `schedule_task` 未在 tool_executor 引入

### Step 3: 改 `tools.py`

Modify `backend/app/domain/agent/tools.py`:

A. 在 `GenerateArticleArgs` 后追加：

```python
class CreateGenerationTaskArgs(BaseModel):
    """create_generation_task 工具的参数（v0.6 P1.4 — 包装 v0.2 TaskCreate）.

    与 app.models.task.TaskCreate 对齐，但去掉 name（前端的 name 会从
    brand+topic 自动拼接生成，避免 LLM 多写一个不必要字段）。
    """

    kb_id: str = Field(..., min_length=1)
    brand: str = Field(..., min_length=1, max_length=100)
    topic: str = Field(..., min_length=5, max_length=500)
    keywords: list[str] = Field(..., min_length=1, max_length=20)
    article_count: int = Field(5, ge=1, le=20)
    style: Literal["neutral", "professional", "casual"] = "neutral"
    target_length: int = Field(1500, ge=300, le=10000)
```

B. 在 `_GENERATE_SCHEMA` 之后追加：

```python
_CREATE_TASK_SCHEMA: dict = {
    "name": "create_generation_task",
    "description": (
        "创建一个内容生成任务（v0.2 TaskCreator），用 kb_id 指定的 KB 内容生成 N 篇文章草稿。"
        "返回 task_id。生成 + 审核 + 发布由 v0.2 任务系统负责，"
        "agent 这里只需要触发任务即可，**不需要在会话内循环**。"
        "生成的 N 篇文章在 /tasks/{task_id} 详情页审核 → 发布。"
        "适用：用户说「给我生成 X 品牌 N 篇文章」「批量生成 X 文章」，N>1 时务必用这个工具。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kb_id": {
                "type": "string",
                "description": "知识库 ID（UUID）",
            },
            "brand": {
                "type": "string",
                "description": "目标品牌名",
            },
            "topic": {
                "type": "string",
                "description": "文章主题（至少 5 个字）",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "关键词（至少 1 个）",
            },
            "article_count": {
                "type": "integer",
                "description": "生成文章数量，默认 5，最大 20",
                "default": 5,
            },
            "style": {
                "type": "string",
                "enum": ["neutral", "professional", "casual"],
                "description": "写作风格，默认 neutral",
                "default": "neutral",
            },
            "target_length": {
                "type": "integer",
                "description": "每篇目标字数，默认 1500",
                "default": 1500,
            },
        },
        "required": ["kb_id", "brand", "topic", "keywords", "article_count"],
    },
}
```

C. 修改 `TOOLS` 列表（line 171-175）：

```python
TOOLS: list[dict] = [
    {"type": "function", "function": _DIAGNOSE_SCHEMA},
    {"type": "function", "function": _SEARCH_SCHEMA},
    {"type": "function", "function": _GENERATE_SCHEMA},
    {"type": "function", "function": _LIST_SCHEMA},
    {"type": "function", "function": _CREATE_TASK_SCHEMA},
]


TOOL_NAMES: set[str] = {
    ToolName.DIAGNOSE_BRAND.value,
    ToolName.SEARCH_KNOWLEDGE.value,
    ToolName.GENERATE_ARTICLE.value,
    ToolName.LIST_KNOWLEDGE_BASES.value,
    ToolName.CREATE_GENERATION_TASK.value,
}
```

D. 修改 `_VALIDATORS`：

```python
_VALIDATORS: dict[str, type[BaseModel]] = {
    "diagnose_brand": DiagnoseBrandArgs,
    "search_knowledge": SearchKnowledgeArgs,
    "generate_article": GenerateArticleArgs,
    "list_knowledge_bases": ListKnowledgeBasesArgs,
    "create_generation_task": CreateGenerationTaskArgs,
}
```

### Step 4: 改 `tool_executor.py` — dispatch + 新方法

Modify `backend/app/domain/agent/tool_executor.py`:

A. Imports 顶（line 18-23）：

```python
from app.domain.agent.tools import (
    CreateGenerationTaskArgs,
    DiagnoseBrandArgs,
    GenerateArticleArgs,
    SearchKnowledgeArgs,
    validate_tool_args,
)
```

B. `execute()` 分发（line 49-56）追加：

```python
        if tool_name == "create_generation_task":
            return await self._execute_create_generation_task(validated)

        raise ValueError(f"Unknown tool: {tool_name}")
```

C. 文件末尾追加新方法：

```python
    async def _execute_create_generation_task(
        self, args: CreateGenerationTaskArgs
    ) -> dict:
        """创建内容生成任务（v0.2 TaskCreator 包装）.

        与 generate_article 不同：这里**不抛 HumanConfirmationRequired**，
        立即落 v0.2 tasks 表 + 触发 worker；agent turn 即结束。
        """
        from app.core.db import get_session_factory
        from app.repositories.knowledge_repo import KnowledgeRepository
        from app.repositories.task_repo import TaskRepository
        from app.tasks.task_worker import schedule_task

        async with get_session_factory()() as session:
            kb_repo = KnowledgeRepository(session)
            kb = await kb_repo.get_kb(args.kb_id)
            if kb is None:
                raise ValueError(f"knowledge base not found: {args.kb_id}")

            task_repo = TaskRepository(session)
            # 自动生成 task name = brand + topic 截断
            task_name = f"{args.brand} - {args.topic}"[:200]
            task = await task_repo.create_task(
                name=task_name,
                kb_id=args.kb_id,
                brand=args.brand,
                topic=args.topic,
                keywords=args.keywords,
                article_count=args.article_count,
                style=args.style,
                target_length=args.target_length,
            )
            await session.commit()

        # 触发后台 worker（v0.2 task_worker 已有）
        schedule_task(task.id)

        return {
            "task_id": task.id,
            "kb_id": args.kb_id,
            "article_count": args.article_count,
            "status": task.status,
            "next_step": f"已创建任务。请到 /tasks/{task.id} 详情页审核 {args.article_count} 篇草稿。",
        }
```

### Step 5: 同步更新既有测试

In `backend/tests/test_agent_tools.py`:

- Rename `test_three_tools_registered` → `test_five_tools_registered`; `assert len(TOOLS) == 5`
- `test_tool_names_match_enum` 改为 5 项 set（如 Task 2 Step 4）
- 加 create_generation_task validator 测试：

```python
class TestValidateCreateTaskArgs:
    def test_valid_args(self) -> None:
        args = validate_tool_args(
            "create_generation_task",
            {
                "kb_id": "kb-123",
                "brand": "北北云吞",
                "topic": "玉林老字号云吞店介绍",
                "keywords": ["云吞", "皮薄"],
                "article_count": 5,
            },
        )
        from app.domain.agent.tools import CreateGenerationTaskArgs
        assert isinstance(args, CreateGenerationTaskArgs)
        assert args.style == "neutral"  # default
        assert args.target_length == 1500  # default

    def test_article_count_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            validate_tool_args(
                "create_generation_task",
                {
                    "kb_id": "kb", "brand": "X",
                    "topic": "足够长的 topic 内容",
                    "keywords": ["x"],
                    "article_count": 0,
                },
            )

    def test_article_count_too_high_raises(self) -> None:
        with pytest.raises(ValidationError):
            validate_tool_args(
                "create_generation_task",
                {
                    "kb_id": "kb", "brand": "X",
                    "topic": "足够长的 topic 内容",
                    "keywords": ["x"],
                    "article_count": 100,
                },
            )
```

### Step 6: 跑看 PASS

Run: `cd backend && python -m pytest -q tests/test_agent_tools.py tests/test_agent_tool_executor_create_task.py tests/test_agent_tool_executor_search.py`
Expected: PASS — 既有 + List (4) + Search validator (1) + Search executor (4) + Create validator (3) + Create executor (2)

### Step 7: Commit

```bash
git add backend/app/domain/agent/tools.py \
        backend/app/domain/agent/tool_executor.py \
        backend/tests/test_agent_tools.py \
        backend/tests/test_agent_tool_executor_create_task.py
git commit -m "feat(backend/v0.6/P1.4): create_generation_task agent 工具

包装 v0.2 TaskRepository.create_task + task_worker.schedule_task；
agent 调一次即落 v0.2 tasks 表 + 触发 worker，不再抛 HumanConfirmation。
返回 {task_id, status, article_count, next_step: /tasks/<id>}，
LLM 把 next_step 直接回给用户。

TOOLS 列表总 5 件 (DIAGNOSE/SEARCH/GENERATE/LIST/CREATE) 全部注册；
2 executor 测试 + 3 validator 测试。"
```

---

## Task 5: prompts 策略文本 + MAX_REACT 5→7

**Files:**
- Modify: `backend/app/domain/agent/prompts.py` (整段替换 AGENT_SYSTEM_PROMPT)
- Modify: `backend/app/domain/agent/react_loop.py:25` (5 → 7)
- Create: `backend/tests/test_agent_prompt_strategy.py` (1 test)

**Interfaces:**
- Consumes: 现有 `AGENT_SYSTEM_PROMPT`, `MAX_REACT_ITERATIONS = 5`
- Produces:
  - `AGENT_SYSTEM_PROMPT` 字符串追加"知识库使用策略"段
  - `MAX_REACT_ITERATIONS = 7`

### Step 1: 写失败测试

Create `backend/tests/test_agent_prompt_strategy.py`:

```python
"""Tests for AGENT_SYSTEM_PROMPT strategy section (v0.6 P1.4)."""
from app.domain.agent.prompts import AGENT_SYSTEM_PROMPT
from app.domain.agent.react_loop import MAX_REACT_ITERATIONS


def test_prompt_mentions_list_knowledge_bases() -> None:
    """Prompt 必须告诉 LLM 优先调 list_knowledge_bases 探索可用 KB."""
    assert "list_knowledge_bases" in AGENT_SYSTEM_PROMPT


def test_prompt_mentions_create_generation_task() -> None:
    """Prompt 必须告诉 LLM 多篇生成走 create_generation_task 而非循环."""
    assert "create_generation_task" in AGENT_SYSTEM_PROMPT


def test_prompt_mandates_source_attribution() -> None:
    """Prompt 要求 chunk 引用时附 kb_name + doc_filename（溯源）."""
    assert "kb_name" in AGENT_SYSTEM_PROMPT
    assert "doc_filename" in AGENT_SYSTEM_PROMPT


def test_max_react_iterations_is_seven() -> None:
    """MAX_REACT_ITERATIONS 从 5 提到 7，给 list → search → create_task 三步留余量."""
    assert MAX_REACT_ITERATIONS == 7
```

### Step 2: 跑看 FAIL

Run: `cd backend && python -m pytest -q tests/test_agent_prompt_strategy.py -x`
Expected: FAIL — prompt 不含 list_knowledge_bases；MAX_REACT_ITERATIONS 还是 5

### Step 3: 改 prompts.py

Replace whole file `backend/app/domain/agent/prompts.py`:

```python
"""v0.4 Agent 系统 prompt (v0.6 P1.4 加入'知识库使用策略'段)."""

AGENT_SYSTEM_PROMPT = """你是 GEO Agent，一个帮助用户做"生成式引擎优化"（GEO）的 AI 助手。

你可以使用以下工具：
- diagnose_brand：诊断一个品牌的 GEO 健康度（综合分数 + 5 维子分数 + 建议）
- search_knowledge：在指定知识库或全局搜索相关资料（kb_id 可选；不传则跨所有 KB 召回）
- generate_article：基于知识库生成**单篇**草稿（**会询问用户确认**）
- list_knowledge_bases：列出所有知识库（含 kb_name / doc_count），用于发现有哪些品牌资料库
- create_generation_task：批量创建 N 篇生成任务（**不**询问确认，直接落 v0.2 tasks 表 + 触发 worker）

工作原则：
1. 优先使用工具获取真实数据，不要凭空回答
2. 每次只调用一个工具，等结果回来再决定下一步
3. 总结时引用具体的数字和工具结果
4. 不知道的不要编造，明确告诉用户
5. 回复简洁，1-3 句话为主
6. 中文回复

【知识库与生成任务的策略 (v0.6 P1.4)】

7. 当用户提到品牌 / 资料库 / KB 相关问题时：
   a. 第一步调 list_knowledge_bases() 看有哪些可用 KB（含品牌名）
   b. 用户明确提到某品牌 → 从列表里 name-match 出 kb_id，然后 search_knowledge(kb_id=?, query=...)
   c. 用户模糊/忘了品牌名 → search_knowledge(kb_id 不传, query=用户原话或关键词)
8. 召回的 chunks 必须显式带来源：返回字段里有 kb_name / doc_filename / sources。
   引用时附"依据《doc_filename》（KB: kb_name）"格式，让用户能溯源。
9. 生成文章的数量规则：
   - 单篇（N=1）→ 用 generate_article（需要用户确认）
   - 多篇（N>=2）→ **必须**用 create_generation_task：
     * 不在 agent 会话里循环
     * 落 v0.2 tasks 表，由后台 worker 处理
     * 在回答里把 next_step 的 /tasks/<task_id> 链接告诉用户
10. search_knowledge 不传 kb_id 时跨库（向量 + 关键词 + RRF）；传了则单库。
"""
```

### Step 4: 改 react_loop.py

Modify `backend/app/domain/agent/react_loop.py`:

```python
MAX_REACT_ITERATIONS = 7  # v0.6 P1.4: 5 → 7，留余量给 list → search → create_task
```

### Step 5: 跑看 PASS

Run: `cd backend && python -m pytest -q tests/test_agent_prompt_strategy.py`
Expected: PASS — 4 个 case 全过

### Step 6: Commit

```bash
git add backend/app/domain/agent/prompts.py \
        backend/app/domain/agent/react_loop.py \
        backend/tests/test_agent_prompt_strategy.py
git commit -m "feat(backend/v0.6/P1.4): AGENT_SYSTEM_PROMPT 策略 + MAX_REACT 7

prompt 追加 v0.6 P1.4 知识库使用策略段 (10 行内):
 - 先 list 看品牌 → kb_id 决定走哪条 search
 - chunks 引用附 kb_name + doc_filename (溯源)
 - 多篇走 create_generation_task，**不在会话循环**
MAX_REACT_ITERATIONS 5 → 7 (留余量给三步最小链)。
4 单测覆盖 prompt 关键句 + 新 MAX。"
```

---

## Task 6: 文档同步 + 全量回归

**Files:**
- Modify: `docs/CHANGELOG.md` (在 v0.6 段 P1.3 后追加 P1.4 节)
- Modify: `docs/HANDOFF_V0.6.md` (在 P1.3 子节后追加 P1.4 节)
- Modify: `frontend/docs/DESIGN.md` (Section 7 IA 表里 agent 行追加工具集说明)

**Interfaces:** 同步 spec §12 退出标准

### Step 1: CHANGELOG 改

In `docs/CHANGELOG.md`, after the P1.3 section, append:

```markdown
### Phase 1 / P1.4 已完成 (本批)

- **Agent 工具集从 3 扩到 5**：业务要求"智能助手不只 KB 问答还能调别的工具"，把 agent 工具集扩到 5 件
  - 新 `list_knowledge_bases`：(no args) → `[{kb_id, kb_name, doc_count, created_at}]`。`GET /api/knowledge` 响应增加 `doc_count` 走 **单 SQL JOIN GROUP BY**（避免 N+1）
  - `search_knowledge` 改 `kb_id` 可选：不传跨库走 `HybridSearch.search_across_kbs` (P1.3)；传了走 `repo.search_chunks_hybrid` (v0.5)。返回统一 shape 加 `kb_name`、`scope` 字段
  - 新 `create_generation_task`：包装 v0.2 `TaskRepository.create_task` + `task_worker.schedule_task`，**不**抛 HumanConfirmation。agent turn 即结束；用户去 `/tasks/<task_id>` 审核 N 篇草稿
- **`AGENT_SYSTEM_PROMPT` 加入"知识库使用策略"段**：强制 LLM 先 list → name-match → search；多篇必须走 create_task；chunk 引用附 `kb_name` + `doc_filename` 可溯源
- **`MAX_REACT_ITERATIONS` 5 → 7**：给 `list → search → create_task` 三步最小链留余量
- **测试**：
  - 既有测试零回归：`test_three_tools_registered` → `test_five_tools_registered`（5 件套）
  - 新增 `tests/test_agent_tool_executor_search.py` 4 cases（双分支 + shape 统一）
  - 新增 `tests/test_agent_tool_executor_create_task.py` 2 cases（happy + bogus_kb）
  - 新增 `tests/test_agent_prompt_strategy.py` 4 cases（prompt 含 list/create 关键词 + MAX_REACT=7）
  - 既有 `tests/test_knowledge_repo.py` 新增 2 cases（含 `doc_count` + N+1 防护）
  - 既有 `tests/test_agent_tools.py` 增 4 validator cases（list + create_task）
  - 全量：**后端 436 passed（+16）、前端不变**
```

### Step 2: HANDOFF_V0.6.md 改

Append below P1.3 section:

```markdown
## Phase 1 / P1.4 — Agent 工具集扩到 5（2026-07-11）

> 目标：用户提「给我生成北北云吞 5 篇宣传文」，agent 能自己 list → 匹配 → 召回 → 创建任务，不在会话循环。

**新增工具 2**：list_knowledge_bases、(改动) search_knowledge kb_id 可选、(新增) create_generation_task
**Prompt 策略**：先 list 后 search；多篇走 create_task 不在循环
**MAX_REACT_ITERATIONS**：5 → 7
**文档**：spec §16 → `2026-07-11-geo-agent-kb-fullchain-design.md`
**数据流**：agent_chat.py → list → name-match → search → create_task → 用户去 /tasks/审核

### 手动验证 P1.4

```bash
# 起 backend + frontend
cd backend && uvicorn app.main:app --port 8000 &
cd frontend && npm run dev

# 浏览器: http://localhost:5173/agent
# 输入「我有几个知识库？」（应触发 list 工具，回答：「当前有 1 个知识库：北北云吞」）
# 输入「给我生成北北云吞的 5 篇不同的宣传文」
#   → agent 应 1) list → 2) 匹配 kb_id='fbac45ba-...' → 3) search → 4) create_task
#   → 回答里出现 task_id 和「去 /tasks/<id> 审核 5 篇草稿」
# 去 http://localhost:5173/tasks/<id> 看到 5 篇文章正在生成
```

### 风险

- list_knowledge_bases 在数百 KB 量级的 doc_count GROUP BY 性能：当前 SQL 是单次聚合，SQLite 仍可；千级以上考虑切换到 PostgreSQL
- prompt 策略段过长（10 行）会侵蚀 system prompt tokens budget；监控 LLM 调用 system prompt 长度
```

### Step 3: frontend/docs/DESIGN.md 改

In Section 7 IA 表里 `/agent` 一行后追加 agent 工具集：

```markdown
- 新增 `/agent` 一行后追加 5 工具简述：

| 工具 | 入参 |
|---|---|
| `list_knowledge_bases` | () |
| `search_knowledge` | `kb_id?`, `query`, `limit=5` |
| `create_generation_task` | `kb_id, brand, topic, article_count, keywords, style, target_length` |

(诊断/单篇生成工具不变)
```

### Step 4: 全量回归

Run:
```bash
cd backend && python -m pytest -q
```
Expected: PASS — 后端 ~436 passed（基线 420 + 16 新 case）

```bash
cd frontend && npx vitest run
```
Expected: PASS — 前端不变（spec §7 无前端改动），仍 87 passed

```bash
cd frontend && npx tsc --noEmit
```
Expected: 0 errors

### Step 5: Commit

```bash
git add docs/CHANGELOG.md \
        docs/HANDOFF_V0.6.md \
        frontend/docs/DESIGN.md
git commit -m "docs(v0.6/P1.4): CHANGELOG + HANDOFF + DESIGN 同步 P1.4 完成

P1.4 agent 工具集扩到 5 件套的官方记录 + 手动验证步骤；前端 DESIGN
文档 §7 IA 表追加 agent 工具集说明。"
```

---

## Self-Review Notes

**1. Spec coverage**:
- §1 Context → 不直接对应 task，是 spec 序言
- §2 决策矩阵 → Task 2 (list) + Task 3 (search 可选) + Task 4 (create task) + Task 5 (prompt)
- §3 工具集 → Tasks 2/3/4
- §4 数据流 → 不直接对应 task，是 spec 用例说明
- §5.1 list → Task 1 (doc_count) + Task 2 (tool)
- §5.2 search 可选 → Task 3
- §5.3 create task → Task 4
- §6 prompt 策略 + MAX_REACT → Task 5
- §7 文件地图 → 已经全部覆盖
- §8 错误处理 → Tasks 2/3/4 step 5
- §9 测试 → 每个 task 都有测试
- §10 风险未做 → 在 Task 6 docs 里声明
- §11 决策日志 → 不进 implementation plan
- §12 退出标准 → Task 6

**2. Placeholder scan**:
- 没有 TBD / TODO / "implement later"
- 没有 "similar to Task N"
- 没有 "write tests for the above"
- 没有"add validation" / "handle edge cases" 的空描述

**3. Type consistency**:
- `CreateGenerationTaskArgs.article_count` 在所有出现处都用 `int = Field(5, ge=1, le=20)`
- `SearchKnowledgeArgs.kb_id` 在所有出现处都是 `str | None`
- `executor._execute_search_knowledge` 返回 dict shape 在 4 个 test 里断言一致 (kb_name + doc_filename keys 都在)
- `KnowledgeBase.doc_count: int = 0` 在 schema + repo + 2 tests 一致

**4. Order check**:
- Task 1 先做 (schema + repo 是 Task 2 list 工具的数据来源)
- Task 2 单独可测 (tool schema + validator)
- Task 3 修改 search 既有工具 + executor 双分支
- Task 4 加 create task 工具
- Task 5 prompt + MAX_REACT
- Task 6 docs + 全量回归

每个 task 的步骤顺序：失败测试 → 跑看 fail → 最小实现 → 跑看 pass → commit，符合 TDD。Task 6 不写测试，只做 docs + 全量回归验证。

---

## Final Acceptance Checklist

- [ ] All 16+ new test cases pass (mapping to spec §9)
- [ ] 既有 420+ 后端测试零回归
- [ ] 87 前端测试零回归（spec §7 声明不动前端）
- [ ] TypeScript strict 0 errors
- [ ] pytest -q + npm test 跨平台（Win/Linux）一致
- [ ] 6 commits 形成可读 git log:
  1. `feat(backend/v0.6/P1.4): KnowledgeBase.doc_count 单 SQL JOIN`
  2. `feat(backend/v0.6/P1.4): list_knowledge_bases agent 工具`
  3. `feat(backend/v0.6/P1.4): search_knowledge kb_id 可选 + 双分支`
  4. `feat(backend/v0.6/P1.4): create_generation_task agent 工具`
  5. `feat(backend/v0.6/P1.4): AGENT_SYSTEM_PROMPT 策略 + MAX_REACT 7`
  6. `docs(v0.6/P1.4): CHANGELOG + HANDOFF + DESIGN 同步 P1.4 完成`

Plan complete and saved to `docs/superpowers/plans/2026-07-11-geo-agent-kb-fullchain-plan.md`. 6 tasks total, ~3-4 hours of focused TDD implementation.

请选执行方式：
1. **Subagent-Driven（推荐）**：每个 task 一个 fresh subagent + 两阶段 review — 较快
2. **Inline Execution**：本会话串行跑 — 你全程看得见每步

或要修改某些 task 顺序 / 拆分。[e~[
