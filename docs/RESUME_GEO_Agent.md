# 简历项目描述 — GEO 优化 Agent

> 面向 AI / Agent 开发岗。基于仓库证据撰写，未编造指标、用户规模、自研模型能力或未实现的功能。
>
> **更新记录**：v2 — 合并 v0.6 P1.6 未提交改动，新增「推理模型适配」段，重写「写工具与人机协同」段反映后台异步重构。

---

## 证据分析

**证据来源（按优先级）**

- 一级（直接文档 / 配置）：`README.md`、`docs/CHANGELOG.md`、`docs/HANDOFF_V0.6.md`、`backend/requirements.txt`、`backend/Dockerfile`、`docker-compose.yml`、`frontend/package.json`、`.env.example`、`backend/app/core/config.py`
- 二级（代码组织与核心实现）：`backend/app/domain/agent/{react_loop,tool_executor,tools,prompts,session_manager}.py`、`backend/app/services/{embedding,hybrid_search,reindex}.py`、`backend/app/domain/generator/{content_writer_agent,system_prompts}.py`、`backend/app/api/agent_chat.py`、`backend/tests/test_content_writer_agent.py`、`backend/tests/test_tool_executor.py`
- 三级（基于版本演进表的合理推断）：v0.1 → v0.6 P1.6 说明项目从单功能诊断演进到完整 Agent 平台

**角色契合度判断**

- 强证据：
  - 自写 ReAct 推理循环 + OpenAI Function Calling + 5 工具调度、Pydantic 工具参数校验
  - **Human-in-the-loop 断点续跑（v0.4 旧路径，已演进为 opt-in）+ 写工具统一后台异步（v0.6 P1.6 新默认）**
  - **推理模型适配（DeepSeek-R1 / MiniMax 等）：静态 `_strip_think_blocks` 正则剥离 + 流式三态状态机（before_think / in_think / after_think）+ 7 字符回看缓冲，正确处理 `<think>...</think>` 块跨 chunk 切断**
  - bge-small-zh-v1.5 + ChromaDB + jieba + RRF 混合检索、跨库召回、降级策略、增量向量化
  - SSE 流式事件（Agent）+ ContentWriter 流式生成（带 think 块剥离）
  - 多 session 历史持久化、APScheduler 后台 worker、WordPress 发布、提及率阈值邮件告警
- 中证据：system_prompts 显式禁止 think 块外泄与文末信源列表污染（双层防御）、pytest + vitest + Playwright E2E、test_content_writer_agent.py 102 行新增测试覆盖 think 块剥离
- 保守边界（不写进简历）：未做模型训练 / 微调；不做 MCP server 暴露、跨 session 学习、多用户 / 权限（README 明示推迟到 v1.0）；LLM 响应非真正流式（SSE 仅承载 agent 事件，但 ContentWriter 本身支持真流式）；无可引用的用户规模 / 性能指标

**项目定位一句话**：面向品牌"生成式引擎优化"（GEO）的 AI Agent 平台，串起诊断、知识库 RAG、内容生成、自动发布、提及率监测的完整闭环；适配 DeepSeek-R1 / MiniMax 等推理模型。

---

## 简历版最终描述（完整版）

### GEO 优化 Agent（v0.1 → v0.6 P1.6）

面向品牌 GEO（生成式引擎优化）的 AI Agent 平台，对接 DeepSeek / Kimi 等 OpenAI 兼容 LLM（含 DeepSeek-R1 / MiniMax 等推理模型），提供自然语言入口完成诊断 → 检索 → 内容生成 → 审核发布 → 监测的端到端闭环。

- **Agent 编排**：自写 ReAct 推理循环（最大 7 步），通过 OpenAI Function Calling 协议调度 5 个工具（品牌诊断 / 知识库检索 / 单篇生成 / 列出知识库 / 批量生成任务）；用 Pydantic 模型对工具参数做强校验，按"只保留有配对 tool 结果的 tool_call_id"策略保证多 provider 兼容。
- **RAG 与混合检索**：基于 bge-small-zh-v1.5（512 维，本地 sentence-transformers）+ ChromaDB 构建每知识库一个 collection 的向量索引；与 jieba 关键词召回并行，通过 Reciprocal Rank Fusion（k=60）融合；任一链路失败自动降级到纯关键词召回；同时支持单库与跨库（v0.6 P1.3）两种召回路径。
- **推理模型适配**：ContentWriterAgent 适配 DeepSeek-R1 / MiniMax 等带 `<think>...</think>` 推理块输出的模型——静态路径用 `_strip_think_blocks` 正则一次性剥离；流式路径用三态状态机（`before_think → in_think → after_think`）+ 7 字符回看缓冲，正确处理 think 块跨 chunk 切断的情形，避免推理过程被当作正文落库；`system_prompts` 同时显式禁止模型在正文写出 think 块（双层防御）。
- **写工具与人机协同（v0.6 P1.6 重构）**：写类工具从"抛 HumanConfirmationRequired 暂停 ReAct → 流式预览 → 用户确认"演进为"默认直接落 v0.2 Task 表 + 触发后台 worker → 立即返回 task_id"，与批量生成任务复用同一套路径，避免流式卡顿；Human-in-the-loop 路径（`_execute_generate_article_confirmed` + `run_agent_turn_from_checkpoint`）保留为 opt-in，确认消息以 `pending_confirmation` 落库后从 checkpoint 续跑剩余推理步。
- **流式与持久化**：FastAPI `StreamingResponse` + 前端 `fetch + ReadableStream` 推送结构化 SSE 事件（assistant_message / tool_call_start / tool_call_result / human_confirmation_required / turn_complete 等）；ContentWriter 自身支持流式生成并在前端实时显示；多 session 历史全部持久化到 SQLite，跨刷新可恢复。
- **检索增强生成与发布闭环**：ContentWriter 把检索 chunk 注入 prompt 作为"不得编造"约束，支持中性 / 专业 / 口语三种风格与字数控制；批量生成走 APScheduler 后台 worker，前端通过任务详情页审核 → WordPress 发布 → 提及率定期监测，超阈值 SMTP 邮件告警。
- **工程化**：bge 模型在启动期 lazy 向量化 + 上传 / 删除钩入 ChromaDB 实现增量同步，失败标记 `pending_index` 待下次重启补齐；`test_content_writer_agent.py` 102 行新增测试覆盖 think 块静态剥离与流式跨 chunk 切断；`test_tool_executor.py` 覆盖后台异步与 Human-in-the-loop 双路径；pytest + vitest + Playwright E2E 覆盖 agent 循环、工具执行、混合检索等关键路径。

**技术栈**：RAG（bge-small-zh-v1.5 + ChromaDB + jieba + RRF 融合）、ReAct Agent + OpenAI Function Calling、推理模型适配（think 块剥离 + 流式状态机）、FastAPI（SSE）/ Pydantic / SQLAlchemy async / APScheduler、OpenAI 兼容 LLM（DeepSeek / DeepSeek-R1 / Kimi / MiniMax）、React 18 + TypeScript + Vite + Tailwind + Radix UI + Playwright、Docker / docker-compose

---

## 精简版（投递一页纸简历 / 候选人系统时使用）

### GEO 优化 Agent

面向品牌 GEO（生成式引擎优化）的 AI Agent 平台，串联"诊断 → RAG 检索 → 内容生成 → 审核发布 → 提及率监测"端到端闭环；6 个版本持续演进至 v0.6，对接 DeepSeek / Kimi / DeepSeek-R1 等 OpenAI 兼容 LLM。

- **Agent 编排**：自写 ReAct 循环（7 步上限）+ OpenAI Function Calling 调度 5 个工具，Pydantic 强校验参数，按"配对 tool_call_id"策略兼容多 provider。
- **RAG 混合检索**：bge-small-zh-v1.5 + ChromaDB + jieba 双路召回，RRF（k=60）融合，支持单库 / 跨库，任一链路失败自动降级。
- **推理模型适配**：ContentWriter 用正则 + 流式三态状态机（`before_think → in_think → after_think`）+ 7 字符回看缓冲剥离 DeepSeek-R1 等模型的 `<think>...</think>` 推理块，避免跨 chunk 切断污染正文。
- **写工具与人机协同（v0.6 P1.6）**：写类工具默认走后台异步（落 v0.2 Task 表 + 触发 worker + 立即返回 task_id），与批量任务复用同一套路径；Human-in-the-loop 路径保留为 opt-in，确认后从 `pending_confirmation` checkpoint 续跑。
- **流式与持久化**：FastAPI SSE 推送结构化事件 + ContentWriter 流式生成；多 session 历史入 SQLite；启动期 lazy 向量化 + 上传删除钩入 ChromaDB 实现增量同步，失败待重启补齐。

**技术栈**：RAG（bge + ChromaDB + jieba + RRF）、ReAct Agent + Function Calling、推理模型 think 块剥离、FastAPI SSE / Pydantic / SQLAlchemy async / APScheduler、DeepSeek & DeepSeek-R1 & Kimi & MiniMax（OpenAI 兼容）、React 18 + TypeScript + Vite + Tailwind、Docker

---

## 版本对照表（投递时可按 JD 选用）

| 维度 | 完整版 | 精简版 |
|---|---|---|
| 篇幅 | 7 条要点 + 技术栈 | 5 条要点 + 技术栈 |
| 适用 | 详细项目经历、技术博客、候选人系统扩展段 | 一页纸简历、移动端投递 |
| 强调 | 端到端闭环 + 推理模型适配 + 架构演进 | 编排 + RAG + 推理模型 + 后台路径 + 流式 |
| 字数估算 | ~700 字 | ~430 字 |

---

## v2 相对 v1 的更新说明

| 变更 | 原因 |
|---|---|
| **新增「推理模型适配」要点** | 仓库未提交改动 `content_writer_agent.py` 新增 `_strip_think_blocks` 静态剥离 + 流式三态状态机 + 7 字符回看缓冲，专门处理 DeepSeek-R1 / MiniMax 等推理模型；`system_prompts.py` 新增禁止 think 块外泄的双层防御；测试覆盖 102 行新增 |
| **改写「写工具与人机协同」要点** | v0.6 P1.6 重构：`_execute_generate_article` 从抛 HumanConfirmationRequired 改成直接落 v0.2 Task 表 + 触发 worker；旧 Human-in-the-loop 路径保留为 opt-in；这本身是有意识的架构演进（避免流式卡顿），值得在简历中体现 |
| **精简版同步**：Human-in-the-loop 不再单独成条 | 5 条要点合并为"写工具与人机协同（v0.6 P1.6）"，覆盖默认后台路径 + opt-in 旧路径 |
| **技术栈行**：加入「推理模型适配（think 块剥离 + 流式状态机）」 | 新能力的关键词标签 |
| **保守边界更新**：澄清 LLM 流式现状 | Agent SSE 仅承载事件，但 ContentWriter 自身支持真流式；表述更准确 |