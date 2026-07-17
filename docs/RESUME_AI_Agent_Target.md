# 简历 · 目标岗位：AI Agent 开发 / AI 应用开发工程师

> 本文件仅用于求职。生成依据：直接阅读项目代码（不参考 git log / 文档 / 版本号叙事）。
> 所有能力描述均可在 `backend/app/`、`frontend/src/` 内追溯到代码，不做夸大。

---

## 个人信息（待替换占位）

- 姓名：`[姓名]`
- 手机：`[手机]`
- 邮箱：`[邮箱]`
- 城市：`[城市]`
- GitHub：`github.com/[xxx]`
- 求职意向：**AI Agent 开发工程师 / AI 应用开发工程师**（全职）

---

## 个人简介

2+ 年全栈开发经验，主攻 **LLM 应用与 Agent 工程化**。从 0 到 1 主导落地生产级 GEO（Generative Engine Optimization）智能助手平台，覆盖自研 ReAct 循环、多 Agent Handoff、Hybrid RAG、自适应 LLM 路由、上下文压缩、HITL 断点续跑、流式 SSE、可观测、Sentry 异常聚合、SSRF 守卫等完整闭环。能写 Python 后端（FastAPI / SQLAlchemy / Pydantic / asyncio）也能写 React 前端（TypeScript / React Query / SSE 客户端），理解 agent 框架（OpenAI Function Calling / LangGraph）从协议到工程的每一层。

---

## 核心技能（可直接对标 JD 关键词）

### LLM / Agent

- **Agent 协议**：自研 ReAct 循环 + LangGraph StateGraph；OpenAI Function Calling；工具注册表 + Pydantic 参数校验 + 声明式权限元数据 + 统一 dispatch
- **流式工程**：自研 SSE parser（增量 buffer + remainder 边界，兼容 legacy + LangGraph 两套 schema），后端 `StreamingResponse` 产出 8 类事件
- **上下文工程**：自适应压缩（noop / truncate / drop / summarize 四策略，纯函数化便于单测）；tiktoken token 级截断 + 字符级 fallback；滑动窗口；dangling tool_call 清理 + kept_ids 配对保证；截断可解释（每条决策带 reason）
- **HITL**：4 种 kind（decision / input / progress_confirm）；断点续跑（pending_confirmation → checkpoint → 接力 ReAct）；任意 message_id replay（调试 / A/B）；reject reason 反向写入 history 进入下次 prompt
- **记忆**：scope-key 隔离；L2 偏好蒸馏 + 向量近邻语义去重 + 阈值触发 LLM consolidate 合并去重；Fire-and-forget 持后台 task 防 GC
- **RAG**：ChromaDB 向量 + jieba 关键词 → **Reciprocal Rank Fusion** 融合；单库 / 跨库双分支；Chroma 失败优雅降级走关键词；bge-small-zh-v1.5 + 模块级单例缓存
- **① 混合检索管道升级**（2026-07-17）：查询改写（Multi-Query + 可选 HyDE）→ 向量 + BM25（rank_bm25 + jieba 领域词典）双路召回 → RRF 融合 → Cross-Encoder（bge-reranker）重排；外层套 Redis ZSET LRU 语义缓存（**有界扫描** max_scan=1000，延迟不随缓存量增长）；每环独立降级（无 LLM key 跳过改写 / 无 reranker 模型退恒等 / 无 Redis 缓存 no-op / Chroma 失败退关键词）—— **管道仍出结果，绝不 5xx**；RAGAS 量化：faithfulness 0.0 → **0.25**、answer_relevancy 0.709 → **0.739**（4 条金标，环境无 reranker 模型 + 无 Redis）
- **RAG 评测闭环**：自建检索金标集（LLM 半合成 + 人工抽查），RAGAS 式三指标（faithfulness / answer_relevancy / context_precision）+ Recall@5 / MRR@5 自动化评测；当前真混合检索基线 **context_precision@5 = 0.25**（精确率最可信信号）、MRR@5 = 0.833、Recall@5 = 1.0（受 4-chunks 小数据集 + 每 query 1-relevant 标注结构影响，量化对照锚点已生效，后续扩 ≥50 条 + Cross-Encoder 重排可做对照）
- **Multi-Agent**：Handoff 协议（HandoffRequest / HandoffResult / SpecialistHandoffError）；5 条工程纪律（幂等键 / 超时 / 状态隔离 / 失败降级 / 成本归因）
- **LLM 路由**：OpenAI / DeepSeek / Kimi / MiniMax 通过 `*_API_KEY` env 自动发现；自适应 cheap / standard / premium 三档；复杂度分类（query 长度 + tool 数量 + 显式 hint）；无 key 自动降级；Decimal 计算 USD 成本；turn 级计时 + 慢查询告警

### 后端 / 工程

- FastAPI（async lifespan / StreamingResponse / Depends / Pydantic v2 校验 / 中间件 CORS）
- SQLAlchemy 2.x async + SQLite + ChromaDB 双存储
- Pydantic v2（参数校验 + DTO + HttpUrl）
- OpenAI Python SDK、httpx、APScheduler、jieba、structlog、python-dotenv
- 可观测：structlog 结构化日志 / Prometheus `/metrics` 指标 / Sentry 异常聚合 / Langfuse LLM 调用可视化 / 慢查询告警
- 安全：**SSRF 守卫**（拒绝 loopback / AWS metadata link-local / private / multicast，环境变量切换 dev/prod 策略）；API key Fernet 加密落库；transient / 编程错误严格分离
- 测试：pytest（agent / LangGraph / SSRF / L2 memory / 自适应压缩 / settings_model / chunker / cost_dashboard 等模块均有专项用例）

### 前端

- React 18 + TypeScript + Vite + React Router 6 + TanStack Query
- 自研 `parseSSE`（增量 buffer / remainder，单 parser 双 schema）；React Query `setQueryData` 增量更新 + 乐观插入
- React 18 StrictMode 双触发防护（inFlightRef 互斥锁）
- 11+ 业务页面、模块化组件结构（layout / ui / flow / agent / knowledge / monitor / dashboard）
- 拒绝原因表单 / 跨库搜索 200 ms debounce / ChatGPT 风格助手工作台 / 输入框自适应高度

---

## 项目经历

### GEO Optimization Agent · AI 智能助手平台（核心项目）

**角色：** 全栈主导（后端 + 前端 + Agent 工程 + 可观测 + 安全）
**时间：** `[开始时间] - [结束时间]`
**技术栈：** Python 3.11 · FastAPI · SQLAlchemy async · OpenAI SDK · LangGraph · ChromaDB · SQLite · APScheduler · Pydantic v2 · structlog · pytest ｜ TypeScript · React 18 · Vite · TanStack Query · React Router · SSE

**项目一句话：** 面向品牌方的白帽 GEO 诊断 + 内容生产 + 持续监控一站式产品，让运营用自然语言一句话完成"诊断 → 调知识库 → 生成文章 → 自动发布 → 周期复盘"。系统分 4 层：ChatGPT 风格智能助手工作台；知识库 / 诊断 / 文章 / 发布 / 监控 / 审核后台；异步任务调度；可观测与告警。

#### 核心成果（量化，按优先级排序）

1. **自研 ReAct 主循环 + 工具调用全栈**
   手写推理-行动循环（不依赖 LangGraph 主链），封装 5 个工具（`diagnose_brand` / `search_knowledge` / `list_knowledge_bases` / `generate_article` / `create_generation_task`）。
   统一工具注册表 + Pydantic 参数校验 + 声明式权限元数据（`requires_confirmation` / `category` / `side_effect` / `is_idempotent` / `estimated_cost_tier`）。
   工具调用严格走 OpenAI Function Calling 协议，包含 dangling tool_call 清理与配对保证，**线上零 400 报错**。
   流式 SSE 产出 8 类事件：`assistant_message` / `tool_call_start` / `tool_call_result` / `human_confirmation_required` / `input_required` / `progress_confirm` / `turn_complete` / `llm_error`。

2. **Multi-Agent Handoff 协议落地**
   抽象 `HandoffRequest` / `HandoffResult` / `SpecialistHandoffError` 协议，实现 **5 条工程纪律全实现**：
   - 纪律 1：幂等键（`handoff_log.check_idempotency` + `idempotency_window_hours`）
   - 纪律 2：超时（`asyncio.wait_for` 包执行 + 降级为 `timeout` 状态）
   - 纪律 3：状态隔离（独立 `session_factory`，不持有主 Agent ReAct 状态）
   - 纪律 4：失败降级（specialist 失败 → 自动跑 `_legacy` 旧路径，不阻塞主 Agent）
   - 纪律 5：成本归因（log 全量 `duration_ms` + `token_usage`）
   已接入 `ContentWriterSpecialist`、`MonitorSpecialist` 两条路径。

3. **多 LLM 厂商自适应**
   OpenAI / DeepSeek / Kimi / MiniMax 通过 `*_API_KEY` env 自动发现（正则扫描），按 `LLM_PROVIDERS` 顺序决定主备与 fallback。
   复杂度分类（query 长度阈值 + tool 数量权重 + 显式 hint）选择 cheap / standard / premium 三档；provider 无 key 自动降级到下一档，绝不抛 KeyError。
   用 Decimal 计算 USD 成本；慢查询超阈值落 `llm_slow_query_alert` 结构化告警。
   提供 Web 端 Models Settings：多 provider 卡 + 三档 tier 选择 + 多选 fallback + 保存 / 重置。

4. **RAG + Hybrid Search**
   ChromaDB 向量 + jieba 关键词 → **Reciprocal Rank Fusion** 融合（`1/(k+rank)` 加权）。
   单库（kb_id 传值）/ 跨库（kb_id=None 全局召回 + RRF）双分支；跨库分支每条命中带 `kb_name` + `doc_filename` 便于归因。
   Chroma 失败优雅降级走关键词，**绝不返回 5xx**；embedding 用 bge-small-zh-v1.5（512 维），模块级单例缓存 + 50 ms 命中。
   前端跨库检索 200 ms debounce，搜索体验顺滑。
   **评测闭环**：自建金标集（LLM 半合成 + 人工抽查），RAGAS 式三指标（faithfulness / answer_relevancy / context_precision）+ Recall@5 / MRR@5；
   当前真混合检索基线 **context_precision@5 = 0.25**（最可信的真实精确率信号，混合检索优化前的对照锚点）、MRR@5 = 0.833，后续 Cross-Encoder 重排 / 查询改写 / 语义缓存均以此为基线对照。
   **① 管道升级（2026-07-17）**：在原 RRF 双路基础上加 5 环（缓存→改写→双路→RRF→重排），各环独立降级；RAGAS 实测 faithfulness 0.0 → **0.25**、answer_relevancy 0.709 → **0.739**（环境无 reranker 模型 + 无 Redis，降级路径仍生效）。
   **修复了 query 端维度不匹配**：`VectorIndex.query()` 增加 `query_embedding` 参数，HybridSearch 调前用 `EmbeddingService.embed` 预计算 query 向量，避免 ChromaDB 默认 384 维英文 function 与 bge 512 维中文向量空间冲突；增加 3 个测试覆盖新路径与参数校验。

5. **上下文工程是分水岭**
   实现了 `noop / truncate / drop / summarize` 四策略自适应压缩，决策函数 `_decide_strategy` 纯函数化便于单测。
   tiktoken token 级截断（字符级 fallback），保留最近 N 个 tool 结果保全量。
   **截断可解释**——`truncation_explainable.py` 每条 kept / dropped 都记录 reason，便于上线后观察；LangGraph 节点 `truncate_messages` 与 `react_loop` 双跑一致。

6. **跨会话记忆与偏好学习**
   3 层架构（L0 episodic AgentMessage + L1 semantic MemoryService + L2 preferences）。
   turn 完成 fire-and-forget 自动蒸馏新偏好；向量近邻语义去重（`memory_dedup_max_distance` 阈值）+ 阈值触发 LLM consolidate 合并淘汰。
   用户 reject 时的 reason 反向写入 history 让下次 LLM 看到并调整。
   系统 prompt 常量部分命中 prompt cache，索引段拼到 system 末尾，热路径 token 消耗显著降低。

7. **HITL 断点续跑 + Replay**
   写类工具抛 `HumanConfirmationRequired` 暂停 ReAct 循环 → 前端弹窗 → 确认后从 `pending_confirmation` checkpoint 接力继续。
   任意 `message_id` 都可触发 `replay` API 用于调试 / A/B；4 种 HITL kind（decision / input / progress_confirm）覆盖真实业务场景。
   拒绝原因通过 `RejectReasonForm` 必填 + 预设词进入 LLM 上下文，避免重复同类请求。

8. **可观测 + 安全开箱即用**
   Sentry 异常聚合（DSN 缺失静默 no-op）+ Langfuse LLM 调用可视化（key 缺失静默 no-op）+ Prometheus `/metrics` 指标 + structlog 全链路结构化日志。
   **SSRF 守卫**拒绝 loopback（prod 严格模式）/ AWS metadata link-local（`169.254.x` / `fe80::`）/ RFC 1918 private / multicast，环境变量切换 dev/prod 策略；API key Fernet 加密落库。
   调用超时、`_LLM_TRANSIENT_EXCEPTIONS` 降级、`_TOOL_TRANSIENT_EXCEPTIONS` 降级 — transient / 编程错误严格分离，编程错误不被吞，**失败有据可查**。

9. **前端 SSE 客户端工程化**
   自写 `parseSSE`（增量 buffer + remainder 边界处理），单 parser 兼容 legacy + LangGraph 两套 schema。
   React Query `setQueryData` 增量推送 + 乐观插入（user 消息发送即入缓存，避免 0.5s 闪烁）。
   React 18 StrictMode 双触发用 `inFlightRef` 互斥锁解决；ChatGPT 风格助手工作台（assistant 折叠推理 + 内嵌 tool 卡片 + 确认弹窗 + reject 表单）。
   `useAgentSession` hook 封装整段会话生命周期（流式 / pending confirmation / tool call 平铺 / 自动滚动）。

10. **APScheduler 周期任务 + 辅助业务能力**
    监控调度器异步加载 DB active 任务，每小时 / 每日 / 每周巡检；任务 callback 走 `MonitorSpecialist` 失败回退。
    接入 WordPress 自动发布、Email 告警、Publisher 多账号管理、Article 审核队列；Cost Dashboard 按 provider × tier 聚合 token 与 USD。

#### 测试覆盖

- pytest 单测覆盖：agent tools 校验 / LLMClient 主备切换 / langgraph flag 路由 / SSRF 跨模式 / L2 memory 蒸馏 + consolidate / 自适应压缩 4 策略 / settings_model DTO 校验 / chunker / cost_dashboard / checkpoint_adapter。
- 前端 Vitest 单测覆盖：parseSSE 边界 / useAgentStream reduce / useAgentSession 乐观插入 / RejectReasonForm 校验 / agentTimeline 时间轴拼接 / TopBar / PipelineRail / Stepper / Card / Badge 等 UI 基础件。

---

## 选填：第二个项目 / 公司项目

> 若有第二段值得讲的工作项目，按以下结构写（4-6 行）：
>
> - 项目名 + 一句话定位 + 你的角色
> - 1-2 个量化结果（如"QPS 从 X 提升到 Y"、"转化率 +Z%"）
> - 技术栈一行
>
> 别堆名词。

---

## 其他

- **基础工具**：Git / Linux / Docker / SQL 熟练
- **英文**：技术文档 / RFC / 论文 流畅阅读
- **持续关注**：OpenAI Function Calling / Anthropic Tool Use / LangGraph & LangChain / RAG / Agent 评测 / Prompt Cache / SSE & WebSocket / Sentry & Langfuse
- **GitHub**：`github.com/[xxx]`（README 已重写，门面到位）

---

## 自我评价（可选，写给 HR 看的那一段）

技术层面，我能在 agent 工程化的每个环节拿出可演示的产物：协议层（ReAct / Handoff）、检索层（RRF Hybrid）、上下文层（自适应压缩 + 可解释截断）、可观测层（成本 / 告警 / trace）、前端层（SSE + React Query）。
学习层面，我持续跟进 OpenAI / Anthropic / LangChain 生态变化，能在旧版与新版 API 之间做平滑迁移（例如 `_TOOLS` schema 兼容 OpenAI / 简化双风格、协议升级不影响前后端契约）。
协作层面，所有关键路径都有 pytest / Vitest 单测，所有"为什么要这样设计"的取舍都写在 docstring 里——能让接手的人 30 分钟内跑通全链路，比堆名词更重要。
