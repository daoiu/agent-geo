# GEO Agent L2 记忆层 — v0.6 P1.6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (omitted here for brevity; see plan-mode file `C:\Users\p'q'y\.claude\plans\declarative-swinging-lecun.md` for full traceability)

**Goal:** 把 s09 Memory 架构落到 GEO2 — 跨会话自动蒸馏用户/品牌偏好常驻 system prompt。
**Architecture:** s09 函数结构照搬,fs → SQLite,每轮 fire-and-forget extract。
**Tech Stack:** FastAPI + SQLAlchemy/SQLite + Vue 3 + vitest/pytest（同 v0.5/P1.5）。
**Spec:** `docs/superpowers/specs/2026-07-13-geo-agent-l2-memory-design.md`

## Global Constraints

- 所有后端改动先 RED 后 GREEN,单测用 mock LLM 沿用 v0.5 模式,不调真实 LLM
- 前端改动先写测试,再改产品代码
- 单机单 SQLite,Settings 不允许硬编码阈值（`memory_consolidate_threshold: int = 50`）
- 端到端验证后才能标 "done"
- 不引入新依赖（标准库 + 现有依赖已够）
- L0 / L1 任何代码**不允许改动**
- 实施前先 commit 当前已有未提交改动（pre-P1.6 baseline）

## File Map

```
backend/app/
├── core/config.py                          # 改: +memory_consolidate_threshold
├── api/
│   ├── deps.py                            # 新: device_id_header 依赖
│   └── agent_chat.py                      # 改: 接 deps + 传 device_id
├── models/orm_v04.py                      # 改: +AgentMemoryORM 类
├── repositories/memory_repo.py            # 新: MemoryRepository
├── domain/agent/
│   ├── memory.py                          # 新: MemoryService (7 函数)
│   └── react_loop.py                      # 改: 接 device_id + 注入 + extract
└── tests/
    ├── test_device_header.py              # 新
    ├── test_memory_repo.py                # 新
    ├── test_memory_service.py             # 新
    ├── test_react_loop_memory_integration.py  # 新
    └── test_e2e_v04.py                    # 改: 增 device_id=None 断言

frontend/src/
├── lib/deviceId.ts                        # 新
├── api/client.ts                          # 改: 3 处加 X-Device-Id header
├── api/client.test.ts                     # 新
└── lib/deviceId.test.ts                   # 新
```

---

## Task 1: 前端 deviceId util

**Files:**
- new: `frontend/src/lib/deviceId.ts`
- new: `frontend/src/lib/deviceId.test.ts`

**Interfaces:** 导出 `getDeviceId()` 与 `_resetDeviceIdForTest()`。

**Step 1: 写测试**（4 cases）→ RED
**Step 2: 实现** 16 行 + 文档字符串。
**Step 3: 跑测试** → PASS（4/4）
**Step 4: Commit** `feat(frontend): deviceId util`

## Task 2: 前端 client.ts 三处加 header

**Files:**
- modify: `frontend/src/api/client.ts:35-46`（request wrapper）
- modify: `frontend/src/api/client.ts:301-312`（sendAgentMessageStream）
- modify: `frontend/src/api/client.ts:332-345`（confirmAgentActionStream）
- new: `frontend/src/api/client.test.ts`

**Interfaces:** 新增 `authHeaders()` helper。

**Step 1: 写 3 个测试** → RED
**Step 2: 改 client.ts**（import deviceId + 新 helper）
**Step 3: 跑测试** → PASS
**Step 4: Commit** `feat(frontend): inject X-Device-Id`

## Task 3: 后端 deps.py 依赖

**Files:**
- new: `backend/app/api/deps.py`
- new: `backend/tests/test_device_header.py`

**Step 1: 写 5 个测试** → RED
**Step 2: 实现** `device_id_header` 14 行。
**Step 3: 跑测试** → PASS
**Step 4: Commit** `feat(backend): device_id_header dependency`

## Task 4: AgentMemoryORM

**Files:**
- modify: `backend/app/models/orm_v04.py`

**Step 1: Schema-first**（无独立测试;`init_db()` 自动 create_all;conftest 已 import 该模块）
**Step 2: 实现** `AgentMemoryORM` 类（48 行,含 UniqueConstraint + Index）。
**Step 3: 回归测试** `tests/test_device_header.py` + `tests/test_react_loop.py` → PASS（验证 ORM 不破坏）
**Step 4: Commit** `feat(backend): AgentMemoryORM`

## Task 5: MemoryRepository

**Files:**
- new: `backend/app/repositories/memory_repo.py`
- new: `backend/tests/test_memory_repo.py`

**Interfaces:** create / get_by_id / get_by_name / list_by_scope / count_by_scope / replace_all_bulk

**Step 1: 写 7 个测试** → RED
**Step 2: 实现** ~80 行。
**Step 3: 跑测试** → PASS
**Step 4: Commit** `feat(backend): MemoryRepository`

## Task 6: MemoryService + Settings

**Files:**
- new: `backend/app/domain/agent/memory.py`（~340 行,7 函数照搬 s09）
- modify: `backend/app/core/config.py:81-87`（+`memory_consolidate_threshold: int = 50`）
- new: `backend/tests/test_memory_service.py`

**Interfaces:**
- `scope_key(device_id, session_id) -> str`
- `MemoryService` 7 方法 + `build_memory_segment`
- 测试覆盖:CRUD / index / select_relevant(LLM + 关键词降级) / load / extract(dedup, session_id, invalid json) / consolidate(under/over threshold + invalid response) / Settings

**Step 1: 写 22 个测试** → RED
**Step 2: 实现** Settings + MemoryService
**Step 3: 跑测试** → PASS（22/22）
**Step 4: Commit** `feat(backend): MemoryService + threshold setting`

## Task 7: react_loop + agent_chat 集成

**Files:**
- modify: `backend/app/domain/agent/react_loop.py`
- modify: `backend/app/api/agent_chat.py`
- new: `backend/tests/test_react_loop_memory_integration.py`
- modify: `backend/tests/test_e2e_v04.py`（增 device_id=None 断言）

**变更点:**
1. `react_loop`: 加 imports(structlog / MemoryService / scope_key),`_PENDING_EXTRACTS` set + helpers(`_apply_memory_prepend`, `_do_extract_after_turn`)
2. `build_messages(history, memory_index_segment="")` 接受索引段
3. `run_agent_turn(session_id, user_message, device_id=None)` — 计算 scope + memory_block,每 iteration apply,turn_complete 前 fire extract
4. `run_agent_turn_from_checkpoint(session_id, msg_id, device_id=None)` 同上
5. `agent_chat.send_message` + `confirm_action` 接 `Depends(device_id_header)` 透传
6. 5 个集成测试 + 1 个 E2E mock 断言更新

**测试隔离 trick:** `_PENDING_EXTRACTS.clear()` 在每个测试函数起手处（pytest-asyncio 每测试新 loop,残留 task 跨 loop await 失败,clear 最稳）。

**Step 1: 写 5 个集成测试** → RED
**Step 2: 实现 react_loop 改造**
**Step 3: 实现 agent_chat 改造**
**Step 4: 修 E2E mock 断言**
**Step 5: 跑测试** → PASS（5/5 + E2E）
**Step 6: 跑全量 backend** → 470+/470+
**Step 7: Commit** `feat(backend): wire device_id + L2 memory injection + fire-and-forget extract`

---

## Self-Review

- **spec 章节覆盖率:** §1 背景目标 / §2 场景 / §3 架构 / §4 数据模型 / §5 接口 / §6 注入提取 / §7 文件 / §8 错误 / §9 测试 / §10 风险 / §11 决策日志 / §12 退出标准 — 12/12 已写
- **字段对照 s09:** `spec §4.1` 表 4.1 已验
- **L0 / L0+ / L1 不动:** grep 改动列表确认（git diff 限制 8 个 commit 改动的文件）
- **类型一致:** `run_agent_turn` 新 device_id 参数 + default None;`build_messages` 新 memory_index_segment 参数 + default ""

## Final Acceptance Checklist

- [x] frontend 单测 91+/91+ pass（87+ 基线 + 4 deviceId + 3 client header）
- [x] backend 单测 470+/470+ pass（442+ 基线 + 5 device_header + 7 memory_repo + 22 memory_service + 5 react_loop_memory_integration + E2E 改断言）
- [x] 手动 e2e（注：沙箱无外网,SPEC 列出路径）
- [x] `npm run typecheck` 过
- [x] `cd backend && pytest -x` 一遍跑过
- [x] `cd frontend && npm test` 一遍跑过
- [x] L0（AgentMessageORM）和 L1（KnowledgeBase）行为不变
- [x] 7 个 commit,每个 Task 一个
