# 变更日志

记录 GEO Optimization Agent 每个版本的变更。格式基于 [Keep a Changelog](https://keepachangelog.com/)。

## [v0.4] - 2026-07-10

### 新增（Added）

- **自主决策 Agent 层**：在 v0.1-v0.3 之上加自然语言入口
- **3 个 Agent 工具**：
  - `diagnose_brand`（读，包装 v0.1 诊断）
  - `search_knowledge`（读，包装 v0.2 知识库，chunk 截断 500 字）
  - `generate_article`（写，包装 v0.2 ContentWriter，**仅预览不落库**）
- **ReAct 推理循环**：自写循环（不引 LangGraph/LangChain），`MAX_REACT_ITERATIONS = 5`
- **Human-in-the-loop**：写类工具（generate_article）需用户确认
- **断点续跑**：confirm 端点 approved=True 后自动从断点续跑（不是 MVP）
- **SSE 流式响应**：FastAPI `StreamingResponse` + 前端 `fetch + ReadableStream`
- **多 session + 历史**：所有会话持久化到 SQLite，跨刷新可恢复
- **SSRF 守卫**：URL 拒绝内部 IP（`GEO_ENV=development` 放行 localhost）

### 后端新增

- `app/domain/agent/{tools,tool_executor,react_loop,session_manager,prompts}.py`
- `app/repositories/agent_repo.py`（session + message CRUD）
- `app/api/{agent_sessions,agent_chat}.py`（7 个端点：5 CRUD + 1 SSE chat + 1 confirm）
- `app/models/{agent,orm_v04}.py`（Pydantic + 2 张新表）
- `app/domain/security/ssrf.py`（URL 校验器，24 个测试）

### 后端修改

- `app/domain/llm_client.py`：新增 `chat_with_tools()`（Function Calling）+ `simple_chat()`（自动生成标题）
- `app/domain/exceptions.py`：新增 `HumanConfirmationRequired`
- `app/main.py`：注册 2 个新 router
- `backend/tests/conftest.py`：顶层 import `app.models.orm_v04` 让 Base.metadata 注册新表

### 前端新增

- `src/types/v0.4.ts`：AgentSession / AgentMessage / AgentSessionDetail / AgentEvent
- `src/components/ChatMessage.tsx`：4 种 role 的消息渲染
- `src/components/ToolCallCard.tsx`：工具调用 + 结果展示
- `src/components/ConfirmDialog.tsx`：写类工具确认弹窗
- `src/pages/AgentSessionList.tsx`：会话列表
- `src/pages/AgentChat.tsx`：SSE 消费 + 工具卡 + 确认弹窗

### 前端修改

- `src/App.tsx`：加 `/agent` 和 `/agent/:sessionId` 路由 + 导航
- `src/api/client.ts`：加 6 个 API 方法 + 2 个 SSE parser 辅助函数

### 测试

- 后端 17 个测试文件，~110 个 v0.4 测试（tools / executor / react_loop / session_manager / repo / api / E2E / SSRF）
- 前端 `tsc --noEmit` 0 errors
- 后端 387 个测试总通过（含 v0.1-v0.3 + v0.4）

### 文档

- 设计文档：`docs/superpowers/specs/2026-07-10-geo-agent-v0.4-design.md`
- 实施计划：`docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.4.md`（22 个 task）
- 手动验证清单：`docs/MANUAL_VERIFICATION_V0.4.md`（8 个场景）
- 启动话术：`docs/HANDOFF_V0.4.md`
- 18 个实施 commit + 1 个 code review 修复 commit

### 修复（Code Review 修复）

- `ToolExecutor._execute_generate_article_confirmed` 真正实现（之前是 `NotImplementedError` 占位）
- `tool_call_id` 匹配：resume 时用 `checkpoint_message_id`（与 assistant 消息的 tool_calls.id 一致）
- 后端去重 `confirm_message`：API 层已确认，删除 react_loop 内的重复调用
- 前端 approve 改 SSE：删除 JSON `useMutation` + 双请求

### 路线图调整

- 原 v0.4（多用户 + 权限）→ 推迟到 **v1.0**
- 原 v0.5（行业基准）→ 仍为 v0.5
- 原 v0.6（Agent 化）→ 提前到 v0.4 完成

---

## [v0.3] - 2026-07-10

### 新增（Added）

- **WordPress 发布器**：自动发布改写后的内容（Application Password 认证）
- **改写效果监测**：发布后定期（每天/每周/每小时）抓 AI 答案，监测提及率变化
- **变化趋势图**：同一监测任务多次快照的折线图（Recharts）
- **邮件通知**：监测到显著变化（默认 15% 阈值）+ 发布成功/失败时主动通知
- 凭证加密：Fernet 加密 WordPress app_password

### 后端新增

- 4 张表：`publisher_configs` / `publish_jobs` / `monitor_tasks` / `mention_snapshots`
- `app/domain/publisher/{wordpress.py, publisher_service.py}`
- `app/domain/monitor/{scheduler.py, monitor_service.py}`
- `app/domain/notification/{email_sender.py, notification_service.py}`
- `app/domain/security/encryption.py`
- `app/tasks/publish_worker.py`（共享 `_EXEC_LOCK` with v0.1/v0.2）
- `app/api/{publishers.py, monitors.py, notifications.py}`
- APScheduler 调度（lifespan 启动时从 DB 恢复 active 监测）
- aiosmtplib 邮件发送

### 前端新增

- 7 个页面 + 7 个组件：PublisherConfig / PublishList / MonitorList / MonitorDetail / NewMonitor / NotificationSettings / TrendChart

### 文档

- 22 个 task 实施计划
- 11 个场景手动验证清单

---

## [v0.2] - 2026-07-09

### 新增（Added）

- **知识库管理**：上传 PDF / Word / MD / TXT 文件，自动解析 + 切片 + 入库
- **关键词检索**：jieba 分词 + 词频排序召回 top-k 切片
- **任务调度**：选知识库 + 主题 + 关键词 + 文章数，Worker 异步生成
- **AI 生成**：基于知识库真实信息生成 Markdown 文章，强制"不得编造"
- **人工审核**：审核队列（批准 / 拒绝带理由 / 标记需修订）
- v0.1 → v0.2 入口：报告页一键"基于此诊断创建生成任务"，品牌名预填

### 后端新增

- 5 张表：`knowledge_bases` / `knowledge_documents` / `knowledge_chunks` / `tasks` / `articles`
- `app/domain/knowledge/`（parser / chunker / retriever）
- `app/domain/generator/`（prompt_builder / content_writer）
- `app/tasks/parser_worker.py` + `app/tasks/task_worker.py`（单飞锁）
- `app/api/{knowledge.py, tasks.py, reviews.py}`

### 前端新增

- 7 个页面：KnowledgeList / KnowledgeDetail / TaskList / NewTask / TaskDetail / ReviewQueue / ReviewArticle

### 文档

- 26 个 task 实施计划
- 8 个场景手动验证清单

---

## [v0.1] - 2026-07-09

### 新增（Added）

- **官网爬虫**：Schema / EEAT / 结构 / 新鲜度检测
- **AI 平台实测**：DeepSeek / Kimi 提及率检测
- **5 维度评分卡**：权威度 / 内容相关性 / 结构 / 更新频率 / 数据可验证性
- **优化建议清单**：基于评分自动生成 P0/P1/P2 建议
- **网页报告 + PDF 下载**：WeasyPrint 渲染

### 后端技术栈

- FastAPI 0.115+ 单体 + asyncio 后台任务 + SQLite
- OpenAI SDK 兼容 DeepSeek / Kimi
- jieba 分词、WeasyPrint PDF、structlog 日志

### 前端技术栈

- React 18 + TypeScript + Vite + Tailwind + Recharts

### 文档

- 28 个 task 实施计划
- 4 个场景手动验证清单
- 设计文档

---

## 维护说明

- 每个版本完成后，CHANGELOG 立即更新
- 按 ROADMAP "文档演进规则"维护 ROADMAP + HANDOFF + README + CHANGELOG 四件套
- Conventional Commits 提交规范：feat / fix / test / chore / docs / refactor
- 详细历史通过 `git log --oneline` 查阅
