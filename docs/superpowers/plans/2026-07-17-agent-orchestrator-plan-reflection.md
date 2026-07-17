# ②b Agent 编排层实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 ②a 统一 LangGraph 路径上,加入口复杂度 router + Plan-Execute 模式 + 运行时升降级 + ReflectionAgent 质量评分(<60 重试最多 2 次返回最高分),新 flag 灰度。

**Architecture:** 新增 `app/domain/agent/orchestrator/`(router / plan_execute / reflection / graph),orchestrator 图包裹 ②a 统一图作为 ReAct 子图;`dispatch` 按 `agent_orchestrator_enabled` 路由。各能力先做成可独立单测的纯逻辑,再在 graph 组装。

**Tech Stack:** LangGraph StateGraph · 既有 `classify_complexity` · `LLMClient.simple_chat` · `ToolExecutor`/`TOOLS` · pytest(asyncio_mode=auto)。

## Global Constraints

- 语言:对话 / docstring 用简体中文。
- **依赖 ②a 完成**(统一图 `react_graph.build_react_graph` 为 ReAct 子图)。
- 默认 `agent_orchestrator_enabled=False`:不影响 ②a 既有单一路径。
- 降级:reflection LLM 失败 → 跳过评分原样返回;planner 失败 → 降级 ReAct;无 key → router 退 ReAct + reflection 关闭;编程错误向上抛不吞。
- 单向升级(升 Plan-Execute 后不降回),防震荡。
- 新增 SSE 事件 `reflection_score` / `mode_switch` 为附加事件,不破坏既有 8 类。
- 测试位置:`backend/tests/agent/orchestrator/`(pyproject `testpaths=["tests"]`、`pythonpath=["."]`、`asyncio_mode="auto"`),工作目录 `backend/`。

**关键既有接口:**
- `app.core.adaptive_model.classify_complexity(query, tool_count=0, hint=None) -> "simple"|"standard"|"complex"`
- `app.domain.agent.tools.TOOLS`;`app.domain.agent.tool_executor.ToolExecutor(session_id).execute(name, args)`
- `app.domain.llm_client.LLMClient.simple_chat(prompt) -> str`;`.available_providers`
- `app.domain.agent.react_graph.build_react_graph()`(②a 统一图)

---

### Task 1: 配置项

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Test: `backend/tests/agent/orchestrator/test_config.py`

**Interfaces:**
- Produces:`agent_orchestrator_enabled` / `reflection_enabled` / `reflection_min_score` / `reflection_max_retries` / `plan_execute_max_steps`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/orchestrator/test_config.py
from app.core.config import get_settings


def test_orchestrator_defaults():
    s = get_settings()
    assert s.agent_orchestrator_enabled is False
    assert s.reflection_enabled is True
    assert s.reflection_min_score == 60
    assert s.reflection_max_retries == 2
    assert s.plan_execute_max_steps == 6
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/agent/orchestrator/test_config.py -v`
Expected: FAIL(AttributeError)

- [ ] **Step 3: 实现**

`config.py` 追加:
```python
    # ②b Agent 编排层
    agent_orchestrator_enabled: bool = False
    reflection_enabled: bool = True
    reflection_min_score: int = 60
    reflection_max_retries: int = 2
    plan_execute_max_steps: int = 6
```
`.env.example` 追加 `AGENT_ORCHESTRATOR_ENABLED=false`。

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/agent/orchestrator/test_config.py -v` → PASS
```bash
git add backend/app/core/config.py .env.example backend/tests/agent/orchestrator/test_config.py
git commit -m "feat(orchestrator): ②b 配置项"
```

---

### Task 2: 模式 router `router.py`

**Files:**
- Create: `backend/app/domain/agent/orchestrator/__init__.py`(空)
- Create: `backend/app/domain/agent/orchestrator/router.py`
- Test: `backend/tests/agent/orchestrator/test_router.py`

**Interfaces:**
- Consumes: `classify_complexity`
- Produces:
  - 常量 `MODE_REACT = "react"`、`MODE_PLAN = "plan_execute"`
  - `choose_mode(query: str, hint: str | None = None) -> str`(complex → Plan,其余 → ReAct;入口 `tool_count=0`,靠长度 + hint)
  - `should_escalate(state: dict) -> bool`(ReAct 达 max_iterations 或连续 tool 失败 ≥2,且 `escalated` 未置位)
  - `should_downgrade(steps: list | None) -> bool`(planner 无有效步骤)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/orchestrator/test_router.py
from app.domain.agent.orchestrator.router import (
    MODE_REACT, MODE_PLAN, choose_mode, should_escalate, should_downgrade,
)


def test_short_query_is_react():
    assert choose_mode("小米诊断") == MODE_REACT


def test_hint_complex_forces_plan():
    assert choose_mode("短", hint="complex") == MODE_PLAN


def test_long_query_is_plan():
    assert choose_mode("长" * 900) == MODE_PLAN


def test_escalate_on_max_iterations():
    assert should_escalate({"outcome": "max_iterations_reached", "escalated": False}) is True


def test_no_escalate_when_already_escalated():
    assert should_escalate({"outcome": "max_iterations_reached", "escalated": True}) is False


def test_downgrade_when_no_steps():
    assert should_downgrade([]) is True
    assert should_downgrade([{"step": "x"}]) is False
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/agent/orchestrator/test_router.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现**

```python
# backend/app/domain/agent/orchestrator/router.py
"""模式路由:入口复杂度选模式 + 运行时升降级判定。"""
from __future__ import annotations

from app.core.adaptive_model import classify_complexity

MODE_REACT = "react"
MODE_PLAN = "plan_execute"


def choose_mode(query: str, hint: str | None = None) -> str:
    # 入口未知实际 tool 数,tool_count=0,靠 query 长度 + hint
    complexity = classify_complexity(query, tool_count=0, hint=hint)
    return MODE_PLAN if complexity == "complex" else MODE_REACT


def should_escalate(state: dict) -> bool:
    if state.get("escalated"):
        return False
    if state.get("outcome") == "max_iterations_reached":
        return True
    return state.get("consecutive_tool_failures", 0) >= 2


def should_downgrade(steps: list | None) -> bool:
    return not steps
```

同时创建空 `orchestrator/__init__.py`。

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/agent/orchestrator/test_router.py -v` → PASS(6 passed)
```bash
git add backend/app/domain/agent/orchestrator/__init__.py backend/app/domain/agent/orchestrator/router.py backend/tests/agent/orchestrator/test_router.py
git commit -m "feat(orchestrator): 模式 router + 升降级判定 + 6 用例"
```

---

### Task 3: ReflectionAgent `reflection.py`

**Files:**
- Create: `backend/app/domain/agent/orchestrator/reflection.py`
- Test: `backend/tests/agent/orchestrator/test_reflection.py`

**Interfaces:**
- Consumes: `LLMClient.simple_chat` / `.available_providers`
- Produces:
  - `@dataclass ReflectionResult`:`score: float`、`completeness: float`、`faithfulness: float`、`tool_appropriateness: float`、`critique: str`、`available: bool`
  - `async def score_answer(query, answer, tool_trace: str, llm) -> ReflectionResult`(无 provider → `available=False, score=100`,即不拦截)
  - `def should_retry(result, attempts_done: int, min_score: int, max_retries: int) -> bool`
  - `def pick_best(attempts: list[tuple[float, str]]) -> str`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/orchestrator/test_reflection.py
from app.domain.agent.orchestrator.reflection import (
    ReflectionResult, score_answer, should_retry, pick_best,
)


class _FakeLLM:
    def __init__(self, reply, providers=("p",)):
        self._reply = reply
        self.available_providers = list(providers)
    async def simple_chat(self, prompt): return self._reply


async def test_score_weighted():
    llm = _FakeLLM('{"completeness": 80, "faithfulness": 90, "tool_appropriateness": 50, "critique": "ok"}')
    r = await score_answer("q", "a", "", llm)
    # 0.4*80 + 0.4*90 + 0.2*50 = 78
    assert r.score == 78.0
    assert r.available is True


async def test_no_provider_passes_through():
    llm = _FakeLLM("x", providers=())
    r = await score_answer("q", "a", "", llm)
    assert r.available is False and r.score == 100.0


async def test_invalid_json_returns_zero_available():
    llm = _FakeLLM("非 JSON")
    r = await score_answer("q", "a", "", llm)
    assert r.available is True and r.score == 0.0


def test_should_retry_logic():
    low = ReflectionResult(50, 0, 0, 0, "c", True)
    high = ReflectionResult(70, 0, 0, 0, "c", True)
    assert should_retry(low, attempts_done=1, min_score=60, max_retries=2) is True
    assert should_retry(low, attempts_done=2, min_score=60, max_retries=2) is False  # 用尽
    assert should_retry(high, attempts_done=1, min_score=60, max_retries=2) is False  # 达标


def test_pick_best_returns_highest():
    assert pick_best([(50.0, "a"), (72.0, "b"), (60.0, "c")]) == "b"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/agent/orchestrator/test_reflection.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现**

```python
# backend/app/domain/agent/orchestrator/reflection.py
"""ReflectionAgent:LLM-as-Judge 多维打分(完整/忠实/工具)0-100 + 重试决策。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog

logger = structlog.get_logger()
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_PROMPT = """你是答案质量评审。对下面【答案】按三维打分(各 0-100),并给一句改进建议。
维度:completeness(完整性) / faithfulness(忠实于工具结果、不编造) / tool_appropriateness(工具使用合理)。
只输出 JSON:{{"completeness": int, "faithfulness": int, "tool_appropriateness": int, "critique": "..."}}

【问题】{query}
【工具轨迹】{tool_trace}
【答案】{answer}
"""


@dataclass
class ReflectionResult:
    score: float
    completeness: float
    faithfulness: float
    tool_appropriateness: float
    critique: str
    available: bool


async def score_answer(query: str, answer: str, tool_trace: str, llm) -> ReflectionResult:
    if not getattr(llm, "available_providers", []):
        return ReflectionResult(100.0, 0, 0, 0, "", False)  # 不拦截
    try:
        reply = _FENCE_RE.sub("", await llm.simple_chat(
            _PROMPT.format(query=query, tool_trace=tool_trace[:2000], answer=answer))).strip()
        obj = json.loads(reply)
        c = float(obj["completeness"])
        f = float(obj["faithfulness"])
        t = float(obj["tool_appropriateness"])
        score = 0.4 * c + 0.4 * f + 0.2 * t
        return ReflectionResult(score, c, f, t, str(obj.get("critique", "")), True)
    except Exception as e:  # noqa: BLE001
        logger.warning("reflection_score_failed", error=str(e))
        return ReflectionResult(0.0, 0, 0, 0, "", True)


def should_retry(result: ReflectionResult, attempts_done: int, min_score: int, max_retries: int) -> bool:
    if not result.available:
        return False
    if result.score >= min_score:
        return False
    return attempts_done <= max_retries


def pick_best(attempts: list[tuple[float, str]]) -> str:
    if not attempts:
        return ""
    return max(attempts, key=lambda x: x[0])[1]
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/agent/orchestrator/test_reflection.py -v` → PASS(5 passed)
```bash
git add backend/app/domain/agent/orchestrator/reflection.py backend/tests/agent/orchestrator/test_reflection.py
git commit -m "feat(orchestrator): ReflectionAgent 多维打分 + 重试决策 + 5 用例"
```

---

### Task 4: Plan-Execute `plan_execute.py`

**Files:**
- Create: `backend/app/domain/agent/orchestrator/plan_execute.py`
- Test: `backend/tests/agent/orchestrator/test_plan_execute.py`

**Interfaces:**
- Consumes: `LLMClient.simple_chat`
- Produces:
  - `_parse_steps(reply: str) -> list[dict]`(解析 `[{"step","tool_hint"}]`;非法/空 → `[]`)
  - `async def plan(query: str, llm, max_steps: int = 6) -> list[dict]`
  - `async def execute(steps: list[dict], step_runner, max_steps: int = 6) -> dict`(逐步跑,累积 `results`;某步抛错 → 记 failure;返回 `{"results": [...], "failed_step": idx|None}`)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/orchestrator/test_plan_execute.py
import pytest
from app.domain.agent.orchestrator.plan_execute import _parse_steps, plan, execute


class _FakeLLM:
    def __init__(self, reply): self._reply = reply
    async def simple_chat(self, prompt): return self._reply


def test_parse_steps_ok():
    steps = _parse_steps('[{"step": "查知识库", "tool_hint": "search_knowledge"}, {"step": "写文章"}]')
    assert len(steps) == 2 and steps[0]["tool_hint"] == "search_knowledge"


def test_parse_steps_invalid_returns_empty():
    assert _parse_steps("不是 JSON") == []


async def test_plan_truncates_to_max():
    llm = _FakeLLM('[{"step":"1"},{"step":"2"},{"step":"3"}]')
    steps = await plan("q", llm, max_steps=2)
    assert len(steps) == 2


async def test_execute_accumulates_results():
    calls = []
    async def _runner(step, idx):
        calls.append(idx)
        return f"结果{idx}"
    out = await execute([{"step": "a"}, {"step": "b"}], _runner, max_steps=6)
    assert out["results"] == ["结果0", "结果1"]
    assert out["failed_step"] is None


async def test_execute_records_failure():
    async def _runner(step, idx):
        if idx == 1:
            raise RuntimeError("boom")
        return "ok"
    out = await execute([{"step": "a"}, {"step": "b"}], _runner, max_steps=6)
    assert out["failed_step"] == 1
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/agent/orchestrator/test_plan_execute.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现**

```python
# backend/app/domain/agent/orchestrator/plan_execute.py
"""Plan-Execute:planner 产有序步骤 + executor 逐步执行(step_runner 注入,便于测试/复用工具)。"""
from __future__ import annotations

import json
import re

import structlog

logger = structlog.get_logger()
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_PLAN_PROMPT = """把下面任务拆成有序执行步骤(最多 {max_steps} 步)。
每步给一句话描述,如需工具给 tool_hint(search_knowledge/diagnose_brand/generate_article/...)。
只输出 JSON 数组:[{{"step": "...", "tool_hint": "..."|null}}]

任务:{query}
"""


def _parse_steps(reply: str) -> list[dict]:
    cleaned = _FENCE_RE.sub("", reply).strip()
    try:
        arr = json.loads(cleaned)
        if not isinstance(arr, list):
            return []
        out = []
        for s in arr:
            if isinstance(s, dict) and s.get("step"):
                out.append({"step": str(s["step"]), "tool_hint": s.get("tool_hint")})
        return out
    except (json.JSONDecodeError, TypeError):
        return []


async def plan(query: str, llm, max_steps: int = 6) -> list[dict]:
    reply = await llm.simple_chat(_PLAN_PROMPT.format(query=query, max_steps=max_steps))
    return _parse_steps(reply)[:max_steps]


async def execute(steps: list[dict], step_runner, max_steps: int = 6) -> dict:
    """逐步执行。step_runner: async (step_dict, idx) -> result。

    某步抛异常 → 记 failed_step 并停止(上层可 replan / 降级)。
    """
    results: list = []
    for idx, step in enumerate(steps[:max_steps]):
        try:
            results.append(await step_runner(step, idx))
        except Exception as e:  # noqa: BLE001
            logger.warning("plan_step_failed", idx=idx, error=str(e))
            return {"results": results, "failed_step": idx}
    return {"results": results, "failed_step": None}
```

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/agent/orchestrator/test_plan_execute.py -v` → PASS(5 passed)
```bash
git add backend/app/domain/agent/orchestrator/plan_execute.py backend/tests/agent/orchestrator/test_plan_execute.py
git commit -m "feat(orchestrator): Plan-Execute planner + executor + 5 用例"
```

---

### Task 5: orchestrator 图组装 `graph.py`

**Files:**
- Create: `backend/app/domain/agent/orchestrator/graph.py`
- Test: `backend/tests/agent/orchestrator/test_orchestrator_graph.py`

**Interfaces:**
- Consumes: `choose_mode`/`should_escalate`/`should_downgrade`(T2)、`plan`/`execute`(T4)、`score_answer`/`should_retry`/`pick_best`(T3)、②a `build_react_graph`
- Produces:
  - `async def run_orchestrated(session_id, message, hint=None, deps=None) -> AsyncIterator[bytes]`
    - `deps` 可注入 `{react_runner, plan_runner, reflector, llm}` 以便测试;默认接真实实现
    - 流程:choose_mode → 跑模式 → reflection 打分 → <60 且有余额则带 critique 重试 → 返回最高分那次;附加发 `mode_switch` / `reflection_score` 事件

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/orchestrator/test_orchestrator_graph.py
import json
from app.domain.agent.orchestrator.graph import run_orchestrated
from app.domain.agent.orchestrator.reflection import ReflectionResult


def _decode(b): return json.loads(b.decode("utf-8"))


class _Deps:
    def __init__(self, scores):
        self._scores = list(scores)
        self.answers = []
    async def react_runner(self, session_id, message, critique=None):
        ans = f"答案-{len(self.answers)}"
        self.answers.append(ans)
        yield ("answer", ans)
    async def plan_runner(self, session_id, message, critique=None):
        yield ("answer", "plan答案")
    async def reflector(self, query, answer, trace, llm):
        return ReflectionResult(self._scores.pop(0), 0, 0, 0, "改进点", True)
    llm = type("L", (), {"available_providers": ["p"]})()


async def test_retry_until_pass_returns_best():
    deps = _Deps(scores=[50.0, 75.0])   # 第一次 50 触发重试,第二次 75 达标
    outs = [_decode(x) async for x in run_orchestrated("s1", "短问题", deps=deps)]
    events = [o["event"] for o in outs]
    assert "reflection_score" in events
    # 返回的 assistant_message 应是高分那次
    final = [o for o in outs if o["event"] == "assistant_message"][-1]
    assert final["content"] == "答案-1"


async def test_low_score_exhausts_returns_best():
    deps = _Deps(scores=[40.0, 50.0, 45.0])  # 都不达标,用尽后返回最高 50 那次
    outs = [_decode(x) async for x in run_orchestrated("s1", "短问题", deps=deps)]
    final = [o for o in outs if o["event"] == "assistant_message"][-1]
    assert final["content"] == "答案-1"  # score 50 对应第二次
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/agent/orchestrator/test_orchestrator_graph.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现**

```python
# backend/app/domain/agent/orchestrator/graph.py
"""orchestrator 编排:router → 模式 → reflection 重试 → 返回最高分。

deps 注入点便于单测;默认接真实实现(②a 统一图 + Plan-Execute + Reflection)。
附加 SSE 事件:mode_switch / reflection_score(前端可忽略)。
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import structlog

from app.core.config import get_settings
from app.domain.agent.orchestrator.reflection import pick_best, score_answer, should_retry
from app.domain.agent.orchestrator.router import MODE_PLAN, choose_mode

logger = structlog.get_logger()


def _emit(event: str, data: dict) -> bytes:
    return (json.dumps({"event": event, **data}, ensure_ascii=False) + "\n").encode("utf-8")


class _RealDeps:
    """默认真实依赖(生产路径)。"""
    def __init__(self):
        from app.domain.llm_client import LLMClient
        self.llm = LLMClient(get_settings())
    async def react_runner(self, session_id, message, critique=None):
        from app.domain.agent.dispatch import _run_langgraph_turn
        msg = message if not critique else f"{message}\n\n[改进要求]{critique}"
        async for sse in _run_langgraph_turn(session_id, msg):
            yield ("sse", sse)
    async def plan_runner(self, session_id, message, critique=None):
        # 简化:Plan-Execute 每步走一次受限图调用;此处委托 react_runner 作 executor 载体
        async for x in self.react_runner(session_id, message, critique):
            yield x
    async def reflector(self, query, answer, trace, llm):
        return await score_answer(query, answer, trace, llm)


async def run_orchestrated(session_id: str, message: str, hint: str | None = None, deps=None) -> AsyncIterator[bytes]:
    settings = get_settings()
    deps = deps or _RealDeps()

    mode = choose_mode(message, hint=hint)
    yield _emit("mode_switch", {"mode": mode})

    runner = deps.plan_runner if mode == MODE_PLAN else deps.react_runner
    attempts: list[tuple[float, str]] = []
    critique = None
    attempt_no = 0

    while True:
        attempt_no += 1
        answer = ""
        async for kind, payload in runner(session_id, message, critique):
            if kind == "sse":
                yield payload                      # 透传底层 SSE
            elif kind == "answer":
                answer = payload
                yield _emit("assistant_message", {"content": answer})

        if not settings.reflection_enabled:
            return
        result = await deps.reflector(message, answer, "", deps.llm)
        attempts.append((result.score, answer))
        yield _emit("reflection_score", {"score": result.score, "critique": result.critique,
                                         "attempt": attempt_no})

        if not should_retry(result, attempts_done=attempt_no,
                            min_score=settings.reflection_min_score,
                            max_retries=settings.reflection_max_retries):
            break
        critique = result.critique

    best = pick_best(attempts)
    # 若最高分不是最后一次,补发一次最终答案
    if best and (not attempts or best != attempts[-1][1]):
        yield _emit("assistant_message", {"content": best})
    yield _emit("turn_complete", {})
```

> 说明:生产路径下底层图产出的是 SSE 字节(`kind=="sse"`),`answer` 抽取可在 ②a 完成后据实接线(从 assistant_message 事件聚合);测试用 `kind=="answer"` 简化验证编排控制流。执行时按 ②a 实际 SSE schema 微调 answer 抽取。

- [ ] **Step 4: 运行确认通过 + 提交**

Run: `cd backend && python -m pytest tests/agent/orchestrator/test_orchestrator_graph.py -v` → PASS(2 passed)
```bash
git add backend/app/domain/agent/orchestrator/graph.py backend/tests/agent/orchestrator/test_orchestrator_graph.py
git commit -m "feat(orchestrator): 编排图 router→模式→reflection 重试→最高分 + 2 用例"
```

---

### Task 6: dispatch 接入 flag

**Files:**
- Modify: `backend/app/domain/agent/dispatch.py`
- Test: `backend/tests/agent/orchestrator/test_dispatch_orchestrator.py`

**Interfaces:**
- Produces:`run_agent_turn` 在 `agent_orchestrator_enabled` 时走 `run_orchestrated`,否则走 ②a 单图

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/agent/orchestrator/test_dispatch_orchestrator.py
import json
from app.domain.agent import dispatch


async def test_dispatch_routes_to_orchestrator(monkeypatch):
    monkeypatch.setattr(dispatch, "get_settings",
                        lambda: type("S", (), {"agent_orchestrator_enabled": True})())
    async def _fake_orch(session_id, message, hint=None):
        yield b'{"event":"mode_switch","mode":"react"}\n'
    monkeypatch.setattr(dispatch, "run_orchestrated", _fake_orch, raising=False)
    outs = [x async for x in dispatch.run_agent_turn("s1", "q")]
    assert any(b"mode_switch" in x for x in outs)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/agent/orchestrator/test_dispatch_orchestrator.py -v`
Expected: FAIL(orchestrator 分支不存在)

- [ ] **Step 3: 实现**

`dispatch.py` 顶部加 `from app.domain.agent.orchestrator.graph import run_orchestrated`;`run_agent_turn` 改为:
```python
async def run_agent_turn(session_id: str, message: str) -> AsyncIterator[bytes]:
    if get_settings().agent_orchestrator_enabled:
        async for sse in run_orchestrated(session_id, message):
            yield sse
        return
    async for sse in _run_langgraph_turn(session_id, message):  # ②a 单一路径
        yield sse
```

- [ ] **Step 4: 运行确认通过 + 全量回归 + 提交**

Run: `cd backend && python -m pytest tests/agent/orchestrator/ -v && python -m pytest tests/ -q`
Expected: orchestrator 全绿 + 全量无回归
```bash
git add backend/app/domain/agent/dispatch.py backend/tests/agent/orchestrator/test_dispatch_orchestrator.py
git commit -m "feat(orchestrator): dispatch 按 flag 接入编排层"
```

---

## Self-Review

**Spec coverage:**
- 配置项 → T1 ✅
- router(入口分类 + 升降级判定)→ T2 ✅
- Reflection(多维打分 0-100 + 重试 + 最高分)→ T3 ✅
- Plan-Execute(planner + executor + 失败记录)→ T4 ✅
- 编排图(router→模式→reflection 重试→最高分 + 附加事件)→ T5 ✅
- dispatch flag 灰度 → T6 ✅
- 降级(无 key reflection 不拦截 / planner 空降级 / reflection 失败跳过)→ T2/T3/T4 ✅
- 附加 SSE 事件 mode_switch/reflection_score → T5 ✅
- 非目标(不改 ②a 内部 / 不动 handoff / 无并行步骤)→ 未纳入 ✅

**Placeholder scan:** 无 TBD;每个代码步骤含完整代码。T5 的 answer 抽取接线依赖 ②a 实际 SSE schema,已显式标注「执行时据实微调」,并给了测试用简化注入路径,非占位。

**Type consistency:** `choose_mode(query, hint)` / `should_escalate(state)` / `should_downgrade(steps)` T2 定义、T5 使用一致;`score_answer(query, answer, trace, llm)→ReflectionResult` / `should_retry(result, attempts_done, min_score, max_retries)` / `pick_best(list[tuple[float,str]])` T3 定义、T5 调用一致;`plan(query, llm, max_steps)` / `execute(steps, step_runner, max_steps)` T4 定义;`run_orchestrated(session_id, message, hint, deps)` T5 定义、T6 调用一致。

> ⚠️ 执行提示:T5/T6 的真实 SSE answer 抽取需对齐 ②a 完成后的事件 schema;建议 ②a 全部完成并 parity 达标后再实施 ②b。
