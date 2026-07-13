# GEO2 改进计划（基于锐评 2026-07-14）

> 关联：[README.md](./README.md) 总分 35/55（B 级）/ 11 维度评分
> 来源：11 个锐评文件 §6 改进建议汇总

---

## 高优先级（建议立即做）

### 1. 建评测集

- **关联锐评**：[06-evaluation.md](./06-evaluation.md)（1/5）
- **影响**：从 1/5 → 3/5，单项最大提升
- **估时**：2-3d
- **任务**：
  - 建 `evals/` 目录
  - 写 30 条评测用例（5 类场景各几条：正常 15 / 边界 8 / 数据缺失 8 / 诱导错误 8 / 拒答 5）
  - LLM-as-judge 评测脚本（用 GPT-4o 评 MiniMax 输出）
  - 失败原因分类（outcome + error type + retryable）

### 2. 建 AGENTS.md + ruff + GitHub Actions

- **关联锐评**：[11-harness-engineering.md](./11-harness-engineering.md)（2/5）
- **影响**：从 2/5 → 3.5/5
- **估时**：1-2d
- **任务**：
  - 写 `AGENTS.md`（~100 行，指向 docs/、.superpowers/、backend/）
  - 加 `ruff`（基础 lint）+ `mypy`（类型检查）
  - 加 `.github/workflows/ci.yml`（pytest + ruff + mypy 自动跑）

### 3. 修复 knowledge_repo 反向依赖

- **关联锐评**：[10-architecture-layering.md §3.3](./10-architecture-layering.md)
- **影响**：架构整洁度
- **估时**：0.5d
- **任务**：把 `services/hybrid_search` 引用从 `knowledge_repo.py` 移到上层（service 层或 API 层）

### 4. 同步 generate_article 工具描述

- **关联锐评**：[02-tool-boundary.md §3.5](./02-tool-boundary.md)
- **影响**：消除 schema drift，避免 LLM 行为不一致
- **估时**：0.5d
- **任务**：修改 `tools.py` 的 `_GENERATE_SCHEMA.description` 与 v0.6 P1.6 实际行为对齐（默认走后台、不询问确认）

### 5. max_retries 默认值提到 ≥3 + 指数退避

- **关联锐评**：[05-failure-recovery.md §3.2](./05-failure-recovery.md)
- **影响**：生产稳定性
- **估时**：0.5d
- **任务**：修改 `llm_client.py` 的 `query_single` 默认 max_retries 为 3，加入指数退避（asyncio.sleep(2 ** attempt)）

### 6. memory.py 多处宽泛捕获收敛

- **关联锐评**：[05-failure-recovery.md §3.5](./05-failure-recovery.md)
- **影响**：编程错误可见性
- **估时**：1d
- **任务**：把 `memory.py` 中 8 处 `except Exception` 收敛到 `_LLM_TRANSIENT_EXCEPTIONS` 模式

---

## 中优先级（下一个 sprint）

### 7. 提取 MAX_REACT_ITERATIONS 到 Settings

- **关联锐评**：[01-agent-loop.md](./01-agent-loop.md)
- **估时**：0.5d
- **任务**：与上下文预算对齐，env 可覆盖

### 8. 提取嵌套 async with factory() as session 为依赖注入

- **关联锐评**：[01-agent-loop.md](./01-agent-loop.md)
- **估时**：1d
- **任务**：消除 5 层嵌套 async with，提高可读性

### 9. LLM 调用失败的显式降级

- **关联锐评**：[01-agent-loop.md](./01-agent-loop.md)
- **估时**：1d
- **任务**：在 `chat_with_tools` 外层加 try/except（超时 / 429 / provider error），包装成 SSE 事件

### 10. 工具 schema description 防 drift 测试

- **关联锐评**：[02-tool-boundary.md](./02-tool-boundary.md)
- **估时**：0.5d
- **任务**：单元测试断言 schema description 包含关键行为词

### 11. 改用 token 级截断

- **关联锐评**：[03-context-control.md](./03-context-control.md)
- **估时**：1d
- **任务**：接 tokenizer（tiktoken 或 provider tokenizer），按 token 截断

### 12. 增加历史摘要策略

- **关联锐评**：[03-context-control.md](./03-context-control.md)
- **估时**：2d
- **任务**：窗口 + 摘要双层（旧消息 LLM 摘要）

### 13. 声明式权限策略

- **关联锐评**：[04-permission.md §3.4](./04-permission.md)
- **估时**：1d
- **任务**：每个工具声明 `requires_confirmation: bool` 配置

### 14. HumanConfirmation 路径专项测试

- **关联锐评**：[04-permission.md §3.6](./04-permission.md)
- **估时**：1d
- **任务**：覆盖 approve / reject / 超时 / 跨 session

### 15. react_loop 工具失败引入 transient/programming 区分

- **关联锐评**：[05-failure-recovery.md §3.3](./05-failure-recovery.md)
- **估时**：1d
- **任务**：复用 `_LLM_TRANSIENT_EXCEPTIONS` 模式

### 16. 故障注入测试套件

- **关联锐评**：[05-failure-recovery.md §3.6](./05-failure-recovery.md)
- **估时**：2d
- **任务**：mock LLM 抛 RateLimitError / TimeoutError，验证降级路径

### 17. 接入 Sentry

- **关联锐评**：[07-observability.md §3.4](./07-observability.md)
- **估时**：0.5d
- **任务**：异常聚合 + 用户上下文

### 18. 接入 Langfuse

- **关联锐评**：[07-observability.md §3.4](./07-observability.md)
- **估时**：0.5d
- **任务**：LLM 调用可视化 + 成本分析

### 19. trace_id 串联

- **关联锐评**：[07-observability.md §3.4](./07-observability.md)
- **估时**：1d
- **任务**：contextvars 注入 logger

### 20. 声明式 HITL 策略

- **关联锐评**：[08-hitl.md §3.4](./08-hitl.md)
- **估时**：1d
- **任务**：per-tool `requires_confirmation`

### 21. pending 超时自动取消

- **关联锐评**：[08-hitl.md §3.6](./08-hitl.md)
- **估时**：0.5d
- **任务**：pending > 5 分钟自动取消 + 追加消息

### 22. reject 理由进入 LLM 上下文

- **关联锐评**：[08-hitl.md §3.5](./08-hitl.md)
- **估时**：1d
- **任务**：reject 时把"用户拒绝"作为 user 消息进入历史，影响后续决策

### 23. 端到端 turn 延迟

- **关联锐评**：[09-cost-latency.md §3.4](./09-cost-latency.md)
- **估时**：0.5d
- **任务**：metrics 加 turn_duration_ms 字段

### 24. 每次 LLM 调用的耗时

- **关联锐评**：[09-cost-latency.md §3.5](./09-cost-latency.md)
- **估时**：0.5d
- **任务**：time.perf_counter() 包裹 chat_with_tools

### 25. Provider 单价配置 + cost 字段

- **关联锐评**：[09-cost-latency.md §3.6](./09-cost-latency.md)
- **估时**：1d
- **任务**：Settings 加 MODEL_PRICING 字典，metrics 加 cost_usd 字段

### 26. 慢查询告警

- **关联锐评**：[09-cost-latency.md §3.7](./09-cost-latency.md)
- **估时**：0.5d
- **任务**：LLM > 60s 触发 warning

### 27. 引入 import-linter

- **关联锐评**：[10-architecture-layering.md §3.7](./10-architecture-layering.md)
- **估时**：1d
- **任务**：配置 api → services → domain → repos → models 方向约束

### 28. 显式 Providers 抽象

- **关联锐评**：[10-architecture-layering.md §3.6](./10-architecture-layering.md)
- **估时**：3d
- **任务**：auth / telemetry / feature flag 抽象

### 29. 加 import-linter（harness 维度）

- **关联锐评**：[11-harness-engineering.md §3.3](./11-harness-engineering.md)
- **估时**：1d
- **任务**：见 #27

### 30. 建 tech-debt-tracker.md

- **关联锐评**：[11-harness-engineering.md §3.6](./11-harness-engineering.md)
- **估时**：0.5d
- **任务**：技术债追踪表

---

## 低优先级（可选优化）

### 31. 故障注入工具

- **关联锐评**：[01-agent-loop.md](./01-agent-loop.md)
- **估时**：1d

### 32. 显式 replay API

- **关联锐评**：[01-agent-loop.md §3.5](./01-agent-loop.md), [05-failure-recovery.md §3.7](./05-failure-recovery.md)
- **估时**：2d

### 33. 移除 noqa: BLE001 宽泛捕获

- **关联锐评**：[01-agent-loop.md](./01-agent-loop.md)
- **估时**：1d
- **任务**：区分业务异常与编程异常

### 34. 写类工具 HumanConfirmation 路径标记

- **关联锐评**：[02-tool-boundary.md](./02-tool-boundary.md)
- **估时**：0.5d
- **任务**：schema description 加"暂未启用"标识

### 35. 工具注册表收拢

- **关联锐评**：[02-tool-boundary.md](./02-tool-boundary.md)
- **估时**：1d
- **任务**：ToolName 枚举 / _VALIDATORS / _TOOL_SCHEMAS 收拢到单一注册表

### 36. 截断决策可解释

- **关联锐评**：[03-context-control.md](./03-context-control.md)
- **估时**：1d
- **任务**：输出 metadata：哪些消息被裁、被截断位置

### 37. 自适应压缩

- **关联锐评**：[03-context-control.md](./03-context-control.md)
- **估时**：3d

### 38. token 上限硬限制

- **关联锐评**：[03-context-control.md](./03-context-control.md)
- **估时**：0.5d

### 39. 自动拒绝超时

- **关联锐评**：[04-permission.md](./04-permission.md)
- **估时**：0.5d

### 40. 权限操作审计日志独立表

- **关联锐评**：[04-permission.md](./04-permission.md)
- **估时**：1d

### 41. CORS 生产严格化

- **关联锐评**：[04-permission.md §3.5](./04-permission.md)
- **估时**：0.5d

### 42. 评测集与 CI 集成

- **关联锐评**：[06-evaluation.md](./06-evaluation.md)
- **估时**：1d

### 43. 人评结合

- **关联锐评**：[06-evaluation.md](./06-evaluation.md)
- **估时**：每月 0.5d

### 44. 评测可视化

- **关联锐评**：[06-evaluation.md](./06-evaluation.md)
- **估时**：2d

### 45. Prometheus 指标导出

- **关联锐评**：[07-observability.md](./07-observability.md)
- **估时**：2d

### 46. 用户偏好学习

- **关联锐评**：[08-hitl.md](./08-hitl.md)
- **估时**：3d

### 47. 多类 HITL 事件

- **关联锐评**：[08-hitl.md §3.1](./08-hitl.md)
- **估时**：5d
- **任务**：决策 / 补充输入 / 进度确认

### 48. HITL 端到端测试

- **关联锐评**：[08-hitl.md](./08-hitl.md)
- **估时**：2d

### 49. 月度成本 dashboard

- **关联锐评**：[09-cost-latency.md](./09-cost-latency.md)
- **估时**：3d

### 50. 自适应模型选择

- **关联锐评**：[09-cost-latency.md](./09-cost-latency.md)
- **估时**：5d

### 51. Fallback 策略

- **关联锐评**：[09-cost-latency.md](./09-cost-latency.md)
- **估时**：3d

### 52. ORM 版本迁移脚本

- **关联锐评**：[10-architecture-layering.md §3.5](./10-architecture-layering.md)
- **估时**：5d

### 53. API 层加 auth

- **关联锐评**：[10-architecture-layering.md](./10-architecture-layering.md)
- **估时**：2d

### 54. 定期后台 agent 扫描代码偏差

- **关联锐评**：[11-harness-engineering.md §3.6](./11-harness-engineering.md)
- **估时**：5d

### 55. 自动重构 PR 流程

- **关联锐评**：[11-harness-engineering.md §3.6](./11-harness-engineering.md)
- **估时**：5d

---

## 改进项与锐评维度的映射

### P0 改进项

| 改进项 | 关联锐评 | 当前分 | 目标分 | 估时 |
| --- | --- | --- | --- | --- |
| 建评测集 | 06 评测体系 | 1 | 3 | 2-3d |
| 建 AGENTS.md + ruff + GitHub Actions | 11 Harness 范式 | 2 | 3.5 | 1-2d |
| 修复 knowledge_repo 反向依赖 | 10 架构分层 | 3 | 3.5 | 0.5d |
| 同步 generate_article 工具描述 | 02 工具边界 | 4 | 4.5 | 0.5d |
| max_retries ≥3 + 指数退避 | 05 失败恢复 | 4 | 4.5 | 0.5d |
| memory.py 宽泛捕获收敛 | 05 失败恢复 | 4 | 4.5 | 1d |

**P0 总估时**：6-8d（1 个 sprint）

### P1 改进项

| 改进项 | 关联锐评 | 当前分 | 目标分 | 估时 |
| --- | --- | --- | --- | --- |
| MAX_REACT_ITERATIONS → Settings | 01 Agent Loop | 4 | 4.5 | 0.5d |
| 提取嵌套 async with 为 DI | 01 Agent Loop | 4 | 4.5 | 1d |
| LLM 调用失败显式降级 | 01 Agent Loop | 4 | 4.5 | 1d |
| 工具 schema 防 drift 测试 | 02 工具边界 | 4 | 4.5 | 0.5d |
| token 级截断 | 03 上下文可控 | 4 | 4.5 | 1d |
| 历史摘要策略 | 03 上下文可控 | 4 | 4.5 | 2d |
| 声明式权限策略 | 04 权限策略 | 4 | 4.5 | 1d |
| HumanConfirmation 专项测试 | 04 权限策略 | 4 | 4.5 | 1d |
| react_loop transient 区分 | 05 失败恢复 | 4 | 4.5 | 1d |
| 故障注入测试 | 05 失败恢复 | 4 | 4.5 | 2d |
| 接入 Sentry | 07 可观测性 | 3 | 4 | 0.5d |
| 接入 Langfuse | 07 可观测性 | 3 | 4 | 0.5d |
| trace_id 串联 | 07 可观测性 | 3 | 4 | 1d |
| 声明式 HITL 策略 | 08 HITL | 3 | 4 | 1d |
| pending 超时自动取消 | 08 HITL | 3 | 4 | 0.5d |
| reject 理由进入 LLM 上下文 | 08 HITL | 3 | 4 | 1d |
| 端到端 turn 延迟 | 09 成本/延迟 | 3 | 4 | 0.5d |
| LLM 调用耗时 | 09 成本/延迟 | 3 | 4 | 0.5d |
| Provider 单价 + cost 字段 | 09 成本/延迟 | 3 | 4 | 1d |
| 慢查询告警 | 09 成本/延迟 | 3 | 4 | 0.5d |
| import-linter | 10 架构分层 | 3 | 4 | 1d |
| Providers 抽象 | 10 架构分层 | 3 | 4 | 3d |
| import-linter（harness 维度） | 11 Harness | 2 | 3 | 1d |
| tech-debt-tracker.md | 11 Harness | 2 | 3 | 0.5d |

**P1 总估时**：约 24d（3-4 个 sprint）

### P2 改进项（按需）

P2 共 25 项，总估时约 55d。

按主题归类：

- **01 Agent Loop 卓越化**（#31-#33）：3d
- **02 工具边界完善**（#34-#35）：1.5d
- **03 上下文高级特性**（#36-#38）：4.5d
- **04 权限高级特性**（#39-#41）：2d
- **06 评测 CI 化**（#42-#44）：3.5d
- **07 可观测 Prometheus**（#45）：2d
- **08 HITL 多场景**（#46-#48）：10d
- **09 成本 dashboard + 自适应**（#49-#51）：11d
- **10 ORM 迁移 + auth**（#52-#53）：7d
- **11 熵管理自动化**（#54-#55）：10d

---

## 总体目标

**完成 P0 + P1 后预期总分**：约 47-49 / 55（A 级下限）

| 维度 | 当前 | P0 后 | P0+P1 后 |
| --- | --- | --- | --- |
| 01 Agent Loop | 4 | 4 | 4.5 |
| 02 工具边界 | 4 | 4.5 | 4.5 |
| 03 上下文可控 | 4 | 4 | 4.5 |
| 04 权限策略 | 4 | 4 | 4.5 |
| 05 失败恢复 | 4 | 4.5 | 4.5 |
| 06 评测体系 | 1 | 3 | 3 |
| 07 可观测性 | 3 | 3 | 4 |
| 08 HITL | 3 | 3 | 4 |
| 09 成本/延迟 | 3 | 3 | 4 |
| 10 架构分层 | 3 | 3.5 | 4 |
| 11 Harness 范式 | 2 | 3.5 | 3.5 |
| **总分** | **35** | **40** | **47.5** |

---

## 实施建议

1. **第 1 个 sprint（1 周）**：完成 P0（建评测集 + AGENTS.md + 修复分层违反 + 同步 schema + 改进重试）
2. **第 2-4 个 sprint（3 周）**：完成 P1 的核心部分（Sentry/Langfuse 接入、声明式权限、token 级截断）
3. **持续**：P2 按需进行（熵管理 / 自适应模型等）