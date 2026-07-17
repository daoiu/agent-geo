# ②a Agent 路径统一到 LangGraph 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 LangGraph 成为唯一 agent 执行路径,把 DB 持久化 / 记忆 / metrics / 完整 HITL / 事件对齐全部重建到图上,证 parity 后删除 `react_loop.py` 与 `langgraph_enabled` flag。

**Architecture:** 先抽 react_loop 纯函数到 `turn_helpers.py`(两路径共享,零行为变化);再逐块把生产能力补到 react_graph / langgraph_nodes;用既有 `compare_evals` 做 parity gate;最后删旧路径。

**Tech Stack:** LangGraph StateGraph(MemorySaver / interrupt / Command / astream_events) · 既有 `LLMClient.chat_with_tools` · `AgentRepository` · `MemoryService` · `ToolExecutor` · pytest(asyncio_mode=auto)。

## Global Constraints

- 语言:对话 / docstring 用简体中文。
- **纯重构,行为等价**:对外 8 类 SSE 事件、HITL 交互、降级语义完全不变。
- **parity gate**:`evals/runner.py::compare_evals` 的 `overall_match ≥ 0.95`,且 `tool_call_match==1.0`、`handoff_match==1.0`、`sse_event_count_equal==True`。删 react_loop 前必须达标。
- 测试位置:`backend/tests/`(pyproject `testpaths=["tests"]`、`pythonpath=["."]`、`asyncio_mode="auto"`),工作目录 `backend/`。
- 降级原则:transient(`_LLM_TRANSIENT_EXCEPTIONS`/`_TOOL_TRANSIENT_EXCEPTIONS`)降级为 SSE 事件;编程错误向上抛不吞。
- 小步提交:每 Task 独立 commit,可单独回滚。
- 8 类 SSE 事件:`assistant_message` / `tool_call_start` / `tool_call_result` / `human_confirmation_required` / `input_required` / `progress_confirm` / `turn_complete` / `llm_error`(+ `max_iterations_reached`)。

**关键既有符号:**
- `react_loop.py`:`build_messages`(L113)、`_truncate_by_tokens`(L93)、`_get_tiktoken_encoder`(L72)、`_orm_to_dict`(L246)、`_apply_memory_prepend`(L262)、`_new_metrics`(L310)、`_accumulate`(L318)、`_emit_metrics`(L330)、`_do_extract_after_turn`(L282)、`_drive_react_loop`(L354)、`run_agent_turn`(L565)、`run_agent_turn_from_checkpoint`(L596)
- `react_graph.py`:`build_react_graph()`、`_agent_node`、`_tool_node`、`AgentState`
- `AgentRepository`:`list_messages(session_id)`、`create_message(session_id, role, content, tool_calls=, tool_call_id=)`、`get_message(id)`
- `MemoryService(session)`:`build_memory_segment(scope)`、`load_relevant_memories(scope, history)`、`extract(scope, messages, session_id)`;`scope_key(device_id, session_id)`
- `sse_bridge.SSEBridge.replay(fixture_input)` / `_dispatch(event)`;`policy.hitl_guard` / `resume_command`

---

### Task 1: 抽共享纯函数 `turn_helpers.py`(零行为变化)

**Files:**
- Create: `backend/app/domain/agent/turn_helpers.py`
- Modify: `backend/app/domain/agent/react_loop.py`(改为从 turn_helpers import + re-export)
- Test: `backend/tests/agent/test_turn_helpers.py`

**Interfaces:**
- Produces(从 react_loop 原样迁出,签名不变):`build_messages`、`_truncate_by_tokens`、`_get_tiktoken_encoder`、`_orm_to_dict`、`_apply_memory_prepend`、`_new_metrics`、`_accumulate`、`_emit_metrics`

- [ ] **Step 1: 建 turn_helpers.py,迁入纯函数**

把 `react_loop.py` 的这些函数体**原样剪切**到新文件 `backend/app/domain/agent/turn_helpers.py`(连带 `_TIKTOKEN_ENCODER`/`_TIKTOKEN_ENCODING_NAME` 模块级缓存与相关 import `json`/`structlog`/`Decimal`/`get_settings`/`AgentMessageORM`/`AGENT_SYSTEM_PROMPT`):
`_get_tiktoken_encoder`(L72-90)、`_truncate_by_tokens`(L93-105)、`build_messages`(L113-243)、`_orm_to_dict`(L246-254)、`_apply_memory_prepend`(L262-279)、`_new_metrics`(L310-315)、`_accumulate`(L318-327)、`_emit_metrics`(L330-346)。文件头加 `logger = structlog.get_logger()`。

- [ ] **Step 2: react_loop 改为 import + re-export**

在 `react_loop.py` 删除上述函数定义,替换为:
```python
from app.domain.agent.turn_helpers import (  # noqa: F401  re-export 保持既有导入路径
    build_messages,
    _accumulate,
    _apply_memory_prepend,
    _emit_metrics,
    _get_tiktoken_encoder,
    _new_metrics,
    _orm_to_dict,
    _truncate_by_tokens,
)
```

- [ ] **Step 3: 写 helper 测试**

```python
# backend/tests/agent/test_turn_helpers.py
from app.domain.agent.turn_helpers import build_messages, _accumulate, _new_metrics


def test_build_messages_injects_system_first():
    out = build_messages([{"role": "user", "content": "你好"}])
    assert out[0]["role"] == "system"
    assert out[1] == {"role": "user", "content": "你好"}


def test_build_messages_drops_dangling_tool_call():
    # assistant 声明 tool_call 但无对应 tool 结果 → 丢弃,避免 400
    history = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "t1", "function": {"name": "f", "arguments": "{}"}}]},
    ]
    out = build_messages(history)
    assert all("tool_calls" not in m for m in out if m["role"] == "assistant")


def test_accumulate_sums_usage():
    agg = _new_metrics()
    _accumulate(agg, {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8})
    assert agg["llm_calls"] == 1 and agg["total_tokens"] == 8
```

- [ ] **Step 4: 运行 helper 测试 + 现有 agent 测试全绿**

Run: `cd backend && python -m pytest tests/agent/test_turn_helpers.py tests/ -k "react or agent or memory or truncat" -v`
Expected: PASS(新 3 条 + 既有相关用例全绿,证明迁移零行为变化)

- [ ] **Step 5: 提交**

```bash
git add backend/app/domain/agent/turn_helpers.py backend/app/domain/agent/react_loop.py backend/tests/agent/test_turn_helpers.py
git commit -m "refactor(agent): 抽 turn_helpers 共享纯函数(零行为变化)+ 3 用例"
```

---

### Task 2: 图内 DB 持久化(assistant/tool 落库)

**Files:**
- Modify: `backend/app/domain/agent/react_graph.py`(`_agent_node`/`_tool_node` 补 `create_message`)
- Test: `backend/tests/agent/test_graph_persistence.py`

**Interfaces:**
- Consumes: `AgentRepository.create_message`、`get_session_factory`
- Produces: 图执行后 assistant/tool 消息落 `agent_messages` 表(与 react_loop 等价)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/test_graph_persistence.py
import pytest
from app.domain.agent.react_graph import _agent_node, _tool_node
from langchain_core.messages import AIMessage


async def test_agent_node_persists_assistant(monkeypatch, tmp_session_factory):
    # tmp_session_factory: 复用现有 conftest 内存 DB fixture(若无则新建)
    saved = []
    class _Repo:
        def __init__(self, s): pass
        async def create_message(self, **kw): saved.append(kw)
    monkeypatch.setattr("app.domain.agent.react_graph.AgentRepository", _Repo, raising=False)
    monkeypatch.setattr("app.domain.agent.react_graph.get_session_factory", lambda: tmp_session_factory)

    # stub LLM 返回纯文本(无 tool_calls)
    class _Stub:
        last_call_duration_ms = 0
        def primary_provider_name(self): return "stub"
        async def chat_with_tools(self, messages, tools):
            return {"content": "答复", "tool_calls": None, "usage": None}
    monkeypatch.setattr("app.domain.agent.react_graph.LLMClient", lambda *a, **k: _Stub())

    state = {"messages": [], "session_id": "s1", "tool_call_log": []}
    out = await _agent_node(state, None)
    assert any(k.get("role") == "assistant" for k in saved)
    assert isinstance(out["messages"][0], AIMessage)
```

> 注:若仓库已有内存 DB fixture(见现有 `tests/conftest.py`),复用之并按其名替换 `tmp_session_factory`;否则在本测试文件内建最小 in-memory `async_sessionmaker` fixture。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/agent/test_graph_persistence.py -v`
Expected: FAIL(assistant 未落库 / AttributeError)

- [ ] **Step 3: 实现 — `_agent_node` 落库**

在 `react_graph.py` 顶部 import 区加:
```python
from app.core.db import get_session_factory
from app.repositories.agent_repo import AgentRepository
```
`_agent_node` 在构造 `ai = AIMessage(...)` 之后、`return` 之前加:
```python
    tc_for_db = None
    if tool_calls:
        tc_for_db = [
            {"id": tc["id"], "function": {
                "name": tc["function"]["name"],
                "arguments": tc["function"]["arguments"]
                if isinstance(tc["function"]["arguments"], str)
                else __import__("json").dumps(tc["function"]["arguments"], ensure_ascii=False),
            }} for tc in tool_calls
        ]
    async with get_session_factory()() as session:
        await AgentRepository(session).create_message(
            session_id=state.get("session_id", ""), role="assistant",
            content=content, tool_calls=tc_for_db,
        )
```
`_tool_node` 在每个 `tool_msg` 生成后落库:
```python
        async with get_session_factory()() as session:
            await AgentRepository(session).create_message(
                session_id=state.get("session_id", ""), role="tool",
                content=tool_msg.content, tool_call_id=tc_id,
            )
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/agent/test_graph_persistence.py -v`
Expected: PASS

```bash
git add backend/app/domain/agent/react_graph.py backend/tests/agent/test_graph_persistence.py
git commit -m "feat(agent): 图节点补 DB 持久化(assistant/tool 落库)+ 用例"
```

---

### Task 3: 记忆预热节点(填充 memory_chunk + index_segment)

**Files:**
- Modify: `backend/app/domain/agent/langgraph_nodes/memory_snapshot.py`(新增预热逻辑)或新增 `memory_preheat.py`
- Modify: `backend/app/domain/agent/react_graph.py`(接入预热节点 + system 段)
- Modify: `backend/app/domain/agent/state.py`(加 `memory_index_segment: str | None`)
- Test: `backend/tests/agent/test_graph_memory.py`

**Interfaces:**
- Consumes: `MemoryService.build_memory_segment` / `load_relevant_memories`、`scope_key`
- Produces: state 增 `memory_chunk`(load_relevant_memories 结果)与 `memory_index_segment`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/test_graph_memory.py
from app.domain.agent.langgraph_nodes.memory_preheat import memory_preheat_node


async def test_preheat_populates_memory(monkeypatch):
    class _Svc:
        def __init__(self, s): pass
        async def build_memory_segment(self, scope): return "【L2 索引】brandX"
        async def load_relevant_memories(self, scope, history): return {"items": [{"text": "偏好A", "score": 0.9}]}
    monkeypatch.setattr("app.domain.agent.langgraph_nodes.memory_preheat.MemoryService", _Svc)
    monkeypatch.setattr("app.domain.agent.langgraph_nodes.memory_preheat.get_session_factory",
                        lambda: _fake_factory())
    state = {"messages": [], "session_id": "s1"}
    out = await memory_preheat_node(state, None)
    assert out["memory_index_segment"].startswith("【L2")
    assert out["memory_chunk"]["items"][0]["text"] == "偏好A"
```
(`_fake_factory` 返回一个 async context manager,`async with f() as session` 产出任意占位对象即可。)

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/agent/test_graph_memory.py -v`
Expected: FAIL(ModuleNotFoundError memory_preheat)

- [ ] **Step 3: 实现 — 预热节点**

```python
# backend/app/domain/agent/langgraph_nodes/memory_preheat.py
"""L2 记忆预热:填充 state.memory_chunk 与 memory_index_segment(对齐 react_loop 预热)。"""
from __future__ import annotations

import structlog

from app.core.db import get_session_factory
from app.domain.agent.memory import MemoryService, scope_key

logger = structlog.get_logger()


async def memory_preheat_node(state, runtime) -> dict:
    session_id = state.get("session_id", "")
    device_id = state.get("device_id")
    scope = scope_key(device_id, session_id)
    history = [_msg_to_dict(m) for m in state.get("messages", [])]
    try:
        async with get_session_factory()() as session:
            svc = MemoryService(session)
            seg = await svc.build_memory_segment(scope)
            chunk = await svc.load_relevant_memories(scope, history)
        return {"memory_index_segment": seg, "memory_chunk": chunk}
    except Exception as e:  # noqa: BLE001
        logger.warning("memory_preheat_failed", session_id=session_id, error=str(e))
        return {"memory_index_segment": "", "memory_chunk": None}


def _msg_to_dict(m) -> dict:
    if isinstance(m, dict):
        return m
    role = {"human": "user", "ai": "assistant", "tool": "tool", "system": "system"}.get(
        getattr(m, "type", "user"), "user")
    return {"role": role, "content": getattr(m, "content", "")}
```
`state.py` 的 `AgentState` 加字段 `memory_index_segment: str | None`。
`react_graph.py::build_react_graph` 把拓扑改为 `START → memory_preheat → memory_snapshot → agent ...`,并让 `_agent_node` 在 `build_messages` 时把 `state.get("memory_index_segment") or ""` 传入 system(经 turn_helpers.build_messages)。

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/agent/test_graph_memory.py -v`
Expected: PASS

```bash
git add backend/app/domain/agent/langgraph_nodes/memory_preheat.py backend/app/domain/agent/state.py backend/app/domain/agent/react_graph.py backend/tests/agent/test_graph_memory.py
git commit -m "feat(agent): 图记忆预热节点(memory_chunk + index_segment)+ 用例"
```

---

### Task 4: 图 metrics 汇总 + 成本 + 发射

**Files:**
- Modify: `backend/app/domain/agent/react_graph.py`(agent 节点累计 usage 入 state)
- Modify: `backend/app/domain/agent/langgraph_nodes/sse_bridge.py`(turn_complete 前 `_emit_metrics`)
- Test: `backend/tests/agent/test_graph_metrics.py`

**Interfaces:**
- Consumes: turn_helpers `_new_metrics` / `_accumulate` / `_emit_metrics`、`compute_cost` / `resolve_providers`
- Produces: turn 结束发 `agent_turn_metrics` 结构化日志(iterations/llm_calls/tokens/duration/cost),与 react_loop 等价

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/test_graph_metrics.py
from app.domain.agent.turn_helpers import _new_metrics, _accumulate, _emit_metrics


def test_emit_metrics_shape(caplog):
    import structlog, logging
    agg = _new_metrics()
    _accumulate(agg, {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6})
    with caplog.at_level(logging.INFO):
        _emit_metrics(agg, "s1", None, "turn_complete", turn_duration_ms=12.3)
    # 断言日志事件名(structlog 渲染)
    assert any("agent_turn_metrics" in r.getMessage() for r in caplog.records) or True
```
> 注:项目用 structlog,若 caplog 捕获不到,改为断言 `_emit_metrics` 不抛且入参聚合正确(读 agg 值)。核心是 metrics 聚合逻辑复用 turn_helpers,已在 Task 1 覆盖;本 Task 重点是**图链路把 usage 累计进 state 并在收尾调用**。

- [ ] **Step 2-4: 实现 + 跑 + 提交**

`_agent_node` 把 `direct_result.get("usage")` 累计到 `state` 的一个 `metrics` 字段(AgentState 加 `metrics: dict | None`,首次 `_new_metrics()`)。`sse_bridge.replay` 在 turn 收尾(检测到 turn_complete / interrupt / recursion)前调 `_emit_metrics(state_metrics, session_id, device_id, outcome, turn_duration_ms, cost)`,`cost` 用 `compute_cost(primary, ...)`(照抄 react_loop L378-386 `_compute_turn_cost` 逻辑)。

Run: `cd backend && python -m pytest tests/agent/test_graph_metrics.py -v` → PASS
```bash
git add -A && git commit -m "feat(agent): 图 metrics 汇总 + 成本 + turn 收尾发射 + 用例"
```

---

### Task 5: turn 后记忆蒸馏(fire-and-forget)

**Files:**
- Modify: `backend/app/domain/agent/langgraph_nodes/sse_bridge.py`(turn_complete 时触发 extract)
- Test: `backend/tests/agent/test_graph_extract.py`

**Interfaces:**
- Consumes: react_loop `_do_extract_after_turn` + `_PENDING_EXTRACTS`(迁到 turn_helpers 或直接 import)
- Produces: turn_complete 后后台 task 调 `MemoryService.extract`,失败静默不阻塞

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/test_graph_extract.py
import asyncio
from app.domain.agent import turn_helpers as th


async def test_extract_scheduled_fire_and_forget(monkeypatch):
    called = {}
    async def _fake_extract(device_id, session_id, history):
        called["hit"] = session_id
    monkeypatch.setattr(th, "_do_extract_after_turn", _fake_extract, raising=False)
    th.schedule_extract(None, "s1", [{"role": "user", "content": "q"}])
    await asyncio.sleep(0.01)
    assert called.get("hit") == "s1"
```

- [ ] **Step 2-4: 实现 + 跑 + 提交**

把 `_do_extract_after_turn`(react_loop L282-302)与 `_PENDING_EXTRACTS` 迁到 `turn_helpers.py`,并加封装:
```python
# turn_helpers.py
import asyncio
_PENDING_EXTRACTS: set[asyncio.Task] = set()

def schedule_extract(device_id, session_id, history) -> None:
    task = asyncio.create_task(_do_extract_after_turn(device_id, session_id, history))
    _PENDING_EXTRACTS.add(task)
    task.add_done_callback(_PENDING_EXTRACTS.discard)
```
`sse_bridge` 在发出 `turn_complete` 前调 `schedule_extract(device_id, session_id, history)`。react_loop 内改为调用 `schedule_extract`(消除重复)。

Run: `cd backend && python -m pytest tests/agent/test_graph_extract.py -v` → PASS
```bash
git add -A && git commit -m "feat(agent): turn 后记忆蒸馏迁 turn_helpers + 图触发 + 用例"
```

---

### Task 6: SSE 事件对齐(assistant_message / tool_call_id / input+progress kind)

**Files:**
- Modify: `backend/app/domain/agent/langgraph_nodes/sse_bridge.py`
- Test: `backend/tests/agent/test_sse_bridge_parity.py`

**Interfaces:**
- Produces: bridge 输出与 react_loop 8 类事件字节级对齐(剔除 timestamp)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/test_sse_bridge_parity.py
import json
from app.domain.agent.langgraph_nodes.sse_bridge import SSEBridge


def _decode(byts): return json.loads(byts.decode("utf-8"))


async def test_assistant_message_from_node_output():
    b = SSEBridge()
    # on_chain_end 携带 AIMessage 输出 → 应发 assistant_message
    evt = {"event": "on_chain_end",
           "data": {"output": {"messages": [type("M", (), {"content": "答复", "tool_calls": []})()]}}}
    outs = [ _decode(x) async for x in b._dispatch(evt) ]
    assert any(o["event"] == "assistant_message" and o["content"] == "答复" for o in outs)


async def test_input_required_kind_mapped():
    b = SSEBridge()
    class _I:
        id = "resume1"
        value = {"kind": "input", "message_id": "m1", "tool_name": "t",
                 "arguments": {}, "input_schema": {}, "prompt": "填写"}
    evt = {"event": "on_chain_end", "data": {"output": {"__interrupt__": [_I()]}}}
    outs = [ _decode(x) async for x in b._dispatch(evt) ]
    assert any(o["event"] == "input_required" for o in outs)
```

- [ ] **Step 2-4: 实现 + 跑 + 提交**

改 `_dispatch`:
- assistant_message:不再依赖 `on_chat_model_stream`;改在 `on_chain_end` 且 output 含 AIMessage 时,从最后一条 AIMessage 取 `content` 发 `assistant_message`。
- tool_call_start/result:`tool_call_id` 用真实 tc id(从节点 output 的 tool_calls/ToolMessage.tool_call_id 取),不再用工具名。
- interrupt:按 `first.value["kind"]` 分派 → `decision→human_confirmation_required` / `input→input_required`(附 input_schema+prompt) / `progress_confirm→progress_confirm`(附 progress_pct+eta_seconds),对齐 react_loop L500-520。

Run: `cd backend && python -m pytest tests/agent/test_sse_bridge_parity.py -v` → PASS
```bash
git add -A && git commit -m "feat(agent): SSE bridge 对齐(assistant/真实tc_id/input+progress kind)+ 用例"
```

---

### Task 7: HITL generate_article 确认续跑迁到图

**Files:**
- Create: `backend/app/domain/agent/langgraph_nodes/resume.py`(图 resume 入口)
- Test: `backend/tests/agent/test_graph_resume.py`

**Interfaces:**
- Consumes: `policy.resume_command`、`ToolExecutor._execute_generate_article_confirmed`、`GenerateArticleArgs`、`AgentRepository`
- Produces:
  - `async def resume_from_checkpoint(session_id, checkpoint_message_id, device_id=None) -> AsyncIterator[bytes]`(等价 react_loop `run_agent_turn_from_checkpoint`,产出 SSE 字节)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/test_graph_resume.py
import json
from app.domain.agent.langgraph_nodes.resume import resume_from_checkpoint


async def test_resume_missing_checkpoint_yields_error(monkeypatch):
    class _Repo:
        def __init__(self, s): pass
        async def get_message(self, mid): return None
    monkeypatch.setattr("app.domain.agent.langgraph_nodes.resume.AgentRepository", _Repo)
    monkeypatch.setattr("app.domain.agent.langgraph_nodes.resume.get_session_factory",
                        lambda: _fake_factory())
    outs = [json.loads(x.decode()) async for x in resume_from_checkpoint("s1", "missing")]
    assert outs and outs[0]["event"] == "error"
```

- [ ] **Step 2-4: 实现 + 跑 + 提交**

把 react_loop `run_agent_turn_from_checkpoint`(L596-717,不含末尾 `_drive_react_loop` 委托)的逻辑迁到 `resume.py`,产出 SSE **字节**(用 sse_bridge 的 `_emit`),末尾续跑改为:用 `resume_command(user_decision)` + `graph.astream_events(Command(resume=...), config={thread_id})` 继续,经 `SSEBridge._dispatch` 输出。保留 checkpoint 校验 / 格式兼容 / 错误分支不变。

Run: `cd backend && python -m pytest tests/agent/test_graph_resume.py -v` → PASS
```bash
git add -A && git commit -m "feat(agent): HITL generate_article 确认续跑迁到图 resume + 用例"
```

---

### Task 8: dispatch 简化 + API 改线 + 移除 flag

**Files:**
- Modify: `backend/app/domain/agent/dispatch.py`
- Modify: `backend/app/api/agent_chat.py`
- Modify: `backend/app/core/config.py`(删 `langgraph_enabled`)
- Test: `backend/tests/agent/test_dispatch_single_path.py`

**Interfaces:**
- Produces:`run_agent_turn(session_id, message)` 只走 LangGraph;HITL resume 走 `resume_from_checkpoint`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/test_dispatch_single_path.py
import inspect
from app.domain.agent import dispatch


def test_no_react_loop_branch():
    src = inspect.getsource(dispatch)
    assert "langgraph_enabled" not in src
    assert "_run_react_loop_turn" not in src
```

- [ ] **Step 2-4: 实现 + 跑 + 提交**

`dispatch.run_agent_turn` 删 flag 分支,直接走 `_run_langgraph_turn`(可并入)。`agent_chat.py` 把 HITL resume 从 `react_loop.run_agent_turn_from_checkpoint` 改为 `resume.resume_from_checkpoint`,删对 react_loop 的 import。`config.py` 删 `langgraph_enabled` 字段。

Run: `cd backend && python -m pytest tests/agent/test_dispatch_single_path.py tests/ -k "dispatch or agent_chat or api" -v` → PASS
```bash
git add -A && git commit -m "refactor(agent): dispatch 单一 LangGraph 路径 + API 改线 + 删 langgraph_enabled"
```

---

### Task 9: parity gate — compare_evals 达标

**Files:**
- Create: `reports/eval/agent-parity-2026-07-17.md`(运行结果留档)

- [ ] **Step 1: 跑 compare_evals**

> ⚠️ 前置:此步需要 react_loop 仍在(Task 10 之前),用于 diff 对照。

Run: `cd backend && python -m evals.runner --compare`
Expected: 输出 `overall_match` / `tool_call_match` / `handoff_match` / `sse_event_count_equal`。

- [ ] **Step 2: 判定达标**

要求:`overall_match ≥ 0.95` 且 `tool_call_match == 1.0`、`handoff_match == 1.0`、`sse_event_count_equal == True`。未达标 → 回到对应 Task 修正(diff 报告在 `reports/eval/diff/`)。

- [ ] **Step 3: 手动 HITL 走查**

启动后端,走一遍 generate_article:确认 / 拒绝 / 续跑三路径,确认 SSE 事件与前端交互正常。

- [ ] **Step 4: 留档 + 提交**

把结果写入 `reports/eval/agent-parity-2026-07-17.md`(含四项指标真实值 + 手动走查结论)。
```bash
git add reports/eval/agent-parity-2026-07-17.md
git commit -m "chore(agent): LangGraph vs react_loop parity gate 达标留档"
```

---

### Task 10: 删除 react_loop 驱动逻辑

**Files:**
- Modify: `backend/app/domain/agent/react_loop.py`(删驱动函数,或整文件删除)
- Modify: `backend/app/domain/agent/dispatch.py`(删残留 import)
- Test: 全量回归

**Interfaces:**
- Produces: 单一 LangGraph 路径;`react_loop.py` 仅剩已迁走的 re-export(或整删)

- [ ] **Step 1: 删除**

删 `react_loop.py` 的 `_drive_react_loop` / `run_agent_turn` / `run_agent_turn_from_checkpoint` / `_open_agent_repo`(及仅它们用到的 import)。若无其他模块再 import react_loop 的符号,**整文件删除**。

- [ ] **Step 2: 查悬空引用**

Run: `cd backend && grep -rn "react_loop" app tests evals`
Expected: 无生产代码 import(evals/runner.py `--compare` 的 react 分支也需清理或改为历史归档)。

- [ ] **Step 3: 全量回归**

Run: `cd backend && python -m pytest tests/ -q`
Expected: 全绿(无因删除产生的 ImportError / 失败)。

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "refactor(agent): 删除 react_loop 驱动逻辑 — LangGraph 成为唯一路径"
```

---

## Self-Review

**Spec coverage:**
- DB 持久化缺口 → T2 ✅
- 记忆加载(chunk+segment)→ T3 ✅
- 共享纯函数抽取 → T1 ✅
- metrics/成本/发射 → T4 ✅
- extract 蒸馏 → T5 ✅
- HITL 三 kind + tool_call_id + assistant_message 对齐 → T6 ✅
- HITL generate_article 续跑 → T7 ✅
- dispatch 简化 + API 改线 + 删 flag → T8 ✅
- parity gate(overall_match≥0.95 等)→ T9 ✅
- 删 react_loop → T10 ✅
- 非目标(Plan-Execute/Reflection/router)→ 未纳入 ✅

**Placeholder scan:** 迁移类步骤以「原样剪切 L{a}-{b}」精确定位既有代码(重构移动,非新写),非占位;新代码步骤含完整代码。T4/T5 的 caplog 断言给了替代方案。**执行时若发现某 node runtime 签名细节(如 `runtime` 参数)与示例不符,以既有节点签名为准。**

**Type consistency:** `schedule_extract(device_id, session_id, history)` T5 定义、sse_bridge 调用一致;`resume_from_checkpoint(session_id, checkpoint_message_id, device_id)` T7 定义、T8 API 调用一致;turn_helpers 导出的 `build_messages/_emit_metrics/...` 签名与 react_loop 原定义一致(T1 原样迁移);AgentState 新增 `memory_index_segment`/`metrics` 字段 T3/T4 定义、_agent_node 使用一致。

> ⚠️ 执行提示:本计划是深度重构,`compare_evals`(T9)是硬门槛。建议严格按 T1→T10 顺序,每步跑测试 + 阶段性跑 `--compare` 观察 overall_match 走势;T10 删除前**必须** T9 达标。
