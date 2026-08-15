# GEO2 — Agent Onboarding Guide

> 给 AI 编码 Agent (Claude / Cursor / Copilot / 等) 与新加入贡献者阅读的仓库地图。
> 更新日期: 2026-07-14 · 配套锐评: `docs/review/README.md`

---

## 1. 项目一句话

**GEO2** 是"生成式引擎优化(GEO)"的 AI Agent 后端:用户问"我品牌的 AI 搜索表现怎么样?",Agent 调用工具(诊断 / 检索 / 生成 / 任务)给出数据驱动的回答 + 可执行建议。

## 2. 仓库结构

```
GEO2/
├── AGENTS.md                         ← 你正在读
├── backend/                          ← Python 3.11 / FastAPI / SQLAlchemy
│   ├── app/
│   │   ├── api/                      ← FastAPI 路由(agent_chat / knowledge / tasks / articles)
│   │   ├── core/                     ← config / settings / 中间件
│   │   ├── domain/                   ← 业务核心(agent / generator / llm_client / services)
│   │   ├── repositories/             ← 数据访问(knowledge_repo / agent_repo / ...)
│   │   ├── models/                   ← ORM 模型(orm_v02-v04 演进历史保留)
│   │   ├── tasks/                    ← 后台 worker
│   │   ├── templates/                ← 报告模板
│   │   └── main.py                   ← FastAPI 入口
│   ├── tests/                        ← pytest(单元 + 集成)
│   ├── evals/                        ← LLM 输出评测集(LLM-as-judge)
│   ├── data/                         ← SQLite DB / 文档样例
│   ├── scripts/                      ← 维护脚本
│   ├── pyproject.toml                ← ruff + mypy + pytest 配置
│   └── requirements.txt
├── frontend/                         ← 前端(v0.6 重设计)
├── docs/
│   ├── review/                       ← 11 维度锐评 + 改进计划
│   └── superpowers/                  ← spec/plan/handoff(SDD 文档)
├── .superpowers/sdd/                 ← SDD 任务 brief + report(轻量过程管理)
├── .github/workflows/ci.yml          ← GitHub Actions CI
└── README.md
```

## 3. 必读文档(按顺序)

1. **[`docs/review/README.md`](docs/review/README.md)** — 11 维度质量锐评 + 总分 35/55(B 级)起点
2. **[`docs/review/99-improvement-plan.md`](docs/review/99-improvement-plan.md)** — 55 项 P0/P1/P2 改进清单
3. **[`docs/superpowers/specs/2026-07-14-geo2-upgrade-design.md`](docs/superpowers/specs/2026-07-14-geo2-upgrade-design.md)** — 升级设计 spec
4. **[`docs/superpowers/plans/2026-07-14-geo2-upgrade-plan.md`](docs/superpowers/plans/2026-07-14-geo2-upgrade-plan.md)** — 升级实施 plan

## 4. 关键架构决策(架构分层,不可破坏)

```
API → Services → Domain → Repositories → Models
(api/ → services/ → domain/ → repositories/ → models/)
```

**禁止反向依赖**:
- repositories/ ❌ import services/ 或 domain/
- domain/ ❌ import api/ 或 repositories/
- models/ ❌ import 任何上层

(阶段 1 Task 3 已用 `tests/test_no_repo_to_service.py` 阻断此违反。)

## 5. Agent Loop 关键路径

- `app/domain/agent/react_loop.py` — 576 行 ReAct 循环(自写,无 LangGraph)
- `app/domain/agent/tools.py` — 5 个工具 schema(diagnose / search / generate / list / task)
- `app/domain/agent/memory.py` — 会话记忆(LLM 摘要 + 窗口截断)
- `app/domain/agent/prompts.py` — Agent system prompt
- `app/domain/agent/tool_executor.py` — 工具执行器(HumanConfirmation 抛点)
- `app/domain/agent/session_manager.py` — 会话持久化 + 断点续跑
- `app/domain/llm_client.py` — LLM 客户端(多 provider 可插拔)
- `app/domain/exceptions.py` — HumanConfirmationRequired + _LLM_TRANSIENT_EXCEPTIONS(共享)

## 6. 开发约定

### 6.1 测试先行(TDD)

每个改进项必须先写测试再写实现。`backend/tests/` 用 pytest,`asyncio_mode = "auto"` 自动识别 async。

### 6.2 Lint / Type

- **ruff**: `cd backend && python -m ruff check app/` (宽泛捕获 BLE001 等)
- **mypy**: 初次跑可能大量警告,`pyproject.toml` 已配 `ignore_missing_imports = true`

### 6.3 Commit 格式(简体中文)

```
<type>(<scope>): <subject>

类型: feat / fix / refactor / test / docs / chore / perf
scope: eval / retry / memory / arch / harness / review ...
```

参考 commit: `git log --oneline | grep "docs(review):"`

### 6.4 阶段 tag

每阶段完成打 tag: `upgrade-stage-0` / `upgrade-stage-1` / `upgrade-stage-2` / ...

### 6.5 不引入新框架

❌ LangGraph / LangChain / LlamaIndex — 自写 ReAct 循环可控性 + 学习价值
✅ 例外(2026-07-14): `app/domain/agent/react_loop.py` 单文件主循环可使用 `langgraph>=1.0,<2.0` 与 `langchain-core` — 详见 [`docs/superpowers/specs/2026-07-14-langgraph-react-loop-design.md`](docs/superpowers/specs/2026-07-14-langgraph-react-loop-design.md)
❌ 改 ORM 版本结构(orm_v02-v04 演进历史保留)
❌ 改业务逻辑(仅工程化补强)

## 7. 跑起来

```bash
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload    # 启动 FastAPI
.venv/Scripts/python.exe -m pytest tests/ -v                  # 跑测试
.venv/Scripts/python.exe -m ruff check app/                   # 跑 lint
.venv/Scripts/python.exe -m evals.runner                      # 跑评测集
```

## 8. 升级路线图(总览)

| 阶段 | 内容 | 估时 | 完成后总分 |
| --- | --- | --- | --- |
| 0 | 基线建立(已完成) | 1d | 35 |
| 1 | P0 突击(6 项) | 6-8d | 40 |
| 2 | P1 核心(20 项) | 20d | 47.5(A 级下限) |
| 3 | P1 剩余(8 项) | 10d | 49 |
| 4 | P2 卓越化(25 项) | 55d | 50+ |

详见 [`docs/superpowers/specs/2026-07-14-geo2-upgrade-design.md`](docs/superpowers/specs/2026-07-14-geo2-upgrade-design.md) §3。

## 9. 给 AI Agent 的提示

如果你要在此仓库做改动:

1. **先读 §3 必读 4 份** — 不读 spec/plan 容易破坏已建立的设计
2. **遵守 §4 架构分层** — 反向依赖会被 import-linter 阻断
3. **每个改进项独立 commit** — 便于审查与回滚
4. **TDD 优先** — 先测试再实现,新测试文件放 `backend/tests/`
5. **不破坏已有测试** — 阶段门控要求 `pytest tests/` 全通过
6. **Commit 简体中文** — 按 §6.3