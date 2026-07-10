# 变更日志

记录 GEO Optimization Agent 每个版本的变更。格式基于 [Keep a Changelog](https://keepachangelog.com/)。

## [v0.6] - 2026-07-10 (进行中)

### 方向变更

- 定位从「GEO 诊断 Agent」调整为「**GEO 优化系统**」 —— 一个 6 阶段 GEO 优化操作系统（诊断 → 生成 → 审核 → 发布 → 监测 → 跟踪）
- v0.6 实际定位:前端全面 UI/UX 重设计,核心新增**流程可视化**与**智能感强化**

### Phase 0 已完成 (本 PR)

- **设计令牌**:`src/lib/tokens.ts` 单源真理 + CSS variables + Tailwind extend (Teal `#0D9488` + Orange `#EA580C` + Inter 字体)
- **测试基建**:vitest + @testing-library/react + axe-core/playwright
- **15 个公共组件**:Button / Input / Select / Textarea / Spinner / FieldWrapper / Card / Badge / EmptyState / Modal / Drawer / ConfirmDialog / Skeleton / Tooltip / Tabs / Accordion / Stepper (`src/components/ui/`)
- **6 个流程可视化组件**:StageCard / LiveSignal / RankBadge / KnowledgeChunkCard / MentionMatrix / ReasoningTrace (`src/components/flow/`)
- **Layout Shell 基础**:TopBar (新 Logo + brand) + SideNav (7 组 IA) + Breadcrumb + LayoutShell (含 context pane 槽位) + PipelineRail (6 节点全局底栏, P0 stub 状态)
- **App 接入**:`src/App.tsx` 改为 LayoutShellRouter,19 个旧路由全部保留,新增 `/settings` 占位
- **62 个单测 + e2e (LayoutShell + a11y)**:全过

### Phase 0 不做 (留给 P1+)

- 真实 `usePipelineState` 数据接入 (P0 stub 全 pending)
- 各 page 内部使用新组件重写
- dark mode (接口预留但不发布)
- `/settings` 实际实现
- 流式 LLM token-by-token 输出

### 风险

- 旧 page 内部仍使用 `bg-blue-600` / `text-gray-900` 等与新 token 不一致的硬编码；视觉"新旧混搭"直到 P1-P5 渐进替换
- 旧 `Header` 已删除 (集成进 LayoutShell)

## [v0.5] - 2026-07-10

### 方向变更

- 原 ROADMAP v0.5 "竞品对比 + 行业基准" → 推迟到 **v0.6+**
- v0.5 实际定位:**向量检索升级**(bge + ChromaDB + RRF 混合)
- 原因:召回率从 ~70% → ~90% 是基础设施改进,让 v0.4 agent 透明升级

### 新增(Added)

- **Embedding 服务**:`app/services/embedding.py`(bge-small-zh-v1.5,class-level 缓存,懒加载)
- **VectorIndex**:`app/domain/knowledge/vector_index.py`(ChromaDB 嵌入式封装,每个 KB 一个 `kb_{kb_id}` collection,cosine 距离)
- **HybridSearch + RRF**:`app/services/hybrid_search.py`(关键词 + 向量双路召回,RRF k=60 融合,任一异常降级到纯关键词)
- **ReindexService**:`app/services/reindex.py`(启动时 lazy 向量化,只处理缺失或 `pending_index=True` 的 chunks,幂等;**启动时也清理孤儿 ChromaDB 向量**)
- **增量同步(spec §7)**:
  - `knowledge_chunks.pending_index: Boolean` 字段(标记同步失败)
  - `KnowledgeRepository.mark_chunks_pending` / `list_chunk_ids_for_doc` / `list_chunks_for_doc` 辅助方法
  - `parser_worker.py` 解析成功后调 `VectorIndex.add_chunks`(传预计算 embeddings);失败时 mark pending
  - `api/knowledge.py` DELETE 文档路由调 `VectorIndex.delete_chunks`;失败仅 warning 不破坏 API
  - `init_db()` 加 in-place 迁移:`ALTER TABLE knowledge_chunks ADD COLUMN pending_index`(幂等)
- **v0.4 agent 工具升级**:`tool_executor._execute_search_knowledge` 内部从 `search_chunks_by_keyword` 改为 `search_chunks_hybrid`,API 形状不变(返回多带 `rrf_score` / `sources` 字段)
- **FastAPI lifespan 钩入**:`main.py` 在 `load_all_monitor_tasks` 后调 `ReindexService().reindex_all()`,日志 `v0.5_reindex_done`
- **6 个新 settings**:`chroma_path` / `models_cache_dir` / `embedding_batch_size` / `hybrid_top_k_vector` / `hybrid_top_k_keyword` / `hybrid_rrf_k`
- **Dockerfile**:`COPY data/models /app/data/models`(bge 模型 gitignore,Docker 构建时 COPY)

### 依赖(Dependencies)

- 新增 `chromadb==0.5.20`(嵌入式向量库)
- 新增 `sentence-transformers==3.2.1`(embedding 模型加载,首次安装 ~300MB 含 torch CPU)
- 模型文件 `BAAI/bge-small-zh-v1.5`(~95MB,缓存到 `./data/models/`,gitignore)

### 数据存储(Data)

- 新增 `./data/chroma/`(ChromaDB 持久化,gitignore)
- 新增 `./data/models/`(bge 模型,gitignore)
- 现有 Docker 卷需挂载这两个新目录

### Review 修复(Review Fixes)

- **R1**:`VectorIndex.add_chunks` 强制要求 `embeddings` 参数(避免 ChromaDB 默认英文 embedding 错模型,bug 严重)
- **R2**:`ReindexService` 显式读 `pending_index=True` 触发 reindex(符合 spec §7.2/§9 语义)
- **R5**:`parser_worker` 只 mark 本批 NEW chunks 为 pending(重解析不污染已成功索引的旧 chunks)
- **R6**:`ReindexService` 走 `VectorIndex.add_chunks` 封装(不再直接 `index._collection.add(...)`)
- **R7**:`ReindexService` 清理孤儿 ChromaDB 向量(SQLite 没有但 ChromaDB 仍有的旧向量,来自失败的 DELETE 文档路径)
- **R10**:v0.5 新增 7 个测试文件 docstring 翻译成中文(plan 规范)
- **R11**:`parser_worker` 用 `list_chunks_for_doc(doc_id)` 精确查询(避免 `list_chunks(kb_id)` 全表扫)

### 测试(Tests)

- 后端 **406 个测试全过**(v0.5 实施 402 + review 修复新增 4)
- 新增 9 个测试文件:
  - `test_embedding.py`(4 tests,EmbeddingService)
  - `test_vector_index.py`(10 tests,VectorIndex 含 embeddings 必传校验)
  - `test_hybrid_search.py`(8 tests,RRF 融合 + 降级)
  - `test_reindex.py`(5 tests,含 pending_index 显式读 + 孤儿清理)
  - `test_knowledge_repo.py` 新增 1 个 hybrid test
  - `test_tool_executor.py` 新增 1 个 hybrid 集成 test
  - `test_pending_index_v05.py`(3 tests,迁移幂等)
  - `test_api_knowledge_v05.py`(4 tests,spec §7 钩子)
  - `test_startup_v05.py`(1 test,lifespan reindex 钩子)
  - `test_e2e_v05.py`(4 tests,语义匹配 + 双路命中)

### 手动验证(Manual Verification)

- 7 个手动场景:`docs/MANUAL_VERIFICATION_V0.5.md`
  1. 混合检索召回率提升
  2. 启动时 lazy 向量化
  3. 新增文档自动向量化
  4. 删除文档级联清理
  5. ChromaDB 不可用时降级
  6. 单次 hybrid search < 500ms
  7. v0.4 agent 工具升级

### 不变 / 用户无感知

- ✅ **前端不变** — 透明升级,无新页面
- ✅ **API 路径不变** — 仅 `_execute_search_knowledge` 内部实现改变
- ✅ **v0.2 现有数据兼容** — `pending_index` 字段默认 0,旧 DB 自动 ALTER 加上

### 已知限制(已知推到 v0.5.x / v0.6+)

- ❌ cross-encoder rerank → v0.5.1(准确率 +10-15%)
- ❌ HyDE → v0.5.2(召回率 +5-10%)
- ❌ query rewriting → v0.5.3(召回率 +5%)
- ❌ 行业基准 / 竞品对比 → v0.6+
- ❌ SPA 爬虫 → v0.6+

### ROADMAP 调整

- 原 v0.5(竞品对比 + 行业基准)→ 推迟到 **v0.6+**
- 原 v0.6 向量检索(pgvector 计划)→ 提前到 v0.5,改为 ChromaDB 嵌入式(更轻、不引独立服务)

---

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
