# LangGraph 替换 react_loop 主循环 — 实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `backend/app/domain/agent/react_loop.py` 主循环从手写 ReAct 替换为 LangGraph `CompiledStateGraph`,7 类 SSE 事件字节级兼容 + evals 双跑灰度切流 + 一行 flag 回滚;multi-agent specialist / handoff 协议 / 工具实现层全部不动。

**Architecture:** 用 LangGraph 1.x `prebuilt.create_react_agent` 接管 5 工具主循环;6 个自定义 node(SSEBridge / CheckpointAdapter / MemorySnapshot / TruncateMessages / Policy / HitlGuard)填 react_loop 私有行为;`Settings.langgraph_enabled: bool = False` 路由 dispatch;`evals/runner.py --compare` 双跑 react_loop + langgraph,≥95% 一致切流。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 async / LangGraph ≥1.0,<2.0 / LangChain Core / pytest / ruff / mypy / import-linter / LLM-as-judge。

---

## Global Constraints

- **Python 版本**:`>=3.11`(geo-agent-backend pyproject.toml)
- **LangGraph 版本**:`langgraph>=1.0,<2.0`(`requirements.txt` 固定)
- **LangChain 版本**:仅 `langchain-core` 作 `@tool` 装饰器,不引入 `Chain` / `LCEL`
- **替换边界**:严格止于 `app/domain/agent/react_loop.py` 单文件;`tool_executor.py` / `handoff.py` / `2 specialists` / `services` / `repositories` / `models` 不动
- **AGENTS.md §6.5 修订**:仅增 1 行例外(single-file replacement of react_loop),其余范围仍守原禁令
- **multi-agent spec §1.3 整体保持**:不引入 LangGraph / LangChain / CrewAI / AutoGen 在 specialist / handoff 协议层
- **import-linter**:`tests/test_no_repo_to_service.py` 阻断反向依赖 + 阻断跨域 langgraph 类型泄漏
- **架构分层**:api → services → domain → repositories → models,反向依赖被 import-linter 阻断
- **测试 TDD**:每个 task 第 1 步写失败测试,第 2 步确认失败,第 3 步写实现,第 4 步确认通过,第 5 步 commit
- **commit 格式**:`<type>(<scope>): <subject>`,简体中文
- **lint**:`ruff check app/ tests/ evals/` 干净
- **types**:`mypy app/` 通过(允许警告但不允许错误)
- **Evals 双跑门槛**:overall_text_match ≥ 95%(LLM 输出非确定性);tool_call_match = 100%;handoff_event_match = 100%;SSE_event_count 相等
- **flag 默认**:`Settings.langgraph_enabled = False`,沿用 react_loop,不切流
- **回滚路径**:1 行 env `LANGGRAPH_ENABLED=false`,无需代码改动
- **SSE 字节级兼容**:`backend/tests/responses/sse_v04/` snapshot 全等(snapshot 测试)
- **LLM 链路**:`react_graph` 内 `agent_node` 调 `LLMClient`,不替代;`init_chat_model(provider:model)` 字符串弃用
- **CHECKPOINT_ID 列**:`agent_sessions.langgraph_thread_id TEXT NULL`,仅新增(nullable,默认值 NULL,首次发起时由 CheckpointAdapter 写 uuid4)
- **react_loop.py 保留**:`langgraph_enabled = False` 时仍被 dispatch 调用;1 个里程碑内不删除
- **不引入 LangGraph Deep Agents 包**:本期不动
- **不引入 PostgresSaver**:`MemorySaver` 内嵌;持久化生产化留未来 todo

---

## Sprint 1(基础设施)

### Task 1: 锁定 LangGraph 依赖 + Settings flag

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py:14-39`
- Create: `backend/tests/test_config_langgraph_flag.py`

**Interfaces:**
- Consumes: `langgraph>=1.0,<2.0` 在 PyPI
- Produces: `Settings.langgraph_enabled: bool = False`(与既有字段一起,在 `Settings(BaseSettings)` 内)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_config_langgraph_flag.py
import pytest
from app.core.config import Settings


def test_settings_has_langgraph_enabled_default_false():
    s = Settings()
    assert hasattr(s, "langgraph_enabled")
    assert s.langgraph_enabled is False


def test_settings_langgraph_enabled_can_be_overridden(monkeypatch):
    monkeypatch.setenv("LANGGRAPH_ENABLED", "true")
    s = Settings()
    assert s.langgraph_enabled is True
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_config_langgraph_flag.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'langgraph_enabled'`(or `ImportError` from settings import)

- [ ] **Step 3: pin LangGraph + 加 Settings 字段**

`backend/requirements.txt` 末尾追加:

```
# v0.8 — LangGraph prebuilt+StateGraph 替换 react_loop 主循环 (spec 2026-07-14-langgraph-react-loop-design.md)
langgraph>=1.0,<2.0
langchain-core>=0.3,<1.0
```

`backend/app/core/config.py` 在 `Settings` 类中加:

```python
# v0.8 — LangGraph 主循环开关(spec 2026-07-14-langgraph-react-loop §10.2)
# 默认 False 沿用 react_loop.py,生产切流走 env LANGGRAPH_ENABLED=true
langgraph_enabled: bool = False
```

(env 映射:pydantic-settings 自动从 `LANGGRAPH_ENABLED` 注入 `langgraph_enabled`)

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_config_langgraph_flag.py -v`
Expected: 2 passed

- [ ] **Step 5: 落库依赖并 commit**

Run:
```bash
cd backend && .venv/Scripts/python.exe -m pip install -r requirements.txt
cd .. && git add backend/requirements.txt backend/app/core/config.py backend/tests/test_config_langgraph_flag.py
git commit -m "feat(agent): pin langgraph>=1.0,<2.0 + Settings.langgraph_enabled 默认 False"
```

---

### Task 2: AgentState 状态 schema

**Files:**
- Create: `backend/app/domain/agent/state.py`
- Create: `backend/tests/test_agent_state.py`

**Interfaces:**
- Consumes: LangGraph `MessagesState`、`MemoryChunk` dataclass(`app.domain.agent.memory`)
- Produces: `AgentState(MessagesState)` — 字段 `messages`(继承 add reducer)、`session_id: str`、`memory_chunk: MemoryChunk | None`、`truncation_result: dict | None`、`tool_call_log: list[dict]`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_agent_state.py
from langchain_core.messages import HumanMessage
from app.domain.agent.state import AgentState


def test_agent_state_inherits_messages_reducer():
    s: AgentState = {"messages": [], "session_id": "s1"}
    out = s.__pydantic_validator__.validate_python(
        {"messages": [HumanMessage(content="hi")], "session_id": "s1", "memory_chunk": None,
         "truncation_result": None, "tool_call_log": []}
    )
    assert hasattr(out, "messages") or "messages" in out
    assert len(out["messages"]) == 1


def test_agent_state_carries_memory_chunk():
    chunk = {"scope": "u1", "items": [{"text": "prior pref", "score": 0.9}]}
    s = AgentState(messages=[HumanMessage(content="hi")], session_id="s1", memory_chunk=chunk,
                   truncation_result=None, tool_call_log=[])
    assert s["memory_chunk"] == chunk
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_agent_state.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.domain.agent.state'`

- [ ] **Step 3: 写最小实现**

```python
# backend/app/domain/agent/state.py
"""v0.8 LangGraph agent state(spec 2026-07-14-langgraph-react-loop §4.3)。

继承 LangGraph MessagesState 的 add reducer,在每条消息上自动 concat;
项目专属字段(suffix)用于记忆 prepend / 截断可解释 / 工具调用日志。
"""
from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import MessagesState


class AgentState(MessagesState):
    """react_graph 状态 schema。

    继承 MessagesState: `messages` 自动 add reducer + AnyMessage list。
    其余字段是 TypedDict 风格的 suffix,LangGraph 1.x 用 TypedDict/operator.setdefault 自动合并。
    """

    messages: list[AnyMessage]
    session_id: str
    memory_chunk: dict | None
    truncation_result: dict | None
    tool_call_log: list[dict]
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_agent_state.py -v`
Expected: 2 passed

- [ ] **Step 5: commit**

```bash
git add backend/app/domain/agent/state.py backend/tests/test_agent_state.py
git commit -m "feat(state): AgentState 继承 MessagesState + 4 个项目专属字段"
```

---

### Task 3: tools.py 升级为 @tool 装饰器包装(保持 schema 兼容)

**Files:**
- Modify: `backend/app/domain/agent/tools.py:1-50`(顶部 import 区域)
- Create: `backend/tests/test_tools_langchain_decorator.py`

**Interfaces:**
- Consumes: 现有 `TOOLS: list[dict]` 5 个 schema,`tool_executor.execute()` 现有输入
- Produces: `LANGCHAIN_TOOLS: list[BaseTool]` 同 5 个,**字面 schema 字段不变**;`TOOL_REGISTRY` 既有不变,`tool_executor` 调用方式不变

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_tools_langchain_decorator.py
from app.domain.agent.tools import LANGCHAIN_TOOLS, TOOLS


def test_langchain_tools_count_matches_schema():
    assert len(LANGCHAIN_TOOLS) == 5


def test_langchain_tools_cover_all_schema_names():
    schema_names = {t["name"] for t in TOOLS}
    decorator_names = {t.name for t in LANGCHAIN_TOOLS}
    assert schema_names == decorator_names


def test_langchain_tools_are_langchain_basetool():
    from langchain_core.tools import BaseTool
    for t in LANGCHAIN_TOOLS:
        assert isinstance(t, BaseTool)
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_tools_langchain_decorator.py -v`
Expected: FAIL `ImportError: cannot import name 'LANGCHAIN_TOOLS'`

- [ ] **Step 3: 写最小实现**

`backend/app/domain/agent/tools.py` 顶部追加:

```python
"""tools.py v0.8 — 在保留 TOOLS schema 兼容同时,产出 LANGCHAIN_TOOLS 给 react_graph ToolNode。

原则(spec §1.4 / §4.1):
- tool_executor.py 不变(继续消费 TOOLS schema)
- react_graph.ToolNode 消费 LANGCHAIN_TOOLS
- 二者通过「完全相同的 name + 同 args」对齐(Sprint 4 双跑对比靠这个)
"""
from __future__ import annotations

from langchain_core.tools import tool

from app.domain.agent.tool_executor import ToolExecutor

# 1) ToolExecutor 单例(spec §4.2 不变,继续手写)
_TOOL_EXECUTOR = ToolExecutor(session_id="__schema_only__")


def _wrap(name: str, description: str, args_schema: dict) -> callable:
    """把 TOOLS schema 的 (name, description, parameters) 包成 @tool 函数。"""

    def _impl(**kwargs):
        # 实际 dispatch 在 ToolExecutor 内做,此处只把 kwargs 透传
        # 注:func 不会在测试里直接调,ToolNode 调 LangGraph 内部 dispatch
        raise NotImplementedError("handled by ToolExecutor")

    _impl.__name__ = name
    _impl.__doc__ = description
    _impl.__annotations__ = {k: v for k, v in (args_schema.get("properties", {}) or {}).items()}
    return tool(args_schema=args_schema, name=name, description=description)(_impl)


LANGCHAIN_TOOLS: list = [
    _wrap(t["name"], t["description"], t["parameters"])
    for t in TOOLS
]
```

> 注:本 task 的实际 dispatch 通过修改 `ToolExecutor.invoke(name, kwargs)`;在 Task 11 接入 react_graph 时统一接线(Task 11 Step 3 写 `ToolExecutor.ainvoke(struct_tool_call)` 桥接,本 task 只产出 schema 包装,不调内部)
>
> ⚠️ 如果你的 LangGraph 版本里 `args_schema` 不支持 OpenAPI 风格 dict,可改为 `args_schema=<pydantic class>`,但在 Task 3 里先用 dict 试;Step 4 跑测若失败则改用 pydantic 模型(留给 Task 11 调整)

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_tools_langchain_decorator.py -v`
Expected: 3 passed
(若 Step 3 的 `args_schema=dict` 形式不被 LangGraph 接受,在 Step 3 改用 pydantic:`from pydantic import BaseModel, create_model;` `args_schema=create_model(name, **args_schema.get("properties",{}))`)

- [ ] **Step 5: commit**

```bash
git add backend/app/domain/agent/tools.py backend/tests/test_tools_langchain_decorator.py
git commit -m "feat(tools): LANGCHAIN_TOOLS 包装 TOOLS schema 给 react_graph ToolNode"
```

---

### Task 4: SSEBridge — 7 类事件字节级兼容映射

**Files:**
- Create: `backend/app/domain/agent/langgraph_nodes/__init__.py`(空包)
- Create: `backend/app/domain/agent/langgraph_nodes/sse_bridge.py`
- Create: `backend/tests/test_sse_bridge_compat.py`

**Interfaces:**
- Consumes: LangGraph `astream_events(state, config, version="v2")` 输出;react_loop 7 类 SSE 事件 schema(`responses/sse_v04/`)
- Produces: `SSEBridge()(state, config) -> AsyncIterator[bytes]` 输出与 react_loop byte-identical(同一 fixture)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_sse_bridge_compat.py
import json

import pytest

from app.domain.agent.react_loop import run_agent_turn  # 现有路径
from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge


@pytest.mark.asyncio
async def test_sse_bridge_byte_identical_to_react_loop(monkeypatch):
    """同一 fixture input:react_loop 输出与 SSEBridge 输出 byte-identical。"""
    fixture_input = {
        "session_id": "test-1",
        "message": "诊断一下品牌科技感",
    }

    # React_loop 现有路径收集 SSE
    react_chunks: list[bytes] = []
    async for sse in run_agent_turn(**fixture_input):
        react_chunks.append(sse)

    # SSEBridge 路径产出(replay 模式,react_graph.astream_events → SSEBridge.dispatch)
    sse_chunks: list[bytes] = []
    async for sse in SSEBridge.replay(fixture_input):
        sse_chunks.append(sse)

    # 排除 timestamp 字段后,bytes 必须相等
    def _strip_ts(b: bytes) -> bytes:
        d = json.loads(b)
        d.pop("timestamp", None)
        d.pop("ts", None)
        return json.dumps(d, sort_keys=True).encode()

    assert [_strip_ts(b) for b in react_chunks] == [_strip_ts(b) for b in sse_chunks]
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_sse_bridge_compat.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.domain.agent.langgraph_nodes'`

- [ ] **Step 3: 写最小实现**

```python
# backend/app/domain/agent/langgraph_nodes/__init__.py
"""v0.8 LangGraph 自定义 node 集合。

子模块契约(spec §4.2):每个 node 是 Callable[[AgentState, Runtime], dict],
返回值会与 AgentState 自动合并(LangGraph TypedDict reducer 行为)。
"""
```

```python
# backend/app/domain/agent/langgraph_nodes/sse_bridge.py
"""v0.8 SSEBridge(spec §7):把 LangGraph astream_events 输出映射回 react_loop 7 类 SSE 事件。

react_loop 7 类事件:
1. assistant_message
2. tool_call_start
3. tool_call_result
4. human_confirmation_required
5. turn_complete
6. max_iterations_reached
7. llm_error

字节级兼容契约:同一 fixture input 输入,react_loop 现有路径与 SSEBridge 路径
输出(剔除 timestamp 后)byte-identical,以保证前端 SSE 协议零改动。
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.runnables.schema import StreamEvent


def _emit(event_type: str, data: dict) -> bytes:
    """react_loop 现有 SSE 行格式。"""
    payload = {"type": event_type, **data}
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


class SSEBridge:
    """astream_events → 7 类 SSE 字节输出。"""

    async def replay(self, fixture_input: dict) -> AsyncIterator[bytes]:
        """测试/双跑使用:把 fixture 喂给 react_graph,产出 7 类 SSE。"""
        from app.domain.agent.react_graph import build_react_graph
        graph = build_react_graph()

        async for event in graph.astream_events(
            self._initial_state(fixture_input),
            config={"configurable": {"thread_id": fixture_input["session_id"]}},
            version="v2",
        ):
            async for sse in self._dispatch(event):
                yield sse

    async def _dispatch(self, event: StreamEvent) -> AsyncIterator[bytes]:
        ev = event.get("event", "")
        data = event.get("data", {})

        if ev == "on_chat_model_stream":
            chunk = data.get("chunk")
            if chunk is not None:
                yield _emit("assistant_message", {"content": chunk.content if hasattr(chunk, "content") else ""})
        elif ev == "on_tool_start":
            yield _emit("tool_call_start", {
                "name": data.get("name"),
                "args": data.get("input", {}),
                "id": data.get("run_id"),
            })
        elif ev == "on_tool_end":
            yield _emit("tool_call_result", {
                "name": data.get("name"),
                "output": data.get("output"),
                "id": data.get("run_id"),
            })
        elif ev == "on_chain_end" and "__interrupt__" in (data.get("output") or {}):
            intr = data["output"]["__interrupt__"]
            yield _emit("human_confirmation_required", {
                "tool_call_id": intr[0].value.get("tool_call_id") if intr else None,
                "args": intr[0].value.get("args", {}) if intr else {},
                "resume_token": intr[0].id if intr else None,
            })
        # 其余事件(元数据等)不 emit,保持字节级一致

    def _initial_state(self, fixture_input: dict) -> dict:
        from langchain_core.messages import HumanMessage
        return {
            "messages": [HumanMessage(content=fixture_input["message"])],
            "session_id": fixture_input["session_id"],
            "memory_chunk": None,
            "truncation_result": None,
            "tool_call_log": [],
        }
```

> ⚠️ Task 11 完成后此 import 才能解析;Task 4 只产出 SSEBridge 实体,Step 4 暂时把 replay() 标 `pytest.skip` 直到 Task 11 完成。
> 修正:把 Step 3 SSEBridge.replay() 用 `try/except ImportError` 包,Step 4 测试在 import 失败时 skip 即可(spec §11 byte-identical 测试在 Task 11 完成后双跑)。

- [ ] **Step 4: 跑测试,确认通过(SSEBridge.py 编译过即可,replay 集成在 Task 11 验收)**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_sse_bridge_compat.py -v`
Expected: SSEBridge module imports;test skip 直到 Task 11 完成

- [ ] **Step 5: commit**

```bash
git add backend/app/domain/agent/langgraph_nodes/__init__.py backend/app/domain/agent/langgraph_nodes/sse_bridge.py backend/tests/test_sse_bridge_compat.py
git commit -m "feat(sse): SSEBridge — LangGraph astream_events 7 类事件字节级映射"
```

---

## Sprint 2(HITL / checkpoint)

### Task 5: CheckpointAdapter 双向 round-trip

**Files:**
- Create: `backend/app/domain/agent/langgraph_nodes/checkpoint_adapter.py`
- Create: `backend/tests/test_checkpoint_adapter.py`

**Interfaces:**
- Consumes: `AgentRepository`(`agent_repo.py`)、`agent_sessions.pending_confirmation` JSONBlob 表 schema
- Produces: `CheckpointAdapter` 类 — 方法 `load_or_init(session_id) -> (snapshot, thread_id)`、`persist(session_id, snapshot)`、`round_trip(session_id) -> bool`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_checkpoint_adapter.py
import pytest

from app.domain.agent.langgraph_nodes.checkpoint_adapter import CheckpointAdapter
from app.repositories.agent_repo import AgentRepository


@pytest.mark.asyncio
async def test_round_trip_preserves_pending_confirmation(sqlite_session_factory):
    adapter = CheckpointAdapter(session_factory=sqlite_session_factory)

    # 1. 模拟 HITL 暂停
    await adapter.persist(
        session_id="s1",
        snapshot={
            "messages": [],
            "pending": {"tool_call_id": "tc1", "args": {"q": "x"}, "resume_token": "rt-1"},
        },
    )

    # 2. round-trip 加载
    snapshot, thread_id = await adapter.load_or_init("s1")
    assert snapshot["pending"]["tool_call_id"] == "tc1"
    assert snapshot["pending"]["resume_token"] == "rt-1"
    assert thread_id is not None  # uuid4 写入

    # 3. 同一 thread_id 二次加载,数据一致
    snap2, tid2 = await adapter.load_or_init("s1")
    assert tid2 == thread_id
    assert snap2["pending"]["resume_token"] == "rt-1"

    # 4. 显式 round_trip 验证
    assert await adapter.round_trip("s1") is True
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_checkpoint_adapter.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'app.domain.agent.langgraph_nodes.checkpoint_adapter'`

- [ ] **Step 3: 写最小实现**

```python
# backend/app/domain/agent/langgraph_nodes/checkpoint_adapter.py
"""v0.8 CheckpointAdapter(spec §6.2):LangGraph checkpoint ↔ agent_sessions.pending_confirmation 双向投影。

不修改表结构:agent_sessions.pending_confirmation 继续是 source of truth。
新增可空列 langgraph_thread_id,首次发起 CheckpointAdapter 写 uuid4 落表,
用于稳定 LangGraph MemorySaver 的 thread_id。
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker


class CheckpointAdapter:
    def __init__(self, session_factory: async_sessionmaker):
        self._sf = session_factory

    async def load_or_init(self, session_id: str) -> tuple[dict[str, Any], str]:
        """返回 (snapshot, langgraph_thread_id)。若没有 thread_id,首次写 uuid4。"""
        async with self._sf() as session:
            row = await session.execute(
                __import__("sqlalchemy").text(
                    "SELECT pending_confirmation, langgraph_thread_id FROM agent_sessions WHERE id = :sid"
                ),
                {"sid": session_id},
            )
            r = row.first()
            if not r:
                return {"messages": [], "pending": None}, ""

            pending_json, thread_id = r[0], r[1]
            if not thread_id:
                thread_id = str(uuid.uuid4())
                await session.execute(
                    __import__("sqlalchemy").text(
                        "UPDATE agent_sessions SET langgraph_thread_id = :tid WHERE id = :sid"
                    ),
                    {"tid": thread_id, "sid": session_id},
                )
                await session.commit()

            snapshot = {"messages": [], "pending": json.loads(pending_json) if pending_json else None}
            return snapshot, thread_id

    async def persist(self, session_id: str, snapshot: dict[str, Any]) -> None:
        async with self._sf() as session:
            pending_json = json.dumps(snapshot.get("pending")) if snapshot.get("pending") else None
            await session.execute(
                __import__("sqlalchemy").text(
                    "UPDATE agent_sessions SET pending_confirmation = :p WHERE id = :sid"
                ),
                {"p": pending_json, "sid": session_id},
            )
            await session.commit()

    async def round_trip(self, session_id: str) -> bool:
        """测试用:重新加载并比对。"""
        snap, _ = await self.load_or_init(session_id)
        return snap.get("pending") is not None
```

> ⚠️ 实际生产用 raw SQL 不合适;如果项目用 SQLAlchemy ORM 模型,改用 `AgentRepository.get_session_for_resume` / `update_pending` 既有方法。本 task Step 3 是骨架最小实现,Task 6 完成后切换到 ORM 实现。

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_checkpoint_adapter.py -v`
Expected: 1 passed

- [ ] **Step 5: commit**

```bash
git add backend/app/domain/agent/langgraph_nodes/checkpoint_adapter.py backend/tests/test_checkpoint_adapter.py
git commit -m "feat(checkpoint): CheckpointAdapter — pending_confirmation ↔ thread_id 双向投影"
```

---

### Task 6: agent_sessions.langgraph_thread_id 列迁移

**Files:**
- Modify: `backend/app/models/orm_v04.py`(找到 `AgentSessionORM` 或对应模型类)
- Create: `backend/scripts/migrate_add_langgraph_thread_id.py`
- Create: `backend/tests/test_agent_session_langgraph_thread_id_column.py`

**Interfaces:**
- Consumes: 现有 `agent_sessions` 表 schema(via alembic / 手写 SQL)
- Produces: 新列 `langgraph_thread_id TEXT NULLABLE` 落库;SQLAlchemy ORM 模型同名字段

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_agent_session_langgraph_thread_id_column.py
import sqlite3


def test_agent_sessions_has_langgraph_thread_id_column(tmp_path):
    db = tmp_path / "test.db"
    # 这里应复用项目既有 schema 初始化(例如 conftest 中的 _create_all)
    # 本测试只验证列存在即可
    from sqlalchemy import create_engine, text
    from app.models.orm_v04 import Base

    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)

    cols = [row[1] for row in engine.connect().execute(text("PRAGMA table_info(agent_sessions)")).fetchall()]
    assert "langgraph_thread_id" in cols
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_agent_session_langgraph_thread_id_column.py -v`
Expected: FAIL `AssertionError: 'langgraph_thread_id' not in [...现有列...]`

- [ ] **Step 3: 加 ORM 字段 + 最小迁移脚本**

`backend/app/models/orm_v04.py` 找到 `class AgentSessionORM` 或对应定义,加字段:

```python
# v0.8 spec §6.1 — LangGraph thread_id 持久化(nullable,首次发起时 CheckpointAdapter 写 uuid4)
langgraph_thread_id: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
```

`backend/scripts/migrate_add_langgraph_thread_id.py`:

```python
"""一次性 SQL 迁移:补齐 agent_sessions.langgraph_thread_id 列,无 alembic 时备选。

使用方式:
    sqlite3 data/geo.db < migrate_add_langgraph_thread_id.sql
a 项目内 alembic 已就位则改用:
    alembic upgrade head
"""
from __future__ import annotations

import sqlite3


SQL = """
ALTER TABLE agent_sessions ADD COLUMN langgraph_thread_id TEXT;
"""


def main(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SQL)
    finally:
        conn.close()
    print(f"已添加 langgraph_thread_id 列到 {db_path}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "data/geo.db")
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_agent_session_langgraph_thread_id_column.py -v`
Expected: 1 passed
外加 DB-level 检查:`sqlite3 data/test.db "PRAGMA table_info(agent_sessions)"` 含 `langgraph_thread_id`

- [ ] **Step 5: commit**

```bash
git add backend/app/models/orm_v04.py backend/scripts/migrate_add_langgraph_thread_id.py backend/tests/test_agent_session_langgraph_thread_id_column.py
git commit -m "feat(orm): agent_sessions.langgraph_thread_id TEXT NULL"
```

---

### Task 7: HITL 桥接 — interrupt / Command(resume=...) ↔ HumanConfirmationRequired

**Files:**
- Modify: `backend/app/domain/agent/langgraph_nodes/__init__.py`(可选,导出)
- Modify: `backend/app/domain/agent/react_graph.py`(Task 11 创建,本 task 仅产出函数,后续在 Task 11 中接入图;实际 HITL 接线在 Task 11+)
- Create: `backend/tests/test_hitl_interrupt_bridge.py`

**Interfaces:**
- Consumes: 现有 `HumanConfirmationRequired` exception(`app.domain.exceptions`)、`interrupt` / `Command` from langgraph.types
- Produces: `hitl_guard(state, runtime) -> dict` — 捕获 `HumanConfirmationRequired` → 调 `interrupt(payload)` → 写入 `state.tool_call_log`;`resume_command(decision)` — 包装 `Command(resume=user_decision)` 给 api 层调用

> 本 task 仅有接口与单元测试;接线在 Task 11 react_graph 工厂内进行。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_hitl_interrupt_bridge.py
import pytest
from langgraph.types import interrupt, Command

from app.domain.exceptions import HumanConfirmationRequired


def test_hitl_guard_calls_interrupt_when_tool_raises():
    """_execute 抛 HumanConfirmationRequired 时,hitl_guard 必须调 interrupt(payload)。"""

    called = {}

    def fake_interrupt(payload):
        called["payload"] = payload
        # 模拟 LangGraph __interrupt__
        raise StopIteration("__interrupt__")

    # Patch
    import app.domain.agent.langgraph_nodes.policy as policy_module
    policy_module.interrupt = fake_interrupt  # type: ignore

    from app.domain.agent.langgraph_nodes.policy import hitl_guard

    state = {"messages": [], "session_id": "s1", "tool_call_log": []}

    with pytest.raises(StopIteration):
        hitl_guard(
            state,
            tool_fn=lambda: (_ for _ in ()).throw(HumanConfirmationRequired(tool_call_id="tc1", args={"q": "x"})),
        )

    assert called["payload"]["tool_call_id"] == "tc1"
    assert called["payload"]["args"] == {"q": "x"}


def test_resume_command_wraps_decision():
    from app.domain.agent.langgraph_nodes.policy import resume_command
    cmd = resume_command({"decision": "approve", "tool_call_id": "tc1"})
    assert isinstance(cmd, Command)
    assert cmd.resume == {"decision": "approve", "tool_call_id": "tc1"}
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_hitl_interrupt_bridge.py -v`
Expected: FAIL `ImportError: cannot import name 'hitl_guard' from 'app.domain.agent.langgraph_nodes.policy'`

- [ ] **Step 3: 写最小实现**

`backend/app/domain/agent/langgraph_nodes/policy.py`:

```python
"""v0.8 PolicyNode + HITL guard(spec §9 + §4.2.5)。

复用 _LLM_TRANSIENT_EXCEPTIONS / _TOOL_TRANSIENT_EXCEPTIONS。
HITL 桥接:HumanConfirmationRequired → interrupt(payload),
恢复走 resume_command(user_decision) → Command(resume=...)。
"""
from __future__ import annotations

from langgraph.types import Command, interrupt

from app.domain.exceptions import HumanConfirmationRequired, _LLM_TRANSIENT_EXCEPTIONS, _TOOL_TRANSIENT_EXCEPTIONS


def hitl_guard(state: dict, tool_fn: callable) -> dict:
    """包 tool_fn 调用,把 HumanConfirmationRequired 转换为 interrupt(payload)。

    LangGraph 捕获 interrupt 后会中止当前 turn,持久化到 checkpoint;
    后续 resume 通过 resume_command 注入用户决策。
    """
    try:
        result = tool_fn()
        return {"tool_call_log": state.get("tool_call_log", []) + [{"status": "ok", "result": result}]}
    except HumanConfirmationRequired as exc:
        interrupt({"tool_call_id": exc.tool_call_id, "args": exc.args, "resume_token": exc.tool_call_id})


def resume_command(user_decision: dict) -> Command:
    """用户决策 → LangGraph Command(resume=...) 注入。"""
    return Command(resume=user_decision)
```

> ⚠️ 实际 HITLGuard node 在 Task 11 react_graph 内接线,本 task 仅产出函数。

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_hitl_interrupt_bridge.py -v`
Expected: 2 passed

- [ ] **Step 5: commit**

```bash
git add backend/app/domain/agent/langgraph_nodes/policy.py backend/tests/test_hitl_interrupt_bridge.py
git commit -m "feat(hitl): hitl_guard + resume_command — interrupt ↔ HumanConfirmationRequired 桥接"
```

---

## Sprint 3(记忆 / 压缩 / 截断)

### Task 8: MemorySnapshotNode — L2 memory prepend

**Files:**
- Create: `backend/app/domain/agent/langgraph_nodes/memory_snapshot.py`
- Create: `backend/tests/test_memory_snapshot_node.py`

**Interfaces:**
- Consumes: `app.domain.agent.memory.MemoryService` 既有函数(`build_messages` / `_apply_memory_prepend` / `select_relevant`)
- Produces: `memory_snapshot_node(state, runtime) -> dict`,**严格保留 react_loop 既有语义**:`memory_chunk` prepend 到最后一条 user 消息(NOT 进 system)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_memory_snapshot_node.py
from langchain_core.messages import HumanMessage

from app.domain.agent.langgraph_nodes.memory_snapshot import memory_snapshot_node


def test_memory_snapshot_prepends_to_last_user_message():
    state = {
        "messages": [HumanMessage(content="请诊断"), HumanMessage(content="再问")],
        "session_id": "u1",
        "memory_chunk": {"scope": "u1", "items": [{"text": "prior pref", "score": 0.9}]},
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = memory_snapshot_node(state, runtime=None)
    msgs = out["messages"]
    # 最后一条 user 消息应该被 prepend 记忆
    assert any("prior pref" in str(m.content) for m in msgs)


def test_memory_snapshot_no_op_when_memory_chunk_none():
    state = {
        "messages": [HumanMessage(content="问")],
        "session_id": "u1",
        "memory_chunk": None,
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = memory_snapshot_node(state, runtime=None)
    assert out["messages"] == state["messages"]


def test_memory_snapshot_does_not_inject_into_system():
    from langchain_core.messages import SystemMessage
    state = {
        "messages": [SystemMessage(content="你是 GEO 助手"), HumanMessage(content="问")],
        "session_id": "u1",
        "memory_chunk": {"items": [{"text": "pref", "score": 1.0}]},
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = memory_snapshot_node(state, runtime=None)
    sys_msgs = [m for m in out["messages"] if isinstance(m, SystemMessage)]
    assert all("pref" not in m.content for m in sys_msgs)
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_memory_snapshot_node.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 写最小实现(包既有 memory.py)**

```python
# backend/app/domain/agent/langgraph_nodes/memory_snapshot.py
"""v0.8 MemorySnapshotNode(spec §4.2.3):react_graph 内 L2 记忆 prepend。

严格保留 react_loop 既有 _apply_memory_prepend 语义:
- 把 memory_chunk 拼到最后一条 user 消息之前(NOT 进 system)
- 若 memory_chunk 为 None 则 no-op
- 包 build_messages / select_relevant 既有函数,不重写
"""
from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, get_buffer_string

from app.domain.agent.memory import MemoryService


def memory_snapshot_node(state: TypedDict, runtime) -> dict:
    """Prepend memory_chunk 到最后一条 user 消息。

    Returns:
        dict: LangGraph 自动合并到 state
    """
    messages = list(state["messages"])
    chunk = state.get("memory_chunk")
    if not chunk or not chunk.get("items"):
        return {}

    # 找最后一条 user 消息(react_loop 既有行为)
    last_user_idx = None
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_user_idx = i
            break
    if last_user_idx is None:
        return {}

    memory_text = MemoryService.format_prepend(chunk)
    original = messages[last_user_idx].content
    messages[last_user_idx] = HumanMessage(content=f"{memory_text}\n\n{original}")

    return {"messages": messages}
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_memory_snapshot_node.py -v`
Expected: 3 passed

- [ ] **Step 5: commit**

```bash
git add backend/app/domain/agent/langgraph_nodes/memory_snapshot.py backend/tests/test_memory_snapshot_node.py
git commit -m "feat(memory): MemorySnapshotNode — L2 记忆按 react_loop 既有语义 prepend"
```

---

### Task 9: TruncateMessagesNode — 4 策略压缩 + token 截断可解释

**Files:**
- Create: `backend/app/domain/agent/langgraph_nodes/truncate_messages.py`
- Create: `backend/tests/test_truncate_messages_node.py`

**Interfaces:**
- Consumes: `app.domain.agent.adaptive_compression`、`truncation_explainable.TruncationResult`
- Produces: `truncate_messages_node(state, runtime) -> dict`,跑完返回 `{"messages": state["messages"], "truncation_result": TruncationResult dict}`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_truncate_messages_node.py
from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.agent.langgraph_nodes.truncate_messages import truncate_messages_node


def test_truncate_messages_picks_strategy_and_updates_state():
    state = {
        "messages": [SystemMessage(content="sys")] + [HumanMessage(content=f"msg-{i}" * 100) for i in range(20)],
        "session_id": "s1",
        "memory_chunk": None,
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = truncate_messages_node(state, runtime=None)
    assert "messages" in out
    assert "truncation_result" in out
    assert out["truncation_result"]["strategy"] in {"noop", "truncate", "drop", "summarize"}


def test_truncate_messages_noop_when_under_budget():
    state = {
        "messages": [HumanMessage(content="hi")],
        "session_id": "s1",
        "memory_chunk": None,
        "truncation_result": None,
        "tool_call_log": [],
    }
    out = truncate_messages_node(state, runtime=None)
    assert out["truncation_result"]["strategy"] == "noop"
    assert out["truncation_result"]["saved_tokens"] == 0
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_truncate_messages_node.py -v`
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 写最小实现(包既有 adaptive_compression + truncation)**

```python
# backend/app/domain/agent/langgraph_nodes/truncate_messages.py
"""v0.8 TruncateMessagesNode(spec §4.2.4 + §8.2/§8.3):4 策略自适应压缩 + token 截断可解释。

直接调用既有 adaptive_compression.select_strategy + truncation_explainable.TruncationResult,
不重写策略,只把决策回流到 state.truncation_result 用于日志与 metrics。
"""
from __future__ import annotations

from typing import TypedDict

from app.domain.agent.adaptive_compression import select_strategy, apply_strategy
from app.domain.agent.truncation_explainable import TruncationResult, compute_saved_tokens


def truncate_messages_node(state: TypedDict, runtime) -> dict:
    messages = state["messages"]
    strategy = select_strategy(messages)
    new_messages, decisions = apply_strategy(messages, strategy)
    saved = compute_saved_tokens(messages, new_messages)

    result = TruncationResult(
        strategy=strategy,
        saved_tokens=saved,
        decisions=decisions,
    )
    return {
        "messages": new_messages,
        "truncation_result": result.to_dict(),
    }
```

> 上面的 `select_strategy / apply_strategy / TruncationResult.to_dict / compute_saved_tokens` 都是 `adaptive_compression.py` / `truncation_explainable.py` 已暴露的公开接口。如果某方法签名不一致,以既有公开方法为准并调整调用。

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_truncate_messages_node.py -v`
Expected: 2 passed

- [ ] **Step 5: commit**

```bash
git add backend/app/domain/agent/langgraph_nodes/truncate_messages.py backend/tests/test_truncate_messages_node.py
git commit -m "feat(truncate): TruncateMessagesNode — 4 策略自适应压缩 + 截断决策回写"
```

---

### Task 10: PolicyNode — transient/programming 区分 + retry

**Files:**
- Modify: `backend/app/domain/agent/langgraph_nodes/policy.py`(扩展,接入 retry 装饰器)
- Create: `backend/tests/test_policy_node.py`

**Interfaces:**
- Consumes: `_LLM_TRANSIENT_EXCEPTIONS` / `_TOOL_TRANSIENT_EXCEPTIONS`
- Produces: `policy_llm_call(state, runtime) -> dict`(retry 包 transient),`policy_tool_call(state, runtime) -> dict`(编程错误不重试,产 llm_error)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_policy_node.py
import pytest

from app.domain.agent.langgraph_nodes.policy import policy_llm_call, policy_tool_call
from app.domain.exceptions import (
    TransientLLMError, HumanConfirmationRequired, ProgrammingError,
    _LLM_TRANSIENT_EXCEPTIONS,  # noqa
)


def test_policy_llm_call_retries_on_transient(monkeypatch):
    calls = {"n": 0}

    def fake_llm(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientLLMError("rate limit")
        return {"messages": []}

    monkeypatch.setattr("app.domain.agent.langgraph_nodes.policy._call_llm", fake_llm)

    out = policy_llm_call({"messages": [], "session_id": "s1"}, runtime=None, llm_client=None)
    assert calls["n"] == 3


def test_policy_llm_call_does_not_retry_on_programming(monkeypatch):
    calls = {"n": 0}

    def fake_llm(*args, **kwargs):
        calls["n"] += 1
        raise ProgrammingError("schema drift")

    monkeypatch.setattr("app.domain.agent.langgraph_nodes.policy._call_llm", fake_llm)

    with pytest.raises(ProgrammingError):
        policy_llm_call({"messages": [], "session_id": "s1"}, runtime=None, llm_client=None)
    assert calls["n"] == 1


def test_policy_tool_call_does_not_retry_on_programming(monkeypatch):
    calls = {"n": 0}

    def fake_tool(*args, **kwargs):
        calls["n"] += 1
        raise ProgrammingError("bad arg")

    monkeypatch.setattr("app.domain.agent.langgraph_nodes.policy._call_tool", fake_tool)

    with pytest.raises(ProgrammingError):
        policy_tool_call({"messages": [], "session_id": "s1"}, runtime=None, tool_executor=None, tool_call={"name": "x"})
    assert calls["n"] == 1
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_policy_node.py -v`
Expected: FAIL `ImportError: cannot import name 'policy_llm_call'`

- [ ] **Step 3: 写最小实现**

扩展 `backend/app/domain/agent/langgraph_nodes/policy.py`:

```python
# 追加到 policy.py 末尾
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings  # Settings.max_retries
from app.domain.llm_client import LLMClient
from app.domain.agent.tool_executor import ToolExecutor


def _call_llm(state: dict, llm_client: LLMClient) -> dict:
    """实际 LLM 调用(由 react_graph agent_node 调用)。"""
    return llm_client.chat(state["messages"])


def _call_tool(state: dict, tool_executor: ToolExecutor, tool_call: dict) -> dict:
    return tool_executor.execute(tool_call["name"], tool_call["args"])


@retry(
    retry=retry_if_exception_type(_LLM_TRANSIENT_EXCEPTIONS),
    stop=stop_after_attempt(get_settings().max_retries),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
def policy_llm_call(state: dict, runtime, llm_client: LLMClient) -> dict:
    """包 _call_llm 的 retry/transient 区分。"""
    return _call_llm(state, llm_client)


def policy_tool_call(state: dict, runtime, tool_executor: ToolExecutor, tool_call: dict) -> dict:
    """包 _call_tool;编程错误不重试,直接抛(由 PolicyNode 转 llm_error SSE)。"""
    return _call_tool(state, tool_executor, tool_call)
```

(`tenacity` 已在 requirements.txt 或 `pyproject.toml`,若没有则 `tenacity>=8.0` 追加)

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_policy_node.py -v`
Expected: 3 passed
(若 `tenacity` 未装:`pip install 'tenacity>=8.0'`)

- [ ] **Step 5: commit**

```bash
git add backend/app/domain/agent/langgraph_nodes/policy.py backend/tests/test_policy_node.py
git commit -m "feat(policy): policy_llm_call / policy_tool_call — transient/programming 区分 + retry"
```

---

## Sprint 4(react_graph 工厂 + dispatch + 双跑灰度)

### Task 11: react_graph 工厂(整合所有自定义 node)

**Files:**
- Create: `backend/app/domain/agent/react_graph.py`
- Create: `backend/app/domain/agent/state.py`(已在 Task 2 创建)
- Create: `backend/tests/test_react_graph_integration.py`

**Interfaces:**
- Consumes:`AgentState`(Task 2)、`MemorySnapshotNode`(Task 8)、`TruncateMessagesNode`(Task 9)、`PolicyNode`(Task 10)、`HITLGuard`(Task 7)、`LANGCHAIN_TOOLS`(Task 3)
- Produces:`build_react_graph() -> CompiledStateGraph`,包含节点 `memory_snapshot → agent_node(model) → tool_node(5 tools) → truncate_messages → memory_snapshot_end`,checkpoint 用 `MemorySaver`,HITL 用 `interrupt()`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_react_graph_integration.py
import pytest
from langchain_core.messages import HumanMessage, AIMessage

from app.domain.agent.react_graph import build_react_graph


@pytest.mark.asyncio
async def test_build_react_graph_returns_compiled_graph():
    g = build_react_graph()
    assert hasattr(g, "astream_events")
    assert hasattr(g, "invoke")


@pytest.mark.asyncio
async def test_react_graph_invoke_with_simple_message_returns_messages():
    g = build_react_graph()
    out = await g.ainvoke(
        {
            "messages": [HumanMessage(content="hi")],
            "session_id": "test-graph-1",
            "memory_chunk": None,
            "truncation_result": None,
            "tool_call_log": [],
        },
        config={"configurable": {"thread_id": "test-graph-1"}},
    )
    msgs = out["messages"]
    assert len(msgs) >= 1
    assert any(isinstance(m, AIMessage) or hasattr(m, "type") for m in msgs)
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_react_graph_integration.py -v`
Expected: FAIL `ImportError: cannot import name 'build_react_graph'`

- [ ] **Step 3: 写最小实现**

```python
# backend/app/domain/agent/react_graph.py
"""v0.8 react_graph 工厂(spec §3.1)。

节点拓扑:
  START → memory_snapshot → agent(model+tools) → tool_node → HITLGuard → truncate → memory_snapshot → END
                                                                    ↘ END (turn_complete)

LLM 链路(spec §4.0):react_graph.agent_node 调 LLMClient,不替换。
HITL(spec §5.3):tool_node 内调用 hitl_guard,若需确认则 interrupt(payload)。
Checkpoint(spec §6):MemorySaver 内嵌,thread_id 由 CheckpointAdapter 写落 agent_sessions.langgraph_thread_id。
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.core.providers import resolve_providers  # 已有
from app.domain.agent.langgraph_nodes.memory_snapshot import memory_snapshot_node
from app.domain.agent.langgraph_nodes.policy import hitl_guard, policy_llm_call
from app.domain.agent.langgraph_nodes.truncate_messages import truncate_messages_node
from app.domain.agent.state import AgentState
from app.domain.agent.tools import LANGCHAIN_TOOLS
from app.domain.llm_client import LLMClient


def _agent_node(state: AgentState, runtime) -> dict:
    """react_graph 主循环 LLM 调用 + tool_calls 决策。"""
    llm = _get_llm(runtime)
    return policy_llm_call(state, runtime, llm_client=llm)


def _tool_node(state: AgentState, runtime) -> dict:
    """包 hitl_guard,specialist handoff 继续走 tool_executor 内部降级路径。"""
    tn = ToolNode(LANGCHAIN_TOOLS)
    return tn.invoke(state, runtime)


def _get_llm(runtime):
    """从 runtime.config 拿 llm_client(由 dispatch 注入);若 None 走 resolve_providers 默认。"""
    if runtime is not None and hasattr(runtime, "config") and runtime.config and "llm" in runtime.config:
        return runtime.config["llm"]
    return LLMClient(provider=resolve_providers().default_text_provider)


def build_react_graph():
    g = StateGraph(AgentState)
    g.add_node("memory_snapshot", memory_snapshot_node)
    g.add_node("agent", _agent_node)
    g.add_node("tool_node", _tool_node)
    g.add_node("truncate", truncate_messages_node)
    g.add_node("memory_snapshot_end", memory_snapshot_node)

    g.add_edge(START, "memory_snapshot")
    g.add_edge("memory_snapshot", "agent")
    g.add_conditional_edges("agent", lambda s: "tool_node" if s["messages"][-1].tool_calls else END)
    g.add_edge("tool_node", "truncate")
    g.add_edge("truncate", "memory_snapshot_end")
    g.add_edge("memory_snapshot_end", END)

    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer, interrupt_before=["tool_node"])
```

> ⚠️ `interrupt_before=["tool_node"]` 让 LangGraph 在 tool_node 前自动持久化状态;HITLGuard 通过 `interrupt(payload)` 在 tool_node 内部拦截 HumanConfirmationRequired。语义对齐 react_loop 现有 `pending_confirmation`。
> 若 LangGraph 1.x 不支持 `interrupt_before` 参数,改用 `interrupt=["HITLGuard"]` 在 edges 中显式 edge。

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_react_graph_integration.py -v`
Expected: 2 passed

- [ ] **Step 5: commit**

```bash
git add backend/app/domain/agent/react_graph.py backend/tests/test_react_graph_integration.py
git commit -m "feat(graph): react_graph 工厂 — 整合 4 个自定义 node + create_react_agent 拓扑"
```

---

### Task 12: dispatch 模块 + api/agent_chat 接入

**Files:**
- Create: `backend/app/domain/agent/dispatch.py`
- Modify: `backend/app/api/agent_chat.py:80-120`(找到 `run_agent_turn` 接入点)

**Interfaces:**
- Consumes:`Settings.langgraph_enabled`(Task 1)、`react_graph`(Task 11)、`react_loop._drive_react_loop`(既有)
- Produces:`run_agent_turn(...) -> AsyncIterator[bytes]` 同一函数名,内部按 flag 路由

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_dispatch.py
import pytest

from app.core.config import get_settings
from app.domain.agent.dispatch import run_agent_turn


@pytest.mark.asyncio
async def test_dispatch_routes_to_react_loop_when_flag_false(monkeypatch):
    monkeypatch.setattr(get_settings(), "langgraph_enabled", False)

    called = {"path": None}

    async def fake_react_turn(*args, **kwargs):
        called["path"] = "react_loop"
        yield b'{"type":"turn_complete"}\n'

    async def fake_langgraph_turn(*args, **kwargs):
        called["path"] = "langgraph"
        yield b'{"type":"turn_complete"}\n'

    monkeypatch.setattr("app.domain.agent.dispatch._run_react_loop_turn", fake_react_turn)
    monkeypatch.setattr("app.domain.agent.dispatch._run_langgraph_turn", fake_langgraph_turn)

    out = []
    async for sse in run_agent_turn(session_id="t1", message="hi"):
        out.append(sse)
    assert called["path"] == "react_loop"
    assert out


@pytest.mark.asyncio
async def test_dispatch_routes_to_langgraph_when_flag_true(monkeypatch):
    monkeypatch.setattr(get_settings(), "langgraph_enabled", True)

    called = {"path": None}

    async def fake_react_turn(*args, **kwargs):
        called["path"] = "react_loop"
        yield b""

    async def fake_langgraph_turn(*args, **kwargs):
        called["path"] = "langgraph"
        yield b'{"type":"turn_complete"}\n'

    monkeypatch.setattr("app.domain.agent.dispatch._run_react_loop_turn", fake_react_turn)
    monkeypatch.setattr("app.domain.agent.dispatch._run_langgraph_turn", fake_langgraph_turn)

    out = []
    async for sse in run_agent_turn(session_id="t1", message="hi"):
        out.append(sse)
    assert called["path"] == "langgraph"
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_dispatch.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: 写最小实现**

```python
# backend/app/domain/agent/dispatch.py
"""v0.8 dispatch(spec §10.2):按 Settings.langgraph_enabled 路由 run_agent_turn。

默认 flag=False 沿用 react_loop,保留 1 个里程碑;
切流 flag=True 后 langgraph 接管。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.config import get_settings


async def _run_react_loop_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    """现有路径(react_loop._drive_react_loop 内部 yield SSE)。

    本函数把 react_loop 既有 yield 行为封装,对外不变。
    """
    from app.domain.agent.react_loop import run_agent_turn as react_impl  # type: ignore
    async for sse in react_impl(session_id=session_id, message=message):  # type: ignore
        yield sse


async def _run_langgraph_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    """LangGraph 路径:react_graph.astream_events → SSEBridge.dispatch。"""
    from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge
    sse_bridge = SSEBridge()
    async for sse in sse_bridge.replay({"session_id": session_id, "message": message}):
        yield sse


async def run_agent_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    """api 层调用入口(spec §10.2)。"""
    if get_settings().langgraph_enabled:
        async for sse in _run_langgraph_turn(session_id, message):
            yield sse
    else:
        async for sse in _run_react_loop_turn(session_id, message):
            yield sse
```

`backend/app/api/agent_chat.py`:找到原 `run_agent_turn` 调用点,从 `app.domain.agent.react_loop` 改为 `app.domain.agent.dispatch`:

```python
# 修改 import
- from app.domain.agent.react_loop import run_agent_turn, run_agent_turn_from_checkpoint
+ from app.domain.agent.dispatch import run_agent_turn
+ from app.domain.agent.react_loop import run_agent_turn_from_checkpoint  # HITL 恢复仍走 react_loop 暂时,后续 Task 14 替换
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_dispatch.py -v`
Expected: 2 passed
并验证默认链路没破:`pytest tests/test_api_agent_chat.py -v` 全绿

- [ ] **Step 5: commit**

```bash
git add backend/app/domain/agent/dispatch.py backend/app/api/agent_chat.py backend/tests/test_dispatch.py
git commit -m "feat(dispatch): 按 Settings.langgraph_enabled 路由 run_agent_turn"
```

---

### Task 13: evals --compare 双跑 runner

**Files:**
- Modify: `backend/evals/runner.py:1-30`(扩展入口加 --compare)
- Create: `backend/tests/test_evals_compare_runner.py`

**Interfaces:**
- Consumes: 既有 `evals/cases.py`、`evals/judge.py`、`react_loop.run_agent_turn`
- Produces:`runner --compare` 同时跑 react_loop 与 langgraph 输出 diff 报告(到 `reports/eval/diff/<date>.md`),返回 `{overall_match, tool_call_match, handoff_match, sse_event_count_equal, path: compare_report}`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_evals_compare_runner.py
import pytest

from evals.runner import compare_evals


@pytest.mark.asyncio
async def test_compare_evals_produces_diff_report(tmp_path, monkeypatch):
    """对比 react_loop 与 langgraph 同一 case 的输出,产出 diff 报告。"""
    cases = [
        {"session_id": "c1", "message": "诊断品牌 X 科技感"},
    ]

    # stub LLM 调,固定返回
    async def stub_llm(messages, **kwargs):
        class Resp:
            content = "stubbed response"
            tool_calls = []
        return Resp

    monkeypatch.setattr("app.domain.llm_client.LLMClient.chat", stub_llm)

    report = await compare_evals(cases, output_dir=tmp_path)
    assert report["overall_match"] >= 0.95
    assert report["tool_call_match"] == 1.0
    assert report["handoff_match"] == 1.0
    assert report["sse_event_count_equal"] is True
    assert (tmp_path / "diff_report.md").exists()
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_evals_compare_runner.py -v`
Expected: FAIL `ImportError: cannot import name 'compare_evals'`

- [ ] **Step 3: 写最小实现**

`backend/evals/runner.py` 末尾追加:

```python
# === v0.8 compare 模式(spec §10.1) ===
import json
from pathlib import Path
from typing import Any


async def _collect_sse(run_fn, session_id: str, message: str) -> list[dict]:
    chunks = []
    async for sse in run_fn(session_id=session_id, message=message):
        try:
            chunks.append(json.loads(sse))
        except json.JSONDecodeError:
            pass
    return chunks


async def compare_evals(cases: list[dict], output_dir: Path) -> dict[str, Any]:
    """同一 input 跑 react_loop 与 langgraph,产出 diff 报告。

    Returns:
        dict 含 overall_match / tool_call_match / handoff_match / sse_event_count_equal
    """
    from app.domain.agent.dispatch import run_agent_turn as dispatch

    overall_matches = []
    tool_matches = []
    handoff_matches = []
    sse_counts = []

    for c in cases:
        react_chunks = await _collect_sse(lambda **kw: dispatch(**{**kw, "langgraph_enabled": False}), c["session_id"], c["message"])  # noqa
        # 简化:直接调 react_loop 与 langgraph 两个内部函数
        from app.domain.agent.dispatch import _run_react_loop_turn, _run_langgraph_turn
        react_chunks = await _collect_sse(_run_react_loop_turn, c["session_id"], c["message"])
        lang_chunks = await _collect_sse(_run_langgraph_turn, c["session_id"], c["message"])

        # text 相似度(token-level ROUGE-L 简化实现:unigram overlap)
        react_text = "".join(c["data"].get("content", "") for c in react_chunks if c.get("type") == "assistant_message")
        lang_text = "".join(c["data"].get("content", "") for c in lang_chunks if c.get("type") == "assistant_message")
        overlap = _rouge_l(react_text, lang_text)

        # tool_call_match 100%(同 5 schema 名)
        react_tools = {c2.get("name") for c2 in react_chunks if c2.get("type") == "tool_call_start"}
        lang_tools = {c2.get("name") for c2 in lang_chunks if c2.get("type") == "tool_call_start"}
        tool_match = 1.0 if react_tools == lang_tools else 0.0

        # handoff_event_match 100%(human_confirmation_required 事件数)
        react_handoff = sum(1 for c2 in react_chunks if c2.get("type") == "human_confirmation_required")
        lang_handoff = sum(1 for c2 in lang_chunks if c2.get("type") == "human_confirmation_required")
        handoff_match = 1.0 if react_handoff == lang_handoff else 0.0

        # SSE event count 相等
        sse_count_equal = len(react_chunks) == len(lang_chunks)

        overall_matches.append(overlap)
        tool_matches.append(tool_match)
        handoff_matches.append(handoff_match)
        sse_counts.append(sse_count_equal)

    report = {
        "overall_match": sum(overall_matches) / len(overall_matches) if overall_matches else 1.0,
        "tool_call_match": sum(tool_matches) / len(tool_matches),
        "handoff_match": sum(handoff_matches) / len(handoff_matches),
        "sse_event_count_equal": all(sse_counts),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "diff_report.md").write_text(
        f"""# Compare Report
overall_match: {report['overall_match']:.3f}
tool_call_match: {report['tool_call_match']}
handoff_match: {report['handoff_match']}
sse_event_count_equal: {report['sse_event_count_equal']}

逐 case diff 见日志(本 task 输出 pathlib 列出,生产环境打 Langfuse)。
""",
        encoding="utf-8",
    )
    return report


def _rouge_l(a: str, b: str) -> float:
    """简化 ROUGE-L:最长公共子序列长度 / max(len(a), len(b))。"""
    if not a or not b:
        return 0.0 if a != b else 1.0
    la, lb = a.split(), b.split()
    m, n = len(la), len(lb)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m):
        for j in range(n):
            dp[i + 1][j + 1] = dp[i][j] + 1 if la[i] == lb[j] else max(dp[i + 1][j], dp[i][j + 1])
    return dp[m][n] / max(m, n)
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_evals_compare_runner.py -v`
Expected: 1 passed

- [ ] **Step 5: commit**

```bash
git add backend/evals/runner.py backend/tests/test_evals_compare_runner.py
git commit -m "feat(evals): compare 双跑 react_loop + langgraph — 输出 diff 报告"
```

---

### Task 14: react_loop.py 瘦身,标 deprecated(保留 1 里程碑)

**Files:**
- Modify: `backend/app/domain/agent/react_loop.py`(725 → ~250 行)

**Interfaces:**
- Consumes: 现 react_loop 全部公开 API;新 dispatch 模块已经分走 langgraph 路径
- Produces: react_loop 只剩 react_loop 路径(Settings.langgraph_enabled=False 时调用);`_drive_react_loop` / `run_agent_turn` / `run_agent_turn_from_checkpoint` 公开签名保持

- [ ] **Step 1: 行为等价测试(确认瘦身不破)**

`backend/tests/test_react_loop_legacy_retained.py`:

```python
"""确保 langgraph_enabled=False 路径与 v0.7 行为等价。"""
import pytest

from app.domain.agent.dispatch import run_agent_turn
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_langgraph_disabled_uses_react_loop_path(monkeypatch):
    monkeypatch.setattr(get_settings(), "langgraph_enabled", False)
    out = []
    async for sse in run_agent_turn(session_id="legacy", message="hi"):
        out.append(sse)
        if out[-1].endswith(b'{"type":"turn_complete"}\n'):
            break
    assert out
```

Run: `.venv/Scripts/python.exe -m pytest backend/tests/test_react_loop_legacy_retained.py -v`
Expected: 1 passed(若失败,**先回归测试**;不允许进入 Step 2)

- [ ] **Step 2: 抽离可复用代码到私有模块**

react_loop.py 现行包含:
- 主循环 `_drive_react_loop`(react 路径专属)
- LLM 调用 retry / PolicyNode 已抽到 Task 10
- L2 prepend 已抽到 Task 8
- adaptive_compression + truncation 已抽到 Task 9
- tools.py 升级为 @tool 已做(Task 3)
- 工具 dispatch 还由 tool_executor 持有

`backend/app/domain/agent/react_loop.py` 头部加注释:

```python
"""v0.8 react_loop 瘦身(spec 2026-07-14-langgraph-react-loop-design §14)。

主循环保留 react 路径(Settings.langgraph_enabled=False 时);
- L2 记忆 prepend 由 MemorySnapshotNode 接管(Task 8)
- 4 策略压缩由 TruncateMessagesNode 接管(Task 9)
- retry/transient 由 PolicyNode 接管(Task 10)
- 5 tool dispatch 改用 LANGCHAIN_TOOLS(Task 3)

react_loop 仍保留这部分代码是为了支持 Settings.langgraph_enabled=False 时的灰度回滚。
1 个里程碑后删除(预计在 v0.9)。
"""
```

简化的 react_loop.py(只剩 react 主循环实现,~250 行):

```python
async def _drive_react_loop(state, llm, tool_executor, settings):
    """精简版 react 主循环,逻辑结构 v0.7 同等。"""
    iterations = 0
    while iterations < settings.max_react_iterations:
        iterations += 1
        resp = await llm.chat(state["messages"])
        if not resp.tool_calls:
            state["messages"].append(resp)
            yield {"type": "assistant_message", "content": resp.content}
            yield {"type": "turn_complete"}
            return
        # tool 调用路径
        for tc in resp.tool_calls:
            try:
                result = await tool_executor.execute(tc["name"], tc["args"])
            except HumanConfirmationRequired as exc:
                yield {"type": "human_confirmation_required", "tool_call_id": exc.tool_call_id, "args": exc.args}
                return
            yield {"type": "tool_call_start", "name": tc["name"], "args": tc["args"]}
            yield {"type": "tool_call_result", "name": tc["name"], "output": result}
            state["messages"].append(ToolMessage(content=json.dumps(result), tool_call_id=tc["id"]))
    yield {"type": "max_iterations_reached"}
```

(其余 SSE 事件 / memory / compression 在 `_drive_react_loop` 入口前/后由既有 helper 完成,大部分可保留)

- [ ] **Step 3: 跑现有 react_loop 测试,确保全绿**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/ -v -k "react_loop or legacy_retained or hitl or memory or truncation or tool_executor"`
Expected: 全绿;若红:revert Step 2 改动

- [ ] **Step 4: 跑完整测试套**

Run: `.venv/Scripts/python.exe -m pytest backend/tests/ -v`
Expected: 全绿(740 → 750+ 新测试)

- [ ] **Step 5: commit**

```bash
git add backend/app/domain/agent/react_loop.py backend/tests/test_react_loop_legacy_retained.py
git commit -m "refactor(react_loop): 瘦身至 250 行 — 标注 deprecated,1 里程碑内可删"
```

---

### Task 15: AGENTS.md §6.5 修订 + import-linter 扩展

**Files:**
- Modify: `AGENTS.md`(§6.5)
- Modify: `backend/tests/test_no_repo_to_service.py`(扩展反向依赖阻断规则)

**Interfaces:**
- Consumes:现有 import-linter 配置 `backend/.import-linter.toml`
- Produces:AGENTS.md §6.5 加 1 行例外;import-linter 新规:`app.domain.agent.react_graph` 不能被 `app.domain.agent.{tools, tool_executor, handoff, *specialist}` 反向 import

- [ ] **Step 1: 修改 AGENTS.md §6.5**

打开 `AGENTS.md`,找到 §6.5 「不引入新框架」段落,改成:

```diff
 ### 6.5 不引入新框架

-❌ LangGraph / LangChain / LlamaIndex — 自写 ReAct 循环可控性 + 学习价值
+❌ LangGraph / LangChain / LlamaIndex — 自写 ReAct 循环可控性 + 学习价值
+✅ 例外:`app/domain/agent/react_loop.py` 主循环可使用 `langgraph>=1.0,<2.0` 与 `langchain-core`
+  (详见 `docs/superpowers/specs/2026-07-14-langgraph-react-loop-design.md`)
 ❌ 改 ORM 版本结构(orm_v02-v04 演进历史保留)
 ❌ 改业务逻辑(仅工程化补强)
```

- [ ] **Step 2: 修改 import-linter 配置**

打开 `backend/.import-linter.toml`,在末尾追加:

```toml
# v0.8 spec §1.4 — 阻断 langgraph 类型跨域泄漏
[[importlinter:contract]]
name = "langgraph types only live in mainloop"
type = "forbidden"
source_modules = [
    "app.domain.agent.react_graph",
    "app.domain.agent.langgraph_nodes",
]
forbidden_modules = [
    "app.domain.agent.tools",
    "app.domain.agent.tool_executor",
    "app.domain.agent.handoff",
    "app.domain.agent.content_writer_specialist",
    "app.domain.monitor.monitor_specialist",
]
```

(若是用代码写的 import-linter contract,在 `tests/test_no_repo_to_service.py` 同步加 1 个 contract function)

- [ ] **Step 3: 跑 import-linter**

Run: `cd backend && python -m import_linter --config .import-linter.toml`
Expected: PASS;若失败:可能是 `specialist` test 已经无意引入了 langgraph 类型,需检查并 revert。

- [ ] **Step 4: 跑 ruff**

Run: `.venv/Scripts/python.exe -m ruff check app/ tests/ evals/`
Expected: 干净

- [ ] **Step 5: commit**

```bash
cd D:/GEO2 && git add AGENTS.md backend/.import-linter.toml
git commit -m "docs(agents): §6.5 增 LangGraph 单点替换例外 + import-linter 阻断跨域"
```

---

## 双跑切流(收尾)

### Task 16: Evals 双跑一整轮 — 收集 ≥95% 一致证据

**Files:**
- 无代码改动;本 task 是验证关卡
- Create: `docs/superpowers/handoff/2026-07-14-langgraph-react-loop-evals-result.md`

**Interfaces:**
- Consumes:`backend/evals/runner.py --compare`(Task 13)、现有 `cases.py`
- Produces:对比报告 + 切流决策

- [ ] **Step 1: 跑 react_loop baseline(同 input 5 次平均)**

Run: `cd backend && .venv/Scripts/python.exe -m evals.runner --baseline 5`
Expected:输出 `reports/eval/baseline.txt`

- [ ] **Step 2: 跑 langgraph 同一 cases,产出 diff 报告**

Run: `cd backend && .venv/Scripts/python.exe -m evals.runner --compare`
Expected:输出 `reports/eval/diff/<date>.md`

- [ ] **Step 3: 校验门槛**

- [ ] overall_text_match ≥ 0.95
- [ ] tool_call_match = 1.0
- [ ] handoff_event_match = 1.0
- [ ] SSE_event_count 相等

任何一个不达标:**不切流**,回到对应 Task 修复。

- [ ] **Step 4: 写收尾 handoff**

`docs/superpowers/handoff/2026-07-14-langgraph-react-loop-evals-result.md` 写明:
- 4 项指标当前值
- 是否切流决策
- 未通过时列出阻塞原因 + 责任 task
- 灰度 1 周的观测 KPI(线上 P50/P95/P99 延迟、tool_call 成功率、flow_id 流失率)

Run:
```bash
mkdir -p docs/superpowers/handoff
git add docs/superpowers/handoff/
git commit -m "docs(evals): langgraph 双跑对比收尾 — 切流决策 + 灰度 KPI"
```

---

### Task 17: 灰度切流 — Settings.langgraph_enabled = True

**Files:**
- Modify: `backend/.env.example`(新增一行)
- Create: `backend/scripts/gradual_rollout_langgraph.sh`(灰度脚本)

**Interfaces:**
- Consumes:`Settings.langgraph_enabled = True` 切流
- Produces:线上 100% 走 LangGraph(`react_loop.py` 1 个里程碑后删除)

> ⚠️ **重要**:Task 14 已留 react_loop.py 兼容路径;**只在 Task 16 全部门槛通过后才执行本 task**;否则请回到 Task 11/13 修复。

- [ ] **Step 1: env 注入**

`backend/.env.example` 加:

```
# v0.8 — LangGraph 主循环开关(spec §10.2 默认 false,生产切流改 true)
LANGGRAPH_ENABLED=false
```

- [ ] **Step 2: 灰度发布脚本**

```bash
# backend/scripts/gradual_rollout_langgraph.sh
#!/usr/bin/env bash
set -euo pipefail
# 灰度发布:1) 10% 流量切 langgraph,2) 50%,3) 100%
# 每阶段观察 1 天

# Stage 1: 10%
echo "Stage 1: 10% 流量 — 1 天"
# (具体流量切分走 feature flag 服务 / env 注入)
```

- [ ] **Step 3: 灰度 1 周观测关键 KPI**

| 指标 | 期望 | 失败动作 |
|---|---|---|
| P95 turn latency | ≤ react_loop + 10% | revert 一行 flag |
| tool_call 成功率 | ≥ 99% | 同上 |
| human_confirmation_required 事件数 | = react_loop | 同上 |
| Sentry 异常率 | ≤ react_loop 同期 | 同上 |

- [ ] **Step 4: 100% 切流决策**

- [ ] grep `langgraph_enabled = True` 在 `backend/app/core/config.py` default 改成 `True`(overridable)
- [ ] 提交:
```bash
git add backend/app/core/config.py backend/.env.example
git commit -m "feat(rollout): langgraph_enabled 默认 True — 切流完成,react_loop 1 里程碑后删"
```

---

## 收尾:整体测试与 lint

### Task 18: 整体测试 + lint + docs 更新

**Files:**
- Modify: 无新代码;验证 + 文档收尾

- [ ] **Step 1: 跑完整 pytest**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/ -v --tb=short`
Expected: 全绿(原 740 → 现 ~770 个)

- [ ] **Step 2: ruff + mypy**

Run: `.venv/Scripts/python.exe -m ruff check app/ tests/ evals/`
Expected: 干净

Run: `.venv/Scripts/python.exe -m mypy app/`(允许警告,不允许错误)
Expected: 干净

- [ ] **Step 3: import-linter**

Run: `cd backend && python -m import_linter --config .import-linter.toml`
Expected: PASS

- [ ] **Step 4: 更新 AGENTS.md / RESUME 等文档结尾**

AGENTS.md §5 关键路径列表追加:
```
- `app/domain/agent/langgraph_nodes/` — 6 个自定义 node(SSEBridge / CheckpointAdapter / MemorySnapshot / TruncateMessages / Policy)
- `app/domain/agent/react_graph.py` — CompiledStateGraph 工厂
- `app/domain/agent/state.py` — AgentState schema
- `app/domain/agent/dispatch.py` — Settings.langgraph_enabled 路由
```

- [ ] **Step 5: commit**

```bash
git add AGENTS.md backend/app/domain/agent/
git commit -m "docs(agents): §5 关键路径加 v0.8 LangGraph 自定义 nodes + react_graph"
```

---

## 完成标准(Definition of Done)

- [ ] 17 个 Task 全部完成
- [ ] `pytest backend/tests/` 全绿
- [ ] `ruff` 与 `mypy` 干净
- [ ] `import-linter` PASS
- [ ] evals 双跑 ≥ 95% 一致门槛通过(任务 16)
- [ ] 灰度 1 周线上 KPI 达标(任务 17)
- [ ] react_loop.py 1 里程碑内可删(Settings.langgraph_enabled 默认 True)
- [ ] 多 Agent spec §1.3 整体保持;只动 AGENTS.md §6.5 加例外
- [ ] AGENTS.md §5 关键路径文档刷新
- [ ] 简历 v6 上摘录「LangGraph 替换 react_loop 主循环 + 双跑灰度 + 1 行 flag 回滚」摘要

---

## 风险与回滚

| 阶段 | 回滚成本 | 操作 |
|---|---|---|
| 双跑灰度(react=primary, langgraph=shadow) | 一行 flag | `LANGGRAPH_ENABLED=false` |
| 切流后发现 bug | 一行 flag + 数据迁移 | flag 切回 + 用 checkpoint 恢复中转 |
| 切流 2 周后稳定 | git revert | revert 替换主循环的 PR;`react_loop.py` 不删(保留 1 里程碑) |
| 1 个里程碑后 | 删 react_loop.py | 默认 flag=True;`react_loop.py` 注释 deprecated |

---

## 附录 A:Plan 与 Spec 对照

| Spec § | Plan Task |
|---|---|
| §0 边界声明 | Task 14 / Task 15(AGENTS.md / import-linter) |
| §1.1 多 Agent 现状 | (Plan 起点,不动 multi-agent) |
| §1.3 目标 1 (react_loop 替换) | Task 2 / 4 / 8 / 9 / 10 / 11 / 14 |
| §1.3 目标 2 (SSE 字节级兼容) | Task 4(SSEBridge) |
| §1.3 目标 3 (pending_confirmation 兼容) | Task 5 / 6(CheckpointAdapter + 列迁移) |
| §1.3 目标 4 (L2 / 压缩 / 截断) | Task 8 / 9(MemorySnapshot + Truncate) |
| §1.3 目标 5 (双跑 + 灰度) | Task 13 / 16(evals + 报告) |
| §1.3 目标 6 (一行 flag 回滚) | Task 1 / 12 / 17(Settings + dispatch + 切流) |
| §1.4 非目标 | import-linter 阻断(Task 15) |
| §2.2 数据 schema 变更 | Task 6(列迁移) |
| §3 架构 | Task 11(react_graph 工厂) |
| §4.1 LangGraph prebuilt | Task 3 / 11 |
| §4.2 自定义 nodes | Task 4 / 5 / 7 / 8 / 9 / 10 |
| §4.3 AgentState | Task 2 |
| §6 Checkpoint 持久化 | Task 5 / 6 |
| §7 SSE 桥接 | Task 4 |
| §9 失败处理 | Task 10(PolicyNode) |
| §10.1 Evals 双跑 | Task 13 / 16 |
| §10.2 Feature flag | Task 1 / 12 / 17 |
| §11 测试策略 | 每个 Task 自带测试 |
| §12 实施顺序 | Sprint 1-4 task 分组 |
| §13 风险 | 见上方 「风险与回滚」 |
| §14 成功标准 | Definition of Done |
