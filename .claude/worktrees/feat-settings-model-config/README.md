# GEO2 — Generative Engine Optimization Agent

> 一句话:**GEO2** 是"生成式引擎优化(GEO)"的 AI Agent 后端。用户问"我品牌的 AI 搜索表现怎么样?",Agent 调用工具(诊断 / 检索 / 生成 / 任务)给出数据驱动的回答 + 可执行建议。前端配套 React + Vite + Tailwind。

[![CI](https://github.com/your-org/geo2/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/geo2/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

---

## 目录

- [项目概览](#项目概览)
- [关键能力](#关键能力)
- [技术栈](#技术栈)
- [前置要求](#前置要求)
- [5 分钟本地启动](#5-分钟本地启动)
- [Docker 启动](#docker-启动)
- [架构总览](#架构总览)
- [环境变量](#环境变量)
- [可用脚本](#可用脚本)
- [测试](#测试)
- [部署](#部署)
- [Troubleshooting](#troubleshooting)
- [近期发布:v0.8 LangGraph 替换主循环](#近期发布v08-langgraph-替换主循环)

---

## 项目概览

GEO2 把"AI 搜索时代品牌可见性"这件事拆成 5 个工具 + 2 个 specialist + 1 个图形化评测流水线:

| 组件 | 路径 | 角色 |
|---|---|---|
| **ReAct 主循环** | `backend/app/domain/agent/react_loop.py` | 自写 ReAct(flag=False 默认沿用,v0.8 标 deprecated) |
| **LangGraph 主循环** | `backend/app/domain/agent/react_graph.py` | v0.8 LangGraph 替换(flag=True) |
| **5 工具** | `backend/app/domain/agent/tools.py` | diagnose_brand / search_knowledge / list_knowledge_bases / generate_article / create_generation_task |
| **多 Agent specialist** | `backend/app/domain/agent/content_writer_specialist.py` + `backend/app/domain/monitor/monitor_specialist.py` | 上下文隔离,5 条工程纪律 |
| **Handoff 协议** | `backend/app/domain/agent/handoff.py` | 主 Agent → Specialist 最小契约 |
| **评测** | `backend/evals/` | LLM-as-judge + ContentWriter judge |

复评基线 11 维度 **50/55 A+ 卓越**(多 Agent + Harness 路线完成后)。2026-07-14 v0.8 LangGraph 替换主循环已交付,生产灰度中。

---

## 关键能力

- **流式 Agent SSE**:用户对话入口,断点续跑,工具调用可见
- **5 工具 + 2 specialist**:写类工具走 specialist handoff 协议(失败自动降级)
- **跨会话 L2 偏好记忆**:基于 ChromaDB + bge-small-zh-v1.5 的 cosine 检索,4 种压缩策略(noop / truncate / drop / summarize)
- **Human-in-the-Loop 三分类**:Decision / Input / ProgressConfirm,统一走 LangGraph `interrupt()`
- **评测闭环**:LLM-as-judge + 4 维度打分(quality / relevance / format / cost)
- **可视化仪表盘**:成本 / 慢查询 / 评测三条 dashboard
- **灰度切流开关**:`Settings.langgraph_enabled=False` 沿用 react_loop,`True` 切到 LangGraph,**一行 env 回滚**

---

## 技术栈

### Backend(`backend/`)

- **语言**:Python 3.11
- **Web**:FastAPI 0.115 + Uvicorn
- **ORM**:SQLAlchemy 2.0 async + SQLite(aiosqlite);生产可换 PostgreSQL
- **AI / Agent**:
  - **LLMClient**:多 provider 抽象,DeepSeek / Kimi 等开箱即用
  - **LangGraph 1.x**(`v0.8`,主循环)+ **langchain-core**(`@tool` 包装)
  - **ChromaDB 0.5** + **bge-small-zh-v1.5**(L2 偏好向量)
- **验证**:Pydantic 2.x
- **HTTP**:httpx(async)
- **数据库**:
  - 默认 SQLite(`backend/data/geo.db`)
  - Chroma 向量库(`backend/data/chroma/`)
- **PDF**:WeasyPrint(中文支持)+ Jinja2 模板
- **文档解析**:pypdf / python-docx / selectolax(HTML)
- **测试**:pytest 8 + pytest-asyncio + respx + import-linter
- **Quality**:ruff 0.6 + mypy 1.11 + import-linter 2.13
- **LLM Tracing**:Langfuse(可观测,keys 缺失时静默 no-op)
- **Error 聚合**:Sentry(`init_sentry` 缺失 DSN 时静默)
- **Metrics**:prometheus-client(`geo_*` 命名空间)
- **定时**:APScheduler(monitor 调度)
- **加密**:cryptography.Fernet(API key 字段加密)

### Frontend(`frontend/`)

- **框架**:React 18 + TypeScript 5
- **构建**:Vite 6
- **路由**:React Router v6
- **样式**:Tailwind CSS + Radix UI primitives + class-variance-authority + tailwind-merge
- **数据**:TanStack Query(React Query v5)
- **图表**:Recharts
- **图标**:lucide-react
- **CmdK**:cmdk
- **通知**:sonner
- **测试**:Vitest + Testing Library + Playwright(E2E)
- **可访问性**:@axe-core/playwright

### DevOps

- **容器化**:Docker Compose(`docker-compose.yml`)+ 各自 Dockerfile
- **CI**:GitHub Actions(`.github/workflows/ci.yml`,lint + pytest + ruff)
- **架构治理**:import-linter([`backend/.import-linter.toml`](backend/.import-linter.toml))
- **SDD**:superpowers(`docs/superpowers/specs/` + `docs/superpowers/plans/` + `docs/superpowers/handoff/`)

---

## 前置要求

- **Python** 3.11+
- **Node.js** 20+(LTS 推荐)
- **pnpm**(推荐)或 npm
- **Chrome / Chromium**(Playwright e2e)
- **Git** 2.30+

> Windows 用户建议用 Git Bash 跑命令(已在 README 例子中体现)。

---

## 5 分钟本地启动

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/geo2.git
cd geo2
```

### 2. 启动后端

```bash
cd backend
python -m venv .venv
# Windows
.venv/Scripts/python.exe -m pip install -r requirements.txt
# macOS / Linux
.venv/Scripts/python.exe -m pip install -r requirements.txt  # macOS/Linux 同名 scripts
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入至少 DEEPSEEK_API_KEY(或 KIMI_API_KEY)
```

最小 `.env` 内容示例:

```ini
# 必填 — LLM provider key(至少一个)
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 可选 — v0.8 LangGraph 主循环开关
LANGGRAPH_ENABLED=false
```

### 4. 启动 FastAPI

```bash
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

看到 `Uvicorn running on http://0.0.0.0:8000` 即成功。

### 5. 启动前端(另一个终端)

```bash
cd frontend
npm install
npm run dev
```

看到 `Local: http://localhost:5173/` 即成功。

打开 [http://localhost:5173](http://localhost:5173)。

---

## Docker 启动

### 一键启动(backend + frontend)

```bash
# 项目根
cp .env.example .env
# 编辑 .env 填入至少一个 LLM key

docker compose up -d --build
```

服务起来后:

- **后端**:[http://localhost:8000](http://localhost:8000)
- **前端**:[http://localhost:5173](http://localhost:5173)
- **健康检查**:`curl http://localhost:8000/health`

### 数据持久化

- **SQLite**:挂载 `./backend/data:/app/data`(已在 compose 配置)
- **模型缓存**:挂载 `./backend/data/models`(bge-small-zh-v1.5 ~95 MB,首次启动自动下载)

### 关闭

```bash
docker compose down            # 保留数据
docker compose down -v         # 删除 volume 一并清空
```

---

## 架构总览

### 目录结构

```
GEO2/
├── AGENTS.md                         # 给 AI 编码 agent / 新贡献者的地图
├── docker-compose.yml
├── backend/                          # Python 3.11 / FastAPI / SQLAlchemy
│   ├── app/
│   │   ├── api/                      # FastAPI 路由(agent_chat / knowledge / tasks / articles / publishers / monitors / ...)
│   │   ├── core/                     # config / settings / 中间件 / db / providers / langfuse
│   │   ├── domain/                   # 业务核心(agent / generator / llm_client / services)
│   │   │   ├── agent/                # 主循环(react_loop + react_graph + langgraph_nodes)
│   │   │   ├── monitor/              # Monitor Specialist + scheduler + service
│   │   │   ├── publisher/            # WordPress 发布
│   │   │   ├── generator/            # ContentWriter
│   │   │   └── ...                   # diagnosis / hybrid_search / crawler / embedding / ...
│   │   ├── repositories/             # 数据访问
│   │   ├── models/                   # ORM 模型(orm_v02-v04 演进历史保留)
│   │   ├── tasks/                    # 后台 worker
│   │   ├── templates/                # 报告模板(Jinja2)
│   │   └── main.py                   # FastAPI 入口
│   ├── tests/                        # 146 个 pytest(单元 + 集成)
│   ├── evals/                        # LLM-as-judge 评测(cases.py / judge.py / runner.py)
│   ├── data/                         # SQLite / chroma / 模型缓存
│   ├── scripts/                      # 维护 + 灰度脚本
│   ├── .import-linter.toml           # 架构分层合同(AGENTS.md §4)
│   ├── pyproject.toml                # ruff + mypy + pytest
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                         # React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── pages/                    # 6+ 路由页面
│   │   ├── components/               # 业务组件
│   │   ├── lib/                      # api client / hooks / utils
│   │   └── main.tsx
│   ├── tests/                        # Vitest 单测
│   ├── e2e/                          # Playwright e2e
│   ├── vite.config.ts
│   └── Dockerfile
├── docs/
│   ├── review/                       # 11 维度锐评 + 改进计划
│   └── superpowers/                  # SDD(spec / plan / handoff)
├── .github/workflows/ci.yml
└── README.md (← 你正在看)
```

### 架构分层(单向)

`AGENTS.md §4` 明确分层,**禁止反向依赖**(`import-linter` 阻断):

```
api  →  services  →  domain  →  repositories  →  models
```

每层边界由 `backend/.import-linter.toml` 的合同强制。Layer 详情见该文件。

### ReAct 主循环 + LangGraph 替换(v0.8)

**当前(默认)路径**(`Settings.langgraph_enabled=False`):

```
User Message
   ↓
react_loop.run_agent_turn  (725 行手写 ReAct)
   ├─ LLMClient.chat
   ├─ 5 工具(tool_executor 分发;写类工具走 specialist handoff)
   ├─ L2 memory prepend
   ├─ 4 策略自适应压缩(noop/truncate/drop/summarize)
   ├─ Token 截断可解释
   ├─ max_react_iterations 防死循环
   ├─ 流式 SSE 7 类事件(assistant_message / tool_call_start / tool_call_result /
   │   human_confirmation_required / turn_complete / max_iterations_reached / llm_error)
   └─ pending_confirmation 断点续跑
```

**v0.8 LangGraph 路径**(`Settings.langgraph_enabled=True`,灰度中):

```
User Message
   ↓
react_graph.astream_events  (StateGraph + MemorySaver + interrupt)
   ├─ memory_snapshot_node       ← MemorySnapshotNode(L2 prepend)
   ├─ agent_node                 ← policy_llm_call → LLMClient.chat_with_tools
   ├─ tool_node                  ← 5 工具 dispatch(含 specialist handoff)
   ├─ truncate_messages_node     ← adaptive_compression 4 策略
   └─ interrupt_before=["tools"] ← HITLGuard 在 tool_node 内 interrupt(payload)
   ↓
SSEBridge 桥接 7 类 SSE 字节级兼容
```

详见 [`docs/superpowers/specs/2026-07-14-langgraph-react-loop-design.md`](docs/superpowers/specs/2026-07-14-langgraph-react-loop-design.md)。

### 多 Agent + Handoff 协议

```
[User → 主 Agent / ReAct Loop / 5 工具]
   ├─ diagnose_brand      → DiagnosisService
   ├─ search_knowledge    → HybridSearch
   ├─ list_knowledge_bases
   ├─ generate_article    → ContentWriterSpecialist.handoff()    (specialist)
   └─ create_generation_task → ContentWriterSpecialist.handoff_batch()  (specialist)
```

```
ContentWriterSpecialist                         ← 上下文隔离:(system + brand + topic + chunks)
  - 5 条工程纪律:幂等 / 超时 / 状态隔离 / 失败降级 / 成本归因
  - 独立评测:ContentWriter Specialist LLM-as-judge

MonitorSpecialist                               ← 定期 brand × provider × question 监控
  - APScheduler 调度
  - 产出:monitor_snapshots(被前端 dashboard 消费)
```

主 Agent ⇄ Specialist 通过 `HandoffRequest / HandoffResult / SpecialistHandoffError` 5 字段最小契约通信,**严格上下文隔离**(specialist 不持有 ReAct 状态)。

### 数据流(对话入口)

```
Browser → POST /api/agent/chat            (FastAPI StreamingResponse)
              ↓
        api/agent_chat.run_agent_turn
              ↓
        dispatch.run_agent_turn             (按 flag 路由到 react_loop / react_graph)
              ↓
        react_loop OR react_graph 产出 AsyncIterator[bytes]
              ↓
        StreamResponse: SSE 字节流
              ↓
        Browser (react_router + TanStack Query)
```

---

## 环境变量

`backend/.env.example` 列全部可用变量。以下是核心要点:

### 必填

| 变量 | 描述 | 示例 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API key | `sk-xxx` |
| `KIMI_API_KEY`(可选) | Kimi API key | `sk-xxx` |
| `LLM_PROVIDERS` | 启用的 provider 列表(逗号分隔) | `deepseek` |
| `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | 自定义 base / model | 默认值可用 |

### v0.8 LangGraph 灰度切流

| 变量 | 描述 | 默认 |
|---|---|---|
| `LANGGRAPH_ENABLED` | 主循环切流开关 | `false`(沿用 react_loop) |

**切流**:`LANGGRAPH_ENABLED=true`,**回滚**:`LANGGRAPH_ENABLED=false`(**一行 env**)。

### 数据库 / 加密

| 变量 | 描述 |
|---|---|
| `DATABASE_URL` | SQLAlchemy URL,默认 `sqlite+aiosqlite:///./data/reports.db` |
| `ENCRYPTION_KEY` | **必填**用 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成 |

### 监控 / 可观测(可选)

| 变量 | 描述 |
|---|---|
| `SENTRY_DSN` | Sentry 接入(缺失时静默) |
| `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` | Langfuse LLM tracing(缺失静默) |

### 邮件 / 发布(可选)

| 变量 | 描述 |
|---|---|
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | 通知邮件 |
| `PUBLISH_TIMEOUT_S` | WordPress 发布超时(默认 30s) |
| `NOTIFY_EMAIL_DEFAULT` | 默认收件人(留空回退到 SMTP_FROM) |

完整列表见 `backend/.env.example`。

---

## 可用脚本

### 后端(`backend/`)

| 命令 | 描述 |
|---|---|
| `.venv/Scripts/python.exe -m uvicorn app.main:app --reload` | 启动 FastAPI(自动重载) |
| `.venv/Scripts/python.exe -m pytest tests/ -v` | 跑 pytest 146 个测试 |
| `.venv/Scripts/python.exe -m pytest tests/test_xxx.py -v` | 跑单文件 |
| `.venv/Scripts/python.exe -m pytest tests/ -k "test_name"` | 按名字匹配 |
| `.venv/Scripts/python.exe -m ruff check app/` | Lint(ruff) |
| `.venv/Scripts/python.exe -m mypy app/` | 类型检查(mypy) |
| `.venv/Scripts/python.exe -m lint_imports` | import-linter 架构分层检查 |
| `.venv/Scripts/python.exe -m evals.runner` | 跑 LLM-as-judge 评测(默认 mock response) |
| `.venv/Scripts/python.exe -m evals.runner --compare` | v0.8 双跑 react_loop + langgraph(产 `reports/eval/diff/<date>.md`) |
| `.venv/Scripts/lint-imports` | 同上(命令别名) |

### 后端维护脚本(`backend/scripts/`)

| 命令 | 描述 |
|---|---|
| `python scripts/migrate_add_langgraph_thread_id.py data/geo.db` | 给 `agent_sessions` 加 `langgraph_thread_id` TEXT 列(幂等前先备份 DB) |
| `python scripts/agg_metrics.py` | 聚合并报告历史 turn 指标 |
| `bash scripts/gradual_rollout_langgraph.sh start` | 切流(LANGGRAPH_ENABLED=true) |
| `bash scripts/gradual_rollout_langgraph.sh rollback` | 回滚(LANGGRAPH_ENABLED=false,**紧急**) |
| `bash scripts/gradual_rollout_langgraph.sh status` | 当前状态 |

### 前端(`frontend/`)

| 命令 | 描述 |
|---|---|
| `npm run dev` | Vite dev server(:5173) |
| `npm run build` | TS 类型检查 + 产出 |
| `npm run preview` | 预览生产 build |
| `npm run lint` | TS 类型检查 |
| `npm test` | Vitest 单元(无 watch) |
| `npm run test:watch` | Vitest watch 模式 |
| `npm run test:ui` | Vitest UI |
| `npm run test:e2e` | Playwright e2e(需要 `npx playwright install`) |

### Docker

| 命令 | 描述 |
|---|---|
| `docker compose up -d --build` | 起 backend + frontend |
| `docker compose logs -f backend` | 跟后端日志 |
| `docker compose exec backend pytest` | 在容器内跑测试 |
| `docker compose down` | 关(保留数据) |
| `docker compose down -v` | 清数据关 |

---

## 测试

### 后端

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/ -v                          # 全跑
.venv/Scripts/python.exe -m pytest tests/ --tb=short                 # 短 traceback
.venv/Scripts/python.exe -m pytest tests/ -k "hitl"                  # 按名字筛
.venv/Scripts/python.exe -m pytest tests/test_sse_bridge_compat.py   # T11 双跑对照
.venv/Scripts/python.exe -m pytest tests/test_react_graph_integration.py
.venv/Scripts/python.exe -m pytest tests/ --co                       # 只列不跑
```

### 评测(LLM-as-judge)

```bash
cd backend
.venv/Scripts/python.exe -m evals.runner                             # 默认 mock,跑全 EvalCase
.venv/Scripts/python.exe -m evals.runner --case <id>                 # 单 case
.venv/Scripts/python.exe -m evals.runner --compare                   # v0.8 双跑 diff
.venv/Scripts/python.exe -m evals.content_writer_judge               # ContentWriter specialist judge
```

### 前端

```bash
cd frontend
npm test                          # Vitest 单测
npm run test:watch                # Dev
npm run test:ui                   # UI 调试
npm run test:e2e                  # Playwright(先 npx playwright install chromium)
```

### 架构治理

```bash
cd backend
.venv/Scripts/python.exe -m lint_imports        # import-linter 跑分层合同
```

期望:**4 合同 3 kept,1 broken pre-existing**(多 Agent 改造引入的 `handoff_log_repo → handoff` 历史债务,与 LangGraph 改造无关,见 ledger 注释)。

### CI

`.github/workflows/ci.yml`:push / PR 到 main 时跑:
1. pip cache → install requirements
2. ruff + mypy
3. pytest
4. import-linter

---

## 部署

### Docker Compose(推荐)

```bash
# 1. 准备 .env
cp .env.example .env
# 编辑填入 LLM_PROVIDERS / *_API_KEY / ENCRYPTION_KEY

# 2. 启动
docker compose up -d --build

# 3. 健康检查
curl http://localhost:8000/health

# 4. 看日志
docker compose logs -f backend

# 5. 在容器内跑评测
docker compose exec backend .venv/Scripts/python.exe -m evals.runner
```

### 单容器部署

```bash
cd backend
docker build -t geo2-backend .
docker run -d --name geo2-backend \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  geo2-backend
```

### 生产化 Checklist

- [ ] 生成并设置 `ENCRYPTION_KEY`(Fernet key)
- [ ] 至少一个 LLM provider key
- [ ] `DATABASE_URL` 切到 PostgreSQL(不再用 SQLite)
- [ ] 设置 Langfuse keys(LLM 调用可视化)
- [ ] 设置 Sentry DSN(异常聚合)
- [ ] 如要监控指标,expose Prometheus `/metrics`(prometheus_client 已集成)
- [ ] `LANGGRAPH_ENABLED` 保持 `false` 直到灰度 KPI 达标(见 handoff doc)

---

## Troubleshooting

### `ENOENT: no such file or directory` 缺依赖

```bash
cd backend && .venv/Scripts/python.exe -m pip install -r requirements.txt
cd frontend && npm install
```

### `Foreign key constraint failed` / `no such table: handoff_log`

多 Agent 改造引入 `handoff_log` 表,迁移未跑:

```bash
cd backend
.venv/Scripts/python.exe -c "from app.models.orm_v04 import Base; from app.core.db import engine; import asyncio; asyncio.run(Base.metadata.create_all(engine))"
# 或 alembic(若已配置)
```

### ChromaDB 启动失败 / 模型缺失

```bash
ls backend/data/models/
# 应该含 models--BAAI--bge-small-zh-v1.5/ 目录(~95 MB)
# 缺失时,跑一任意 use_vector=True 的请求触发懒加载,或预下载:
# bash scripts/download_bge_model.sh
```

### LangGraph(`LANGGRAPH_ENABLED=true`)出错

1. **立即回滚**:`LANGGRAPH_ENABLED=false`,重启 FastAPI
2. 看 Sentry / Langfuse 异常归因
3. 比对 [`docs/superpowers/handoff/2026-07-14-langgraph-react-loop-evals-result.md`](docs/superpowers/handoff/2026-07-14-langgraph-react-loop-evals-result.md) 列的 KPI 阈值

### import-linter 报错"Domain depends on Repos/Models (NOT Services)"

**这条是 pre-existing broken**(多 Agent 改造遗留:`handoff_log_repo → handoff`),与 LangGraph 改造无关。

若要解决:在 `backend/.import-linter.toml` 的 `Domain depends on Repos/Models (NOT Services)` 合同 `exclusions` 加:

```toml
"app.repositories.handoff_log_repo -> app.domain.agent.handoff",
```

### WeasyPrint 中文字体

Dockerfile 已装 `fonts-noto-cjk`;本地如缺:macOS `brew install font-noto-cjk`、Ubuntu `apt install fonts-noto-cjk`。

### 前端 e2e 失败 / 浏览器缺

```bash
cd frontend
npx playwright install chromium
```

---

## 近期发布:v0.8 LangGraph 替换主循环

**日期**:2026-07-14

**动机**:
- 在 `react_loop.py` 已经自写 725 行 ReAct + 多 Agent 已经 50/55 A+ 卓越底子上,**正确选型并生产化引入 LangGraph**,主循环 scale 到更复杂分支 + HITL checkpoint + 并行 tool
- 保留自写轮子的可控性 + 学习价值(这是已有的牌),新引入框架的"何时用 / 何时不用"权衡判断(这是新牌)

**改动范围(严格锁)**:
- ✅ 只动 `backend/app/domain/agent/react_loop.py` 单文件
- ❌ multi-agent spec §1.3 整体保持(specialist / handoff 协议不引 LangGraph)
- ➕ AGENTS.md §6.5 加 1 行例外:`react_loop.py` 主循环可使用 `langgraph>=1.0,<2.0`
- ➕ `backend/.import-linter.toml` 加 `Domain modules do not import LangGraph internals` 反向合同

**新增模块**(`backend/app/domain/agent/`):
```
langgraph_nodes/                    # 6 个自定义 LangGraph node
  ├── __init__.py
  ├── sse_bridge.py                 # astream_events → 7 类 SSE 字节级兼容
  ├── checkpoint_adapter.py         # agent_sessions.pending_confirmation ↔ thread_id
  ├── memory_snapshot.py            # L2 prepend(react_loop 既有语义)
  ├── truncate_messages.py          # 4 策略自适应压缩
  └── policy.py                     # HITL guard + retry(联携 LLMClient)
state.py                            # AgentState schema(继承 MessagesState)
dispatch.py                         # Settings.langgraph_enabled 路由
react_graph.py                      # StateGraph 工厂(MemorySaver + interrupt_before)
```

**回滚策略**(**一行 env**):

```bash
LANGGRAPH_ENABLED=true       # 用 LangGraph
LANGGRAPH_ENABLED=false      # 回滚 react_loop
```

**灰度 KPI(生产化 ≥ 5 天观测)**:

| 指标 | 阈值 | 失败动作 |
|---|---|---|
| overall_text_match (ROUGE-L) | ≥ 0.95 | revert flag |
| tool_call_match | = 1.0 | revert flag |
| handoff_event_match | = 1.0 | revert flag |
| P95 turn latency | ≤ react_loop + 10% | revert flag |
| tool_call 成功率 | ≥ 99% | revert flag |
| Sentry 异常率 | ≤ react_loop 同期 | revert flag |

详见 [`docs/superpowers/handoff/2026-07-14-langgraph-react-loop-evals-result.md`](docs/superpowers/handoff/2026-07-14-langgraph-react-loop-evals-result.md)。

### 设计文档链

- **Spec**:`docs/superpowers/specs/2026-07-14-langgraph-react-loop-design.md`(commit c6e300a)
- **Plan**:`docs/superpowers/plans/2026-07-14-langgraph-react-loop-plan.md`(commit 4be99ff)
- **Handoff**:`docs/superpowers/handoff/2026-07-14-langgraph-react-loop-evals-result.md`
- **Ledger**:`.superpowers/sdd/progress.md`(22 commits,32 个新测试全 GREEN)

---

## 致谢

- 项目路线建立在 GEO 优化领域 11 维度质量锐评之上,见 `docs/review/README.md`
- 实现路径严格遵循 [`AGENTS.md`](AGENTS.md) 分层与开发约定

---

## 许可

MIT License — 详见 [LICENSE](LICENSE)。
