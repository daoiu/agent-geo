# Phase 1 循环收敛 + 埋点 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `react_loop.py` 两个入口的重复 ReAct 循环体抽成单一 `_drive_react_loop`，并让 `LLMClient` 透出 token usage、每轮 turn 打一行 metrics 日志。

**Architecture:** 两个入口（`run_agent_turn` / `run_agent_turn_from_checkpoint`）各自保留"起点差异"，产出统一的 `history` 后委托给共享的 `_drive_react_loop` 异步生成器。`chat_with_tools` 返回值新增 `usage` 字段；共享循环累计 token 与调用次数，在三个出口（turn_complete / max_iterations_reached / human_confirmation）打 `agent_turn_metrics` structlog 日志。严格行为等价，除 usage 字段与日志外无可观测行为变化。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy async / structlog / pytest + pytest-asyncio / unittest.mock

## Global Constraints

- **严格行为等价**：除"`chat_with_tools` 返回加 `usage` 字段" + "每轮 turn 三出口打一行 `agent_turn_metrics` 日志"两处加法外，不改任何可观测行为（DB 落库时机、SSE 事件序列、HumanConfirmation 暂停语义全部不变）。
- **不动 DB schema、不改 SSE 协议、无前端变更。**
- **循环读 usage 一律用 `response.get("usage")`**，不用 `response["usage"]`——现有测试的 mock 返回 dict 不含该键，下标访问会 KeyError 破坏回归。
- **provider 不返回 usage 时记 `None`**，不引 tiktoken 估算；区分"未知"（None）与"0 tokens"。
- **`simple_chat` 签名不变**（仍返回 `str`），仅内部 log usage，改造押后 Phase 2。
- **验收 oracle = 现有 442 后端单测全绿**，尤其 `test_react_loop.py` 的 `build_messages` 配对用例与 `TestRunAgentTurnFromCheckpoint`。
- 重构中若发现潜在 bug / 坏味，**只记录不修**（登记到 spec §10），保持本 Phase 严格等价。

---

### Task 1: LLMClient 透出 token usage

**Files:**
- Modify: `backend/app/domain/llm_client.py`（新增 `_extract_usage`；`chat_with_tools` 返回加 `usage`；`simple_chat` 内部 log usage）
- Test: `backend/tests/test_llm_client_usage.py`（新建）

**Interfaces:**
- Produces:
  - `_extract_usage(response) -> dict | None` — 有 `response.usage` 时返回 `{"prompt_tokens": int|None, "completion_tokens": int|None, "total_tokens": int|None}`，否则 `None`
  - `chat_with_tools(messages, tools) -> dict` 返回值新增 key `"usage": dict | None`（原有 `content` / `tool_calls` 不变）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_llm_client_usage.py`：

```python
"""Tests for LLMClient usage passthrough (Phase 1)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from app.core.config import Settings
from app.domain.llm_client import LLMClient, _extract_usage


def _make_response(content, tool_calls, usage):
    """Mock openai response;usage 显式设置(AsyncMock 会自动造子 mock,故必须显式赋值)。"""
    choice = mock.AsyncMock()
    choice.message.content = content
    choice.message.tool_calls = tool_calls
    response = mock.AsyncMock()
    response.choices = [choice]
    response.usage = usage
    return response


@pytest.fixture(autouse=True)
def _isolate_provider_env(monkeypatch):
    from app.domain import llm_client as lc
    monkeypatch.setattr(lc, "_load_env_values", lambda: {
        "DEEPSEEK_API_KEY": "sk-test",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
        "DEEPSEEK_MODEL": "deepseek-chat",
    })


@pytest.fixture
def llm():
    return LLMClient(Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        llm_call_timeout_s=10,
    ))


def test_extract_usage_none_when_absent():
    assert _extract_usage(SimpleNamespace(usage=None)) is None
    assert _extract_usage(SimpleNamespace()) is None


def test_extract_usage_reads_three_fields():
    resp = SimpleNamespace(usage=SimpleNamespace(
        prompt_tokens=10, completion_tokens=5, total_tokens=15))
    assert _extract_usage(resp) == {
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


@pytest.mark.asyncio
async def test_chat_with_tools_returns_usage(llm):
    response = _make_response("ok", None, SimpleNamespace(
        prompt_tokens=100, completion_tokens=20, total_tokens=120))
    with mock.patch("app.domain.llm_client.AsyncOpenAI",
                    return_value=mock.AsyncMock()) as mock_cls:
        mock_cls.return_value.chat.completions.create = mock.AsyncMock(
            return_value=response)
        result = await llm.chat_with_tools(
            messages=[{"role": "user", "content": "hi"}], tools=[])
    assert result["usage"] == {
        "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}


@pytest.mark.asyncio
async def test_chat_with_tools_usage_none_when_provider_omits(llm):
    response = _make_response("ok", None, None)
    with mock.patch("app.domain.llm_client.AsyncOpenAI",
                    return_value=mock.AsyncMock()) as mock_cls:
        mock_cls.return_value.chat.completions.create = mock.AsyncMock(
            return_value=response)
        result = await llm.chat_with_tools(
            messages=[{"role": "user", "content": "hi"}], tools=[])
    assert result["usage"] is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_llm_client_usage.py -v`
Expected: FAIL —— `ImportError: cannot import name '_extract_usage'`

- [ ] **Step 3: 实现 `_extract_usage` + 接入 `chat_with_tools`**

在 `backend/app/domain/llm_client.py` 模块级（`class LLMClient` 之前）加：

```python
def _extract_usage(response) -> dict | None:
    """从 OpenAI 兼容响应提取 token usage;provider 不返回时 None。"""
    u = getattr(response, "usage", None)
    if u is None:
        return None
    return {
        "prompt_tokens": getattr(u, "prompt_tokens", None),
        "completion_tokens": getattr(u, "completion_tokens", None),
        "total_tokens": getattr(u, "total_tokens", None),
    }
```

改 `chat_with_tools` 的 return（原 `llm_client.py:297-300`）：

```python
        return {
            "content": message.content,
            "tool_calls": tool_calls,
            "usage": _extract_usage(response),
        }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_llm_client_usage.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: simple_chat 内部 log usage（签名不变）**

改 `simple_chat`（原 `llm_client.py:316-321`），保留 `return str`，仅加一行日志：

```python
        response = await client.chat.completions.create(
            model=cfg.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        logger.info("simple_chat_usage", usage=_extract_usage(response))
        return response.choices[0].message.content or ""
```

- [ ] **Step 6: 全量回归 + 提交**

Run: `cd backend && python -m pytest tests/test_llm_client_usage.py tests/test_llm_chat_with_tools.py tests/test_llm_client.py -v`
Expected: PASS（含既有 chat_with_tools 用例不回归）

```bash
git add backend/app/domain/llm_client.py backend/tests/test_llm_client_usage.py
git commit -m "feat(llm): chat_with_tools 透出 token usage + simple_chat 记录 usage"
```

---

### Task 2: 抽 `_drive_react_loop`（纯重构，行为等价）

**Files:**
- Modify: `backend/app/domain/agent/react_loop.py`（新增 `_drive_react_loop`；`run_agent_turn` 与 `run_agent_turn_from_checkpoint` 瘦身为委托）
- Test: 无新增；靠 `backend/tests/test_react_loop.py` 全绿当 oracle

**Interfaces:**
- Consumes: `chat_with_tools` 返回含 `usage`（Task 1，本任务用 `.get("usage")` 但暂不消费）
- Produces:
  - `_drive_react_loop(session_id: str, history: list[dict], device_id: str | None = None) -> AsyncIterator[dict]` — 共享 ReAct 循环体，产出与原循环逐事件一致的 SSE 事件流

- [ ] **Step 1: 先跑基线，确认现有循环测试全绿**

Run: `cd backend && python -m pytest tests/test_react_loop.py tests/test_react_loop_memory_integration.py -v`
Expected: PASS（记录通过数作为重构后对照基线）

- [ ] **Step 2: 新增 `_drive_react_loop`（从两处循环体提取的共享实现）**

在 `react_loop.py` 的 `_do_extract_after_turn` 之后、`run_agent_turn` 之前插入：

```python
async def _drive_react_loop(
    session_id: str,
    history: list[dict],
    device_id: str | None = None,
) -> AsyncIterator[dict]:
    """共享 ReAct 循环体。两入口做完各自起点差异后委托到此。

    产出的 SSE 事件流与收敛前逐事件等价。
    """
    settings = get_settings()
    llm = LLMClient(settings)
    factory = get_session_factory()
    scope = scope_key(device_id, session_id)

    async with factory() as session:
        memory_service = MemoryService(session)
        memory_index_segment = await memory_service.build_memory_segment(scope)
        memory_block = await memory_service.load_relevant_memories(scope, history)

    for _iteration in range(MAX_REACT_ITERATIONS):
        messages = build_messages(history, memory_index_segment=memory_index_segment)
        messages = _apply_memory_prepend(messages, memory_block)

        response = await llm.chat_with_tools(messages=messages, tools=TOOLS)
        content = response.get("content")
        tool_calls = response.get("tool_calls") or []

        tc_for_db = None
        if tool_calls:
            tc_for_db = [
                {
                    "id": tc["id"],
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": json.dumps(tc["function"]["arguments"])
                        if isinstance(tc["function"]["arguments"], dict)
                        else tc["function"]["arguments"],
                    },
                }
                for tc in tool_calls
            ]
        async with factory() as session:
            repo = AgentRepository(session)
            await repo.create_message(
                session_id=session_id, role="assistant",
                content=content, tool_calls=tc_for_db,
            )

        yield {"event": "assistant_message", "content": content or ""}

        if tool_calls:
            executor = ToolExecutor(session_id)
            for tool_call in tool_calls:
                tool_id = tool_call["id"]
                tool_name = tool_call["function"]["name"]
                tool_args = tool_call["function"]["arguments"]
                if isinstance(tool_args, str):
                    tool_args = json.loads(tool_args)

                yield {
                    "event": "tool_call_start",
                    "tool_call_id": tool_id,
                    "tool_name": tool_name,
                    "arguments": tool_args,
                }

                try:
                    result = await executor.execute(tool_name, tool_args)
                except Exception as exc:
                    from app.domain.exceptions import HumanConfirmationRequired

                    if isinstance(exc, HumanConfirmationRequired):
                        yield {
                            "event": "human_confirmation_required",
                            "message_id": exc.message_id,
                            "tool_name": exc.tool_name,
                            "arguments": exc.arguments,
                        }
                        return

                    err_payload = {"error": f"{type(exc).__name__}: {exc}"}
                    async with factory() as session:
                        repo = AgentRepository(session)
                        await repo.create_message(
                            session_id=session_id, role="tool",
                            content=json.dumps(err_payload, ensure_ascii=False),
                            tool_call_id=tool_id,
                        )
                    yield {
                        "event": "tool_call_result",
                        "tool_call_id": tool_id,
                        "result": err_payload,
                    }
                    continue

                async with factory() as session:
                    repo = AgentRepository(session)
                    await repo.create_message(
                        session_id=session_id, role="tool",
                        content=json.dumps(result, ensure_ascii=False),
                        tool_call_id=tool_id,
                    )
                yield {
                    "event": "tool_call_result",
                    "tool_call_id": tool_id,
                    "result": result,
                }

            async with factory() as session:
                repo = AgentRepository(session)
                history_rows = await repo.list_messages(session_id)
            history = [_orm_to_dict(m) for m in history_rows]
        else:
            task = asyncio.create_task(
                _do_extract_after_turn(device_id, session_id, history)
            )
            _PENDING_EXTRACTS.add(task)
            task.add_done_callback(_PENDING_EXTRACTS.discard)
            yield {"event": "turn_complete"}
            return

    yield {
        "event": "max_iterations_reached",
        "message": f"agent 达到最大推理步数 ({MAX_REACT_ITERATIONS})",
    }
```

> 注：原 `run_agent_turn` 里的 `should_continue` 是死变量（无处置为 False），提取时直接省略——行为等价。登记到 spec §10。

- [ ] **Step 3: `run_agent_turn` 瘦身为委托**

把 `run_agent_turn` 整个函数体（原 `react_loop.py:216-374`）替换为：

```python
async def run_agent_turn(
    session_id: str,
    user_message: str,
    device_id: str | None = None,
) -> AsyncIterator[dict]:
    """执行一轮 agent 推理 + 行动循环。流式 yield SSE 事件。

    起点差异:加载历史 → 保存 user 消息 → 委托共享循环。
    """
    factory = get_session_factory()
    async with factory() as session:
        repo = AgentRepository(session)
        history_rows = await repo.list_messages(session_id)
        await repo.create_message(
            session_id=session_id, role="user", content=user_message
        )
    history = [_orm_to_dict(m) for m in history_rows] + [
        {"role": "user", "content": user_message}
    ]
    async for evt in _drive_react_loop(session_id, history, device_id):
        yield evt
```

- [ ] **Step 4: `run_agent_turn_from_checkpoint` 瘦身为委托**

保留该函数从开头到"reload history"的起点差异部分（原 `react_loop.py:382-511` 不变），把其后的第二个 for 循环（原 `react_loop.py:513-625`：重算 memory + 循环 + 达上限 yield）整体替换为：

```python
    # 6. 继续 ReAct 循环（委托共享驱动，基于新 tool 结果继续决策）
    async with factory() as session:
        repo = AgentRepository(session)
        history_rows = await repo.list_messages(session_id)
    history = [_orm_to_dict(m) for m in history_rows]

    async for evt in _drive_react_loop(session_id, history, device_id):
        yield evt
```

> 删掉该函数内原先的 `llm = LLMClient(settings)`（第二循环自建）与 `scope` / memory 计算——已由 `_drive_react_loop` 内部承担。`settings` 若在起点差异段已不再使用可一并删。

- [ ] **Step 5: 全量回归确认行为等价**

Run: `cd backend && python -m pytest tests/test_react_loop.py tests/test_react_loop_memory_integration.py tests/test_api_agent_chat.py tests/test_e2e_v04.py -v`
Expected: PASS（与 Step 1 基线通过数一致）

- [ ] **Step 6: 提交**

```bash
git add backend/app/domain/agent/react_loop.py
git commit -m "refactor(agent): 抽共享 _drive_react_loop 消除两入口重复循环体"
```

---

### Task 3: 循环 metrics 埋点

**Files:**
- Modify: `backend/app/domain/agent/react_loop.py`（新增 `_new_metrics` / `_accumulate` / `_emit_metrics`；接入 `_drive_react_loop` 三出口）
- Test: `backend/tests/test_react_loop_metrics.py`（新建）

**Interfaces:**
- Consumes: `_drive_react_loop`（Task 2）；`chat_with_tools` 返回含 `usage`（Task 1）
- Produces:
  - `_new_metrics() -> dict`
  - `_accumulate(agg: dict, usage: dict | None) -> None`
  - `_emit_metrics(agg: dict, session_id: str, device_id: str | None, outcome: str) -> None` — 打 `logger.info("agent_turn_metrics", ...)`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_react_loop_metrics.py`：

```python
"""Tests for per-turn metrics logging in _drive_react_loop (Phase 1)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.agent_repo import AgentRepository


def _resp(content, tool_calls, usage):
    return {"content": content, "tool_calls": tool_calls, "usage": usage}


def _metrics_calls(mock_log):
    return [
        c for c in mock_log.call_args_list
        if c.args and c.args[0] == "agent_turn_metrics"
    ]


@pytest.mark.asyncio
async def test_metrics_logged_on_turn_complete(db_session):
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM, \
         patch.object(rl.logger, "info") as mock_log:
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value=_resp(
            "好的", None,
            {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        ))
        events = [e async for e in rl.run_agent_turn(session.id, "hi")]

    assert events[-1]["event"] == "turn_complete"
    calls = _metrics_calls(mock_log)
    assert len(calls) == 1
    kw = calls[0].kwargs
    assert kw["outcome"] == "turn_complete"
    assert kw["llm_calls"] == 1
    assert kw["total_tokens"] == 120


@pytest.mark.asyncio
async def test_metrics_token_none_when_usage_absent(db_session):
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM, \
         patch.object(rl.logger, "info") as mock_log:
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value=_resp(
            "好的", None, None))
        _ = [e async for e in rl.run_agent_turn(session.id, "hi")]

    kw = _metrics_calls(mock_log)[0].kwargs
    assert kw["total_tokens"] is None
    assert kw["prompt_tokens"] is None


@pytest.mark.asyncio
async def test_metrics_logged_on_max_iterations(db_session):
    repo = AgentRepository(db_session)
    session = await repo.create_session(title="T")

    import app.domain.agent.react_loop as rl
    tool_resp = _resp(None, [{
        "id": "tc",
        "function": {
            "name": "diagnose_brand",
            "arguments": '{"brand_name":"X","industry":"Y","official_url":"https://x.com"}',
        },
    }], {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

    with patch("app.domain.agent.react_loop.LLMClient") as MockLLM, \
         patch.object(rl.logger, "info") as mock_log, \
         patch("app.domain.agent.tool_executor.ToolExecutor.execute",
               new=AsyncMock(return_value={"x": 1})):
        MockLLM.return_value.chat_with_tools = AsyncMock(return_value=tool_resp)
        events = [e async for e in rl.run_agent_turn(session.id, "X")]

    assert events[-1]["event"] == "max_iterations_reached"
    kw = _metrics_calls(mock_log)[0].kwargs
    assert kw["outcome"] == "max_iterations_reached"
    assert kw["iterations"] == 7
    assert kw["tool_calls"] == 7
    assert kw["total_tokens"] == 105  # 7 × 15
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_react_loop_metrics.py -v`
Expected: FAIL —— 无 `agent_turn_metrics` 日志调用（`_metrics_calls` 空，断言失败）

- [ ] **Step 3: 实现 metrics 助手 + 接入三出口**

在 `react_loop.py` 的 `_do_extract_after_turn` 之后加三个助手：

```python
def _new_metrics() -> dict:
    return {
        "iterations": 0, "llm_calls": 0, "tool_calls": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "usage_seen": False,
    }


def _accumulate(agg: dict, usage: dict | None) -> None:
    agg["iterations"] += 1
    agg["llm_calls"] += 1
    if not usage:
        return
    agg["usage_seen"] = True
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        v = usage.get(k)
        if v is not None:
            agg[k] += v


def _emit_metrics(
    agg: dict, session_id: str, device_id: str | None, outcome: str
) -> None:
    logger.info(
        "agent_turn_metrics",
        session_id=session_id, device_id=device_id, outcome=outcome,
        iterations=agg["iterations"], llm_calls=agg["llm_calls"],
        tool_calls=agg["tool_calls"],
        prompt_tokens=agg["prompt_tokens"] if agg["usage_seen"] else None,
        completion_tokens=agg["completion_tokens"] if agg["usage_seen"] else None,
        total_tokens=agg["total_tokens"] if agg["usage_seen"] else None,
    )
```

改 `_drive_react_loop`：循环前建 `agg = _new_metrics()`；每次 `chat_with_tools` 后 `_accumulate`；工具执行成功/失败各 `agg["tool_calls"] += 1`；三出口前 `_emit_metrics`。具体：

在 `for _iteration in range(...)` 之前加：
```python
    agg = _new_metrics()
```

在 `response = await llm.chat_with_tools(...)` 之后、`content = ...` 之前加：
```python
        _accumulate(agg, response.get("usage"))
```

在工具子循环里，每个 tool 的 `yield tool_call_start` 之后加计数（异常路径与成功路径都已计入，故放在 start 后最稳）：
```python
                agg["tool_calls"] += 1
```

三处 yield 前加埋点：
```python
                    if isinstance(exc, HumanConfirmationRequired):
                        _emit_metrics(agg, session_id, device_id, "human_confirmation")
                        yield {
                            "event": "human_confirmation_required",
                            ...
                        }
                        return
```
```python
            _emit_metrics(agg, session_id, device_id, "turn_complete")
            yield {"event": "turn_complete"}
            return
```
```python
    _emit_metrics(agg, session_id, device_id, "max_iterations_reached")
    yield {
        "event": "max_iterations_reached",
        "message": f"agent 达到最大推理步数 ({MAX_REACT_ITERATIONS})",
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_react_loop_metrics.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 全量回归**

Run: `cd backend && python -m pytest -q`
Expected: PASS（全部通过，含 Task 1/2 新增，无回归）

- [ ] **Step 6: 提交**

```bash
git add backend/app/domain/agent/react_loop.py backend/tests/test_react_loop_metrics.py
git commit -m "feat(agent): 每轮 turn 三出口打 agent_turn_metrics 埋点日志"
```

---

## 自查（Self-Review）

**Spec 覆盖：**
- spec §2.3 共享驱动 → Task 2 ✓
- spec §3 埋点字段 → Task 3 `_emit_metrics` ✓
- spec §4 usage 透出 + 累计容错 → Task 1 `_extract_usage` + Task 3 `_accumulate` ✓
- spec §5.1 chat_with_tools 新返回 → Task 1 ✓
- spec §5.2 simple_chat 签名不变仅 log → Task 1 Step 5 ✓
- spec §8 错误处理（usage None / 部分缺失 / 三出口）→ Task 1 + Task 3 测试 ✓
- spec §9 测试矩阵 → Task 1（usage）+ Task 3（metrics）+ 各 Task 回归步骤 ✓
- spec §12 退出标准 → 各 Task Step「全量回归」+ 最终 `pytest -q` ✓

**类型一致性：** `_extract_usage` / `chat_with_tools["usage"]` / `_accumulate(agg, usage)` / `_drive_react_loop(session_id, history, device_id)` / `_emit_metrics(agg, session_id, device_id, outcome)` 跨任务命名与签名一致 ✓

**占位扫描：** 无 TBD / TODO；每个 code step 附完整代码 ✓
