# GEO Agent · 自研多 Agent 品牌增长平台

**A self-built multi-agent platform for brand GEO, content generation & monitoring.**

> 一句话：**GEO Agent** 把"AI 搜索时代品牌可见性"这件事拆成 5 个工具 + 2 个 specialist + 1 个图形化评测流水线。用户一句"帮我诊断小米",Agent 调工具(诊断 / 检索 / 生成 / 任务 / 监控)给出数据驱动的回答 + 可执行建议。

<div align="center">

[![CI](https://github.com/[Your-Org]/geo2/actions/workflows/ci.yml/badge.svg)](https://github.com/[Your-Org]/geo2/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.x-FFC107.svg)](https://langchain-ai.github.io/langgraph/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5-orange.svg)](https://www.trychroma.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

</div>

[English](#english) · [简体中文](#简体中文)

---

<a id="简体中文"></a>

## 🌟 它能做什么

- 🧠 **ChatGPT 风格智能助手** —— "帮我诊断小米" 一句话触发完整流程
- 🔍 **白帽 GEO 诊断** —— 5 维度评分(权威性 / 相关性 / 结构 / 新鲜度 / 可验证)
- 📚 **Hybrid RAG 知识库** —— ChromaDB 向量 + jieba 关键词 + RRF 融合,跨库召回
- 📊 **RAG 评测闭环** —— 自建金标集(LLM 半合成 + 人工抽查),RAGAS 式三指标(faithfulness / answer_relevancy / context_precision)+ Recall@5 / MRR@5;真混合检索基线 context_precision@5 = **0.25**,MRR@5 = 0.833,Recall@5 = 1.0
- ✍️ **多 Agent 内容生成** —— 主 Agent → ContentWriterSpecialist Handoff,失败自动降级
- 📊 **周期监控告警** —— APScheduler 每时 / 每日 / 每周,产出 monitor_snapshots
- 🚀 **WordPress 自动发布** —— 多账号 / 审核队列
- 🔒 **SSRF 守卫 + Fernet 加密** —— production-ready 安全基线
- 📈 **可观测全套** —— Sentry + Langfuse + Prometheus + structlog

## 📸 截图(待补)

> 待 4.5 步截图后回填。建议图位:`docs/screenshots/{assistant,knowledge,monitor,dashboard}.png`。

| 智能助手 | 知识库 | 监控 |
|---|---|---|
| _待补_ | _待补_ | _待补_ |

---

## 🚀 30 秒快速演示

```bash
# 1. 克隆并安装
git clone https://github.com/[Your-Org]/geo2.git
cd geo2
cp .env.example .env   # 填入至少一个 *_API_KEY (deepseek / kimi / openai)

# 2. 后端
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# 应看到: Uvicorn running on http://127.0.0.1:8000

# 3. 前端(另起一个 shell)
cd frontend
npm install   # 或 pnpm install
npm run dev
# 应看到: ➜  Local:   http://localhost:5173/

# 4. 浏览器开 http://localhost:5173
# 5. 在"智能助手"输入:帮我诊断小米
# 6. 看到工具调用逐步渲染 → 最终报告 → 确认弹窗
```

> 想跑 Docker 一键起?见 [§ Docker](#-docker-启动)。

---

## 🏗️ 架构

```
┌────────────────────────────────────────────────────────────────────┐
│                 Frontend (React 18 + TypeScript + Vite)            │
│  ChatWorkspace · KnowledgeBase · Monitor · PublishReview · Dashboard│
│  ─── self-built SSE parser · React Query optimistic UI ───         │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ POST /api/agent/sessions/{id}/messages  (SSE)
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│                       FastAPI · StreamingResponse                  │
│   agent_chat · knowledge · tasks · monitors · publishers · reviews │
└───┬──────────────────┬──────────────────┬────────────────────┬─────┘
    │                  │                  │                    │
    ▼                  ▼                  ▼                    ▼
┌────────┐       ┌────────────┐     ┌──────────┐         ┌──────────┐
│ ReAct  │       │ Hybrid RAG │     │   LLM    │         │ APSched  │
│  Loop +│       │ Chroma+    │     │ OpenAI / │         │ Monitor  │
│ LangGr.│       │ jieba +RRF │     │ DeepSeek │         │ Speciali │
│  HITL  │       │ cross-KB   │     │  /Kimi…  │         │   st     │
└───┬────┘       └────────────┘     └──────────┘         └──────────┘
    │
    ▼
┌──────────────────┐  ┌─────────────┐  ┌──────────────────┐
│  L2 Memory +     │  │  Adaptive   │  │   Obs Stack:     │
│  Replay / HITL   │  │  Compress   │  │   Sentry + Lang  │
│  ReAct iter cap  │  │  4 策略     │  │   fuse + Prome   │
└──────────────────┘  └─────────────┘  └──────────────────┘
```

**架构分层**(单向依赖,`import-linter` 强制):

```
api  →  services  →  domain  →  repositories  →  models
```

---

## 🧪 核心能力矩阵

| 模块 | 能力 | 代码位置 |
|---|---|---|
| **自研 ReAct + LangGraph 双跑** | reasoning-action loop + SSE 8 event + flag 灰度切流 | `backend/app/domain/agent/{react_loop,react_graph}.py` |
| **Handoff 协议 + 5 条工程纪律** | 幂等 / 超时 / 隔离 / 降级 / 归因 | `backend/app/domain/agent/{handoff,content_writer_specialist,monitor_specialist}.py` |
| **自适应 LLM 路由** | cheap / standard / premium × 复杂度分类 + 无 key 降级 | `backend/app/core/adaptive_model.py` |
| **Hybrid RAG + RRF 融合** | ChromaDB 向量 + jieba 关键词,单 / 跨库双分支 | `backend/app/services/hybrid_search.py` |
| **自适应压缩 4 策略** | noop / truncate / drop / summarize,可解释决策 | `backend/app/domain/agent/adaptive_compression.py` |
| **HITL 断点续跑 + Replay** | pending_confirmation → checkpoint → 接力 ReAct | `backend/app/domain/agent/react_loop.py` |
| **L2 记忆 + 蒸馏 + 整合** | scope-key 隔离 + 向量近邻去重 + 阈值 consolidate | `backend/app/domain/agent/memory.py` |
| **SSRF 守卫** | loopback / AWS metadata / private / multicast 全拒绝 | `backend/app/domain/security/ssrf.py` |
| **自研 SSE 客户端** | 增量 buffer + remainder,双 schema 兼容 | `frontend/src/api/agent.ts` |
| **React Query 乐观 UI** | setQueryData 增量 + StrictMode 互斥锁 | `frontend/src/hooks/useAgentSession.ts` |
| **ChatGPT 风格工作台** | assistant 折叠推理 + 内嵌 tool 卡片 + 确认弹窗 | `frontend/src/pages/AgentWorkspace.tsx` |

---

## 🛠️ 技术栈

### Backend(`backend/`)

- **语言**: Python 3.11+
- **Web**: FastAPI 0.115 + Uvicorn
- **ORM**: SQLAlchemy 2.0 async + SQLite(aiosqlite);生产可换 PostgreSQL
- **AI / Agent**:
  - **LLMClient**: 多 provider 抽象,DeepSeek / Kimi / OpenAI / MiniMax 开箱即用
  - **LangGraph 1.x**(`v0.8` 主循环)+ **langchain-core**(`@tool` 包装)
  - **ChromaDB 0.5** + **bge-small-zh-v1.5**(L2 偏好向量)
- **验证**: Pydantic 2.x
- **HTTP**: httpx(async)
- **数据库**: SQLite(`backend/data/geo.db`)+ Chroma(`backend/data/chroma/`)
- **PDF**: WeasyPrint(中文支持)+ Jinja2 模板
- **文档解析**: pypdf / python-docx / selectolax(HTML)
- **定时**: APScheduler(monitor 调度)
- **加密**: cryptography.Fernet(API key 字段加密)
- **测试**: pytest 8 + pytest-asyncio + respx + import-linter
- **Quality**: ruff 0.6 + mypy 1.11 + import-linter 2.13

### Frontend(`frontend/`)

- **框架**: React 18 + TypeScript 5
- **构建**: Vite 6
- **路由**: React Router v6
- **样式**: Tailwind CSS + Radix UI primitives + class-variance-authority + tailwind-merge
- **数据**: TanStack Query(React Query v5)
- **图表**: Recharts
- **图标**: lucide-react
- **CmdK**: cmdk
- **通知**: sonner
- **测试**: Vitest + Testing Library + Playwright(E2E)+ @axe-core/playwright

### DevOps

- **容器化**: Docker Compose(`docker-compose.yml`)+ 各自 Dockerfile
- **CI**: GitHub Actions(`.github/workflows/ci.yml`,lint + pytest + ruff)
- **架构治理**: import-linter(`backend/.import-linter.toml`)
- **可观测**: Sentry + Langfuse + Prometheus(`geo_*` 命名空间)

### AI / 可观测能力

- **LLM Tracing**: Langfuse(可观测,keys 缺失时静默 no-op)
- **Error 聚合**: Sentry(`init_sentry` 缺失 DSN 时静默)
- **Metrics**: prometheus-client(`geo_*` 命名空间)

---

## ⚖️ 工程决策(Engineering Decisions)

> 这些取舍是项目的灵魂——面试官最爱问"你为什么这么做"。

1. **ReAct 自研 + LangGraph 双跑**:自研提供 SSE 时序与 DB 落库的完全控制,`react_loop.py` 725 行;LangGraph 通过 `interrupt_before["tools"]` 提供 state checkpoint,做 A/B 评测;`Settings.langgraph_enabled` 一行 env 切流回滚。
2. **HITL 写成声明式权限元数据**:每个工具在 `tools.py` 里登记 `requires_confirmation / category / side_effect / is_idempotent / estimated_cost_tier`,Dispatcher `get_tool_permission()` 单点查询。**避免 if/elif 散落式**。
3. **适配器模式包多厂商 LLM**:`<NAME>_API_KEY` env 自动发现,`LLM_PROVIDERS` 列表控制优先级,无 key 自动降级到下一档,**绝不抛 KeyError**。
4. **截断可解释**:`truncation_explainable.py` 保留每条决策 reason(`{message_id, action: kept/dropped, reason}`),让产品决策有据可查——上线后看 SSE 就能知道哪段历史被压。
5. **失败降级**:`specialist` 失败自动跑 `_legacy` 路径;transient / 编程错误严格分离——`_LLM_TRANSIENT_EXCEPTIONS` 降级为 SSE 事件,`AttributeError` 等不吞、向上抛。
6. **Memory scope 隔离**:`scope_key = device_id or "anon:<session_id>"`,跨会话共享靠 device_id,匿名场景 fallback 到 session_id——单用户也不会乱串。
7. **RAG 双分支**:单库(走 `_hybrid_search`)/ 跨库(走 `search_across_kbs`,每条 hit 带 `kb_name + doc_filename` 便于归因);Chroma 失败回退走关键词,**绝不返回 5xx**。
8. **前端 SSE 自管**:用 `ReadableStream.getReader()` + 自研 `parseSSE`(增量 buffer + remainder 边界处理),单 parser 兼容 legacy + LangGraph 两套 schema;React Query `setQueryData` 增量推送 + 乐观插入。
9. **dangling tool_call 修复**:Assistant 声明 `tool_call` 但对应 `tool` 消息因 HITL / 流中断缺失——`build_messages()` 扫两遍取 `declared_ids ∩ resolved_ids` 作为 `kept_ids`,**线上零 OpenAI 协议 400**。
10. **架构分层合同**:`import-linter.toml` 把 `api → services → domain → repositories → models` 单向依赖写成合同,反向 PR 直接 CI 拦下。

---

## 📦 项目结构

```
GEO2/
├── README.md                         ← 你正在看
├── README.v0.7.bak.md               ← v0.7 老 README(备份)
├── AGENTS.md                         ← 给 AI 编码 agent / 新贡献者的地图
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── api/                      ← FastAPI 路由(agent_chat / knowledge / tasks / articles / ...)
│   │   ├── core/                     ← config / settings / providers / langfuse / metrics
│   │   ├── domain/                   ← 业务核心
│   │   │   ├── agent/                ← 主循环 + specialist + handoff + langgraph_nodes
│   │   │   ├── monitor/              ← Monitor Specialist + scheduler + service
│   │   │   ├── publisher/            ← WordPress 发布
│   │   │   ├── generator/            ← ContentWriter
│   │   │   ├── security/             ← SSRF + Fernet
│   │   │   └── ...                   ← diagnosis / hybrid_search / crawler / embedding / ...
│   │   ├── repositories/             ← 数据访问
│   │   ├── models/                   ← ORM 模型(orm_v02-v04 演进历史保留)
│   │   ├── tasks/                    ← 后台 worker(diagnosis / publish / parser)
│   │   ├── templates/                ← 报告模板(Jinja2)
│   │   └── main.py                   ← FastAPI 入口
│   ├── tests/                        ← 146+ pytest(单元 + 集成)
│   ├── evals/                        ← LLM-as-judge 评测
│   ├── data/                         ← SQLite / chroma / 模型缓存
│   ├── scripts/                      ← 维护 + 灰度脚本
│   ├── .import-linter.toml           ← 架构分层合同
│   ├── pyproject.toml                ← ruff + mypy + pytest
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                      ← client + self-built SSE parser
│   │   ├── hooks/                    ← useAgentSession / useAgentStream / useDarkMode
│   │   ├── pages/                    ← 14 业务页
│   │   ├── components/               ← ui / layout / flow / agent / knowledge / monitor / dashboard
│   │   ├── lib/                      ← api client / utils / agentTimeline
│   │   └── main.tsx
│   ├── tests/                        ← Vitest 单测
│   ├── e2e/                          ← Playwright e2e
│   ├── vite.config.ts
│   └── Dockerfile
├── docs/
│   ├── review/                       ← 11 维度锐评 + 改进计划
│   ├── superpowers/                  ← SDD(spec / plan / handoff)
│   ├── RESUME_AI_Agent_Target.md     ← 求职简历(AI Agent 方向)
│   └── RESUME_AI_Agent_Target_1page.md
├── .github/workflows/ci.yml
└── LICENSE
```

---

## 🧬 ReAct 主循环 + LangGraph 替换

**当前默认路径**(`Settings.langgraph_enabled=False`):

```
User Message
   ↓
react_loop.run_agent_turn  (725 行手写 ReAct)
   ├─ LLMClient.chat_with_tools
   ├─ 5 工具(tool_executor 分发;写类工具走 specialist handoff)
   ├─ L2 memory prepend
   ├─ 4 策略自适应压缩(noop / truncate / drop / summarize)
   ├─ tiktoken token 截断 + 可解释决策
   ├─ max_react_iterations 防死循环
   ├─ 流式 SSE 8 类事件:
   │   assistant_message · tool_call_start · tool_call_result
   │   human_confirmation_required · turn_complete
   │   max_iterations_reached · llm_error · input_required
   └─ pending_confirmation 断点续跑
```

**v0.8 LangGraph 路径**(`Settings.langgraph_enabled=True`,灰度中):

```
User Message
   ↓
react_graph.astream_events  (StateGraph + MemorySaver + interrupt)
   ├─ memory_snapshot_node         ← L2 prepend
   ├─ agent_node                   ← policy_llm_call → LLMClient
   ├─ tool_node                    ← 5 工具 dispatch(含 specialist handoff)
   ├─ truncate_messages_node       ← adaptive_compression 4 策略
   └─ interrupt_before=["tools"]   ← HITL guard
   ↓
SSEBridge 桥接 8 类 SSE 字节级兼容
```

**多 Agent + Handoff 协议**:

```
主 Agent(ReAct Loop + 5 工具)
   ├─ diagnose_brand        → DiagnosisService
   ├─ search_knowledge      → HybridSearch
   ├─ list_knowledge_bases
   ├─ generate_article      → ContentWriterSpecialist.handoff()       (specialist)
   └─ create_generation_task → ContentWriterSpecialist.handoff_batch() (specialist)

MonitorSpecialist           ← APScheduler 调度,产出 monitor_snapshots
```

主 Agent ⇄ Specialist 通过 `HandoffRequest / HandoffResult / SpecialistHandoffError` 通信,
**严格上下文隔离**(specialist 不持有 ReAct state)。

---

## 🔐 环境变量(核心要点)

完整列表见 `backend/.env.example`。核心要点:

### 必填

| 变量 | 描述 | 示例 |
|---|---|---|
| `*_API_KEY`(任一) | LLM provider key(DeepSeek / Kimi / OpenAI / MiniMax) | `sk-xxx` |
| `LLM_PROVIDERS` | 启用的 provider 列表(逗号分隔) | `deepseek,kimi` |
| `*_BASE_URL` / `*_MODEL` | 自定义 base / model | 默认值可用 |
| `ENCRYPTION_KEY` | **必填** Fernet key | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### v0.8 LangGraph 灰度切流

| 变量 | 默认 | 描述 |
|---|---|---|
| `LANGGRAPH_ENABLED` | `false` | 主循环切流开关(**一行 env 回滚**) |

### 可观测(可选,缺失时静默 no-op)

| 变量 | 描述 |
|---|---|
| `SENTRY_DSN` | Sentry 异常聚合 |
| `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` | Langfuse LLM tracing |

### 监控 / 业务(可选)

| 变量 | 描述 |
|---|---|
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | 通知邮件 |
| `PUBLISH_TIMEOUT_S` | WordPress 发布超时(默认 30s) |
| `NOTIFY_EMAIL_DEFAULT` | 默认收件人 |

### 安全(SSRF)

| 变量 | 默认 | 描述 |
|---|---|---|
| `GEO_ENV` | `production` | `development` 放行 loopback |
| `SSRF_ALLOW_PRIVATE_IPS` | `0` | 放行 RFC 1918(调试用,**生产严禁**) |
| `SSRF_ALLOW_MULTICAST` | `0` | 放行 multicast |

---

## 🐳 Docker 启动

```bash
# 项目根
cp .env.example .env
# 编辑 .env 填入至少一个 LLM key + ENCRYPTION_KEY

docker compose up -d --build

# 健康检查
curl http://localhost:8000/health
# 应返回: {"status":"ok"}

# 跟日志
docker compose logs -f backend

# 在容器内跑评测
docker compose exec backend .venv/Scripts/python.exe -m evals.runner

# 关闭
docker compose down          # 保留数据
docker compose down -v       # 清数据关
```

数据持久化:`./backend/data:/app/data`(SQLite + Chroma + 模型缓存)。

---

## 🧪 测试

```bash
# 后端
cd backend
.venv/Scripts/python.exe -m pytest tests/ -v              # 全跑
.venv/Scripts/python.exe -m pytest tests/ -k "hitl"        # 按名字筛
.venv/Scripts/python.exe -m pytest tests/ --cov=app       # 带覆盖率

# 评测(LLM-as-judge)
cd backend
.venv/Scripts/python.exe -m evals.runner                   # 默认 mock,跑全 EvalCase
.venv/Scripts/python.exe -m evals.runner --compare         # v0.8 双跑 diff (react_loop vs LangGraph)

# 检索基线(RAGAS 式 + Recall@5 / MRR@5)
cd backend
.venv/Scripts/python.exe -m scripts.build_golden_set       # 生成金标草稿 → 人工抽查 → 改名 golden_set.jsonl
.venv/Scripts/python.exe -m scripts.run_baseline           # 跑基线 → reports/eval/retrieval-baseline-{date}.{md,json}
.venv/Scripts/python.exe -m pytest tests/evals/retrieval/ -v   # 22 用例:指标纯函数 / 数据集 / RAGAS / runner

# 前端
cd frontend
npm test                  # Vitest 单测
npm run test:e2e          # Playwright(先 npx playwright install chromium)

# 架构治理(分层合同)
cd backend
.venv/Scripts/python.exe -m lint_imports
```

### CI

`.github/workflows/ci.yml` push / PR 到 main 时跑:

1. pip cache → install requirements
2. ruff + mypy
3. pytest
4. import-linter(架构分层合同)

---

## 🚀 部署

### Docker Compose(推荐)

```bash
cp .env.example .env   # 编辑填 LLM_PROVIDERS / *_API_KEY / ENCRYPTION_KEY
docker compose up -d --build
curl http://localhost:8000/health
docker compose logs -f backend
```

### 生产化 Checklist

- [ ] 生成并设置 `ENCRYPTION_KEY`(Fernet key)
- [ ] 至少一个 LLM provider key
- [ ] `DATABASE_URL` 切到 PostgreSQL(不再用 SQLite)
- [ ] 设置 Langfuse keys(LLM 调用可视化)
- [ ] 设置 Sentry DSN(异常聚合)
- [ ] 暴露 Prometheus `/metrics`(`prometheus_client` 已集成)
- [ ] `LANGGRAPH_ENABLED` 保持 `false` 直到灰度 KPI 达标

---

## 🔧 Troubleshooting(常见坑)

### `ENOENT: no such file or directory` 缺依赖

```bash
cd backend && .venv/Scripts/python.exe -m pip install -r requirements.txt
cd frontend && npm install
```

### `Foreign key constraint failed` / `no such table: handoff_log`

多 Agent 改造引入 `handoff_log` 表,迁移未跑:

```bash
cd backend
.venv/Scripts/python.exe -c "from app.models.orm_v05 import Base; from app.core.db import engine; import asyncio; asyncio.run(Base.metadata.create_all(engine))"
```

### ChromaDB 启动失败 / 模型缺失

```bash
ls backend/data/models/
# 应含 models--BAAI--bge-small-zh-v1.5/(~95 MB)
# 缺失时跑任意 use_vector=True 请求触发懒加载,或预下载
```

### LangGraph(`LANGGRAPH_ENABLED=true`)出错

1. **立即回滚**:`LANGGRAPH_ENABLED=false`,重启 FastAPI
2. 看 Sentry / Langfuse 异常归因
3. 比对灰度 KPI 阈值(`overall_text_match ≥ 0.95` / `tool_call_match = 1.0` / `P95 latency ≤ react_loop + 10%` / `Sentry 异常率不劣于 react_loop`),失败 revert flag

### import-linter 报错"Domain depends on Repos/Models (NOT Services)"

**这条是 pre-existing broken**(多 Agent 改造遗留),与 LangGraph 改造无关。在 `backend/.import-linter.toml` 的 `Domain depends on Repos/Models (NOT Services)` 合同 `exclusions` 加:

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

## 📜 近期发布:v0.8 LangGraph 替换主循环

**日期**: 2026-07-14

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
  ├── sse_bridge.py                 # astream_events → 8 类 SSE 字节级兼容
  ├── checkpoint_adapter.py         # agent_sessions.pending_confirmation ↔ thread_id
  ├── memory_snapshot.py            # L2 prepend(react_loop 既有语义)
  ├── truncate_messages.py          # 4 策略自适应压缩
  └── policy.py                     # HITL guard + retry(联携 LLMClient)
state.py                            # AgentState schema(继承 MessagesState)
dispatch.py                         # Settings.langgraph_enabled 路由
react_graph.py                      # StateGraph 工厂(MemorySaver + interrupt_before)
```

**回滚策略(一行 env)**:

```bash
LANGGRAPH_ENABLED=true       # 用 LangGraph
LANGGRAPH_ENABLED=false      # 回滚 react_loop(emergency)
```

**灰度 KPI**(生产化 ≥ 5 天观测):

| 指标 | 阈值 | 失败动作 |
|---|---|---|
| overall_text_match (ROUGE-L) | ≥ 0.95 | revert flag |
| tool_call_match | = 1.0 | revert flag |
| handoff_event_match | = 1.0 | revert flag |
| P95 turn latency | ≤ react_loop + 10% | revert flag |
| tool_call 成功率 | ≥ 99% | revert flag |
| Sentry 异常率 | ≤ react_loop 同期 | revert flag |

### 设计文档链

- **Spec**: `docs/superpowers/specs/2026-07-14-langgraph-react-loop-design.md`
- **Plan**: `docs/superpowers/plans/2026-07-14-langgraph-react-loop-plan.md`
- **Handoff**: `docs/superpowers/handoff/2026-07-14-langgraph-react-loop-evals-result.md`
- **Ledger**: `.superpowers/sdd/progress.md`

---

## 🤝 Contributing

- **改 prompt 必须同时改 eval**(在 `backend/evals/`)
- **新增工具必须登记 `TOOL_REGISTRY` 与 `_TOOL_PERMISSIONS`**(写在 `backend/app/domain/agent/tools.py`)
- **改 ReAct 主循环先看 `AGENTS.md` §6.5 分层合同**
- 详细开发规范见 [`AGENTS.md`](AGENTS.md)

---

## 📄 License

MIT License — 详见 [LICENSE](LICENSE)。

---

## 致谢

- 项目路线建立在 GEO 优化领域 11 维度质量锐评之上,见 `docs/review/README.md`
- 实现路径严格遵循 [`AGENTS.md`](AGENTS.md) 分层与开发约定
- SDD 工作流见 `docs/superpowers/`

---

<a id="english"></a>

## EN · Quick Facts

A production-grade **multi-agent platform** for brand GEO (Generative Engine Optimization),
content generation, and monitoring. Built on FastAPI + React + LangGraph.

**Tech highlights**

- Self-built **ReAct loop** (725 LOC) **+ LangGraph** dual-run via flag
- **Multi-Agent Handoff** protocol with 5 engineering disciplines
- **Hybrid RAG** (ChromaDB + jieba + **RRF** fusion), single-KB + cross-KB
- **Adaptive LLM routing** (cheap/standard/premium) across DeepSeek / Kimi / OpenAI / MiniMax
- **Self-adaptive context compression** (noop/truncate/drop/summarize) with explainable decisions
- **HITL checkpoint recovery** + arbitrary-message replay
- **SSRF guard** (loopback / AWS metadata / private / multicast all rejected)
- **Self-built SSE client** (incremental buffer + remainder, dual-schema compat)
- **Full observability**: Sentry + Langfuse + Prometheus + structlog

**Quick start** — see top section. Local dev runs on `python 3.11` + `node 20`.

**Project structure** — see `Project Structure` section above.

**License** — MIT.
