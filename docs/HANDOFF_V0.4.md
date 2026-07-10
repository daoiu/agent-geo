# v0.4 实施启动话术

> **新会话复制下面整段即可启动 v0.4 实施**

---

```
按 D:/GEO2/docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.4.md
实施 GEO Agent v0.4（~19 个 task：自主决策 Agent 层）。

前置条件：v0.1 + v0.2 + v0.3 代码已存在并测试通过。

流程：
1. 调 superpowers:using-superpowers skill
2. 读 plan + specs/2026-07-10-geo-agent-v0.4-design.md
3. 报告读完，问执行方式（subagent-driven / inline）
4. 简体中文回复，Conventional Commits，TDD 严格

约束：
- 复用 v0.1 的 LLMClient + v0.2 的 KnowledgeRepository + 共享 _EXEC_LOCK
- 不引入 LangChain / LangGraph / Claude SDK（用 OpenAI SDK + 自己写 ReAct 循环）
- 3 个工具：diagnose_brand / search_knowledge / generate_article
- 知识库 A 模式：agent 只能查，不能改
- 写类工具（generate_article）需 human 确认
- 短任务（30s-2min），单次响应
- MAX_REACT_ITERATIONS = 5
- 多 session 支持 + 历史持久化
- Chat 聊天框 UI（SSE 流式）
- agent 不直接落库到 v0.1-v0.3 系统（generate_article 只返回预览）
```

---

## 关键文件

| 文件 | 路径 | 用途 |
|---|---|---|
| 设计文档 | `docs/superpowers/specs/2026-07-10-geo-agent-v0.4-design.md` | v0.4 做什么 + 为什么 |
| 实施计划 | `docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.4.md` | ~19 个 task 的 TDD 步骤 |
| 手动清单 | `docs/MANUAL_VERIFICATION_V0.4.md` | 发布前必跑 8 个场景 |

## 关键决策摘要

- **方向转变**：原 ROADMAP v0.4 是"多用户系统"，**用户重新定位为"自主决策 Agent"**（多用户推到 v1.0）
- **核心架构**：在 v0.1-v0.3 之上加 agent 编排层
- **ReAct 循环**：自己写（30 行代码），不引 LangGraph
- **工具调用**：原生 LLM Function Calling（OpenAI SDK 兼容 DeepSeek/Kimi）
- **3 工具职责**：
  - `diagnose_brand`（读）：v0.1 诊断，返回简化版
  - `search_knowledge`（读）：v0.2 知识库，**chunk 截断 500 字防 LLM 上下文爆炸**
  - `generate_article`（写）：v0.2 ContentWriter，**只预览不落库**
- **Human-in-the-loop**：写类工具前 `pending_confirmation=True` + 弹窗
- **SSE 协议**：text/event-stream，前端用 fetch + ReadableStream
- **前端无状态**：前端代码只关心 session_id / messages / 工具调用 / human confirmation

## 实施注意事项

- **Phase 0 任务 0.1 (LLMClient 扩展)**：新增 `chat_with_tools(messages, tools) -> {content, tool_calls}` 方法，**复用现有 client**（DeepSeek/Kimi 都支持 OpenAI tools schema）
- **Phase 0 任务 0.2 (ORM)**：2 张新表（agent_sessions / agent_messages）
- **Phase 0 任务 0.3 (异常)**：`HumanConfirmationRequired` 异常承载 message_id / tool_name / arguments
- **Phase 1 工具 schema**：3 个工具的 function calling JSON Schema + Pydantic 验证
- **Phase 2 ToolExecutor**：
  - `_execute_diagnose_brand` 包装 v0.1 `DiagnosisService.run()`
  - `_execute_search_knowledge` 包装 v0.2 `KnowledgeRepository.search_chunks_by_keyword()`（v0.5 会升级）
  - `_execute_generate_article` **先抛 `HumanConfirmationRequired`**，不直接调 ContentWriter
- **Phase 3 AgentRepository**：CRUD + `confirm_message(id, approved)`
- **Phase 4 ReAct 循环**：`build_messages(history)` + `run_agent_turn(session_id, message)` 流式 yield 6 种 SSE 事件
- **Phase 5 API**：session CRUD（agent_sessions.py）+ SSE chat（agent_chat.py）；**SSE 用 FastAPI StreamingResponse**
- **Phase 6 前端**：5 个新组件（ChatMessage / ToolCallCard / ConfirmDialog / ChatInput / AgentChat）；用 `fetch + ReadableStream` 消费 SSE
- **Phase 7 E2E**：测 SSE 流式响应 + human confirmation 流程

## 不要做的事

- ❌ 引入 LangChain / LangGraph / Claude SDK
- ❌ 多用户系统 / 鉴权 / 团队（推到 v1.0）
- ❌ 写类工具直接落库到 v0.2 系统
- ❌ 增删改知识库 / 创建任务的工具（agent 只读）
- ❌ 多 Agent 协作 / Agent 通信
- ❌ 跨 session 学习 / 用户偏好记忆
- ❌ MCP server 暴露
- ❌ 流式 LLM 输出（v0.4 用 SSE 但 LLM 响应一次性）
- ❌ Voice / 图片 / 文件输入

## 测试重点

- 工具 schema 验证（Pydantic）
- ToolExecutor 包装逻辑
- ReAct 循环（MAX_ITERATIONS 触发、human confirmation 暂停）
- RAG 7 组件中 v0.4 覆盖：5. 严格生成（prompt 约束、引用 chunk id）
- 6. 持续评估（v0.4 human-in-the-loop 作为隐式反馈）
- 7. 闭环优化（人工闭环）
- SSE 解析（前端 parser + 错误处理）
