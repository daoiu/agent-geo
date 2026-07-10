# GEO 优化 Agent v0.4

白帽 GEO（生成引擎优化）工具集。给非技术市场人员用：诊断品牌 GEO 健康度 + 基于自有知识库批量生成内容 + 自动发布到 WordPress + 监测提及率变化 + **自然语言入口（自主决策 Agent）**。

## 版本演进

| 版本 | 状态 | 核心能力 |
|---|---|---|
| v0.1 | ✅ | GEO 健康度诊断（爬虫 + LLM 实测 + 5 维评分 + 建议） |
| v0.2 | ✅ | 知识库 + 内容生成（上传资料 → 批量生成文章 → 人工审核） |
| v0.3 | ✅ | 完整闭环（WordPress 发布 + 提及率监测 + 邮件通知） |
| **v0.4** | **✅ 当前** | **自主决策 Agent（自然语言入口 + ReAct 推理 + 3 工具 + Human-in-the-loop）** |
| v0.5 | 🎯 下一步 | 行业基准 / 竞品对比 + 向量检索升级 |

详细路线图见 [docs/ROADMAP.md](docs/ROADMAP.md)。

## v0.4 当前版本功能

### 自主决策 Agent

- **自然语言入口**：用 chat 跟 agent 对话（如"帮我提升小米 GEO 可见度"）
- **ReAct 推理循环**：自写循环（不引 LangGraph），MAX_REACT_ITERATIONS = 5
- **3 个工具**：
  - `diagnose_brand`（读，包装 v0.1 诊断）
  - `search_knowledge`（读，包装 v0.2 知识库，chunk 截断 500 字）
  - `generate_article`（写，包装 v0.2 ContentWriter，**仅预览不落库**）
- **Human-in-the-loop**：写类工具弹窗确认
- **断点续跑**：用户确认后自动从断点继续
- **SSE 流式响应**：FastAPI `StreamingResponse` + 前端 `fetch + ReadableStream`
- **多 session + 历史**：所有会话持久化到 SQLite，跨刷新可恢复
- **SSRF 守卫**：URL 拒绝内部 IP（环境变量切换 dev/prod 模式）

### 来自 v0.1-v0.3

- GEO 健康度诊断（5 维评分卡 + 优化建议 + PDF 报告）
- 知识库管理（PDF/Word/MD/TXT 上传 + 自动解析切片）
- 关键词检索（jieba 分词 + 词频排序）
- 任务驱动的批量内容生成（基于知识库真实信息）
- 人工审核工作流
- WordPress 自动发布（Application Password 认证）
- 提及率定期监测（APScheduler 调度）
- 趋势图 + 邮件通知（变化超阈值）

## 快速开始

### 前置条件

- Docker + docker-compose
- 一个 DeepSeek API key（OpenAI 兼容）

### 启动

```bash
git clone <repo>
cd GEO2
cp .env.example .env
# 编辑 .env，至少填入 DEEPSEEK_API_KEY
docker-compose up --build
```

访问：
- 前端：http://localhost:5173
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs
- **Agent chat 入口**：http://localhost:5173/agent

### 启用开发模式（SSRF 守卫放行 localhost）

```bash
# .env
GEO_ENV=development
```

或在 docker-compose 中加 environment。

## 开发

### 项目结构

```
GEO2/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 入口
│   │   ├── api/             # REST 路由
│   │   │   ├── diagnosis.py # v0.1
│   │   │   ├── knowledge.py, tasks.py, reviews.py  # v0.2
│   │   │   ├── publishers.py, monitors.py, notifications.py  # v0.3
│   │   │   └── agent_sessions.py, agent_chat.py  # v0.4 ← 新
│   │   ├── core/            # 配置 + DB
│   │   ├── domain/          # 业务逻辑
│   │   │   ├── crawler, llm_client, scorer, renderer  # v0.1
│   │   │   ├── knowledge/   # v0.2
│   │   │   ├── generator/   # v0.2
│   │   │   ├── publisher/, monitor/, notification/, security/  # v0.3
│   │   │   └── agent/       # v0.4 ← 新
│   │   │       ├── tools.py
│   │   │       ├── tool_executor.py
│   │   │       ├── react_loop.py
│   │   │       ├── session_manager.py
│   │   │       └── prompts.py
│   │   ├── models/          # Pydantic + SQLAlchemy
│   │   │   └── orm_v04.py   # v0.4 ORM ← 新
│   │   ├── repositories/
│   │   │   └── agent_repo.py  # v0.4 ← 新
│   │   ├── services/        # 编排
│   │   ├── tasks/           # 异步 worker
│   │   └── templates/       # Jinja2 PDF 模板
│   └── tests/
├── frontend/                # React + Vite 前端
│   ├── src/
│   │   ├── pages/           # 路由页面
│   │   │   └── AgentSessionList.tsx, AgentChat.tsx  # v0.4 ← 新
│   │   ├── components/      # 复用组件
│   │   │   └── ChatMessage.tsx, ToolCallCard.tsx, ConfirmDialog.tsx  # v0.4 ← 新
│   │   ├── api/             # API 客户端 + SSE parser
│   │   └── types/           # TypeScript 类型
│   │       └── v0.4.ts      # v0.4 类型 ← 新
│   └── tests/e2e/
├── docs/
│   ├── superpowers/
│   │   ├── specs/           # 设计文档（v0.1-v0.5）
│   │   └── plans/           # 实施计划（v0.1-v0.5）
│   ├── HANDOFF_V0.4.md      # v0.4 启动话术
│   ├── MANUAL_VERIFICATION_V0.4.md
│   ├── ROADMAP.md
│   └── CHANGELOG.md
├── docker-compose.yml
└── .env.example
```

### 后端开发

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -r requirements.txt
pytest -v  # 跑全部测试
```

启动开发服务器：

```bash
uvicorn app.main:app --reload --port 8000
```

### 前端开发

```bash
cd frontend
npm install
npm run dev  # 启动 dev server (端口 5173)
```

类型检查：

```bash
npm run lint
```

E2E 测试：

```bash
npm run test:e2e
```

### 启用 Kimi 作为第二个 LLM

编辑 `.env`：

```bash
KIMI_API_KEY=sk-your-kimi-key
LLM_PROVIDERS=deepseek,kimi
```

重启后端：

```bash
docker-compose restart backend
```

## 文档

### v0.4（当前版本）

- 设计文档：[docs/superpowers/specs/2026-07-10-geo-agent-v0.4-design.md](docs/superpowers/specs/2026-07-10-geo-agent-v0.4-design.md)
- 实施计划：[docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.4.md](docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.4.md)
- 手动验证清单：[docs/MANUAL_VERIFICATION_V0.4.md](docs/MANUAL_VERIFICATION_V0.4.md)
- 启动话术：[docs/HANDOFF_V0.4.md](docs/HANDOFF_V0.4.md)

### 历史版本

| 版本 | 设计文档 | 实施计划 | 手动验证 | 启动话术 |
|---|---|---|---|---|
| v0.1 | [spec](docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md) | [plan](docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md) | [verify](docs/MANUAL_VERIFICATION.md) | [handoff](docs/HANDOFF.md) |
| v0.2 | [spec](docs/superpowers/specs/2026-07-09-geo-agent-v0.2-design.md) | [plan](docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.2.md) | [verify](docs/MANUAL_VERIFICATION_V0.2.md) | [handoff](docs/HANDOFF_V0.2.md) |
| v0.3 | [spec](docs/superpowers/specs/2026-07-10-geo-agent-v0.3-design.md) | [plan](docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.3.md) | [verify](docs/MANUAL_VERIFICATION_V0.3.md) | [handoff](docs/HANDOFF_V0.3.md) |

### 跨版本

- [产品路线图](docs/ROADMAP.md)
- [变更日志](docs/CHANGELOG.md)

## 已知限制

按 ROADMAP 推迟到后续版本：

- ❌ 多用户系统 / 鉴权 / 团队 / 权限（→ v1.0）
- ❌ 写类工具的扩展（增删改知识库 / 创建 v0.2 任务 / 发布 / 监测）—— agent 只读 + 只预览
- ❌ 跨 session 学习 / 用户偏好记忆
- ❌ MCP server 暴露
- ❌ 流式 LLM 输出（v0.4 用 SSE 但 LLM 响应一次性）
- ❌ Voice / 图片 / 文件输入

## 合规说明

本工具**只做诊断、建议、内容生成辅助、发布辅助和监测**，不做内容伪造、AI 投毒等黑帽 GEO 操作。所有建议基于公开方法论，不构成具体法律/财务/医疗建议。

详见设计文档 §9 合规与边界（v0.1） / v0.2 设计 / v0.3 设计 / [v0.4 设计](docs/superpowers/specs/2026-07-10-geo-agent-v0.4-design.md)。

## 许可证

MIT（待定）
