# 07. 可观测性

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义

日志、追踪、成本统计的完整度。包括：结构化日志、关键事件埋点、错误聚合、全链路追踪、可视化面板、可回放。

依据：[`00-learning-summary.md` §6.7](./00-learning-summary.md)

## 2. 评分标准（0-5 分制）

| 分数 | 含义 | 触发条件 |
| --- | --- | --- |
| 0 | 缺失 | 无日志 |
| 1 | 雏形 | 仅有 print |
| 2 | 基础 | 有日志但无结构化 |
| 3 | 达标 | 全链路结构化日志、有 token 成本统计 |
| 4 | 良好 | tracing + 错误聚合 + 可视化面板 |
| 5 | 卓越 | 可回放、可重跑 |

## 3. GEO2 现状调研

### 3.1 结构化日志（强项）

来源：[`requirements.txt`](./../backend/requirements.txt)

```
structlog==24.4.0
```

来源：[`react_loop.py` L23, L36](./../backend/app/domain/agent/react_loop.py)

```python
import structlog
logger = structlog.get_logger()
```

**优点**：

- ✓ 使用 structlog（行业标准的结构化日志库）
- ✓ 各模块独立 logger（agent / memory / crawler / llm_client / notification / monitor）
- ✓ 关键事件有结构化字段（session_id, device_id, outcome, tokens 等）

### 3.2 关键事件埋点（达标）

来源：[`_emit_metrics` L258–L269](./../backend/app/domain/agent/react_loop.py)

```python
def _emit_metrics(agg, session_id, device_id, outcome):
    logger.info(
        "agent_turn_metrics",
        session_id=session_id, device_id=device_id,
        outcome=outcome,
        iterations=agg["iterations"], llm_calls=agg["llm_calls"],
        tool_calls=agg["tool_calls"],
        prompt_tokens=..., completion_tokens=..., total_tokens=...
    )
```

**关键事件清单**：

| 事件 | 来源 | 字段 |
| --- | --- | --- |
| `agent_turn_metrics` | react_loop | outcome / tokens / iterations / llm_calls / tool_calls |
| `llm_timeout` | llm_client | provider / attempt |
| `llm_error` | llm_client | provider / attempt / error |
| `llm_unexpected` | llm_client | provider / attempt / error |
| `extract_after_turn_failed` | react_loop | session_id / error |
| `auto_generate_title_failed` | session_manager | error |

**优点**：

- ✓ 关键事件命名清晰（snake_case 事件名 + 字段）
- ✓ Token 成本统计（每次 turn 都记录）
- ✓ Outcome 区分（turn_complete / human_confirmation / max_iterations_reached）

### 3.3 各模块日志覆盖率

来源：grep `structlog.get_logger\(\)` 在 backend/app 中

| 模块 | logger | 备注 |
| --- | --- | --- |
| agent/react_loop | ✓ | 主循环埋点 |
| agent/memory | ✓ | 记忆系统 |
| agent/session_manager | ✓ | 会话管理 |
| agent/tool_executor | ✓ | 工具执行 |
| domain/crawler | ✓ | 爬虫 |
| domain/llm_client | ✓ | LLM 调用 |
| domain/monitor/monitor_service | ✓ | 监控服务 |
| domain/notification/email_sender | ✓ | 邮件发送 |
| domain/notification/notification_service | ✓ | 通知服务 |
| api/knowledge | ✓ | 知识库 API |

**覆盖率评价**：高 —— 主要业务模块都有结构化日志。

### 3.4 ⚠️ 缺失的能力

| 能力 | 现状 | 影响 |
| --- | --- | --- |
| trace_id（链路追踪） | ✗ 无 | 跨模块问题难定位 |
| Sentry / 错误聚合 | ✗ 无 | 错误未集中管理 |
| Langfuse / 全链路追踪 | ✗ 无 | LLM 调用无可视化 |
| Prometheus / 指标聚合 | ✗ 无 | 无 dashboard |
| 结构化日志输出目标 | 不明 | structlog 默认输出 JSON？需要看配置 |

### 3.5 测试与运维视角的可观测性

**生产部署的可观测性**：

- ✗ 无 trace_id 串联（一次 turn 的多个事件难关联）
- ✗ 无错误聚合（失败原因靠 grep 日志）
- ✗ 无成本 dashboard（每月 token 花费需手动统计）
- ✗ 无慢查询监控（爬虫 / LLM 慢响应无告警）

## 4. 评分与理由

**评分：3 / 5（达标，但缺聚合层）**

| 维度 | 现状 | 评分贡献 |
| --- | --- | --- |
| 结构化日志 | ✓ structlog 24.4.0 | +1 |
| 模块覆盖率 | ✓ 主要模块都有 logger | +0.5 |
| Token 成本统计 | ✓ 每次 turn 都记录 | +1 |
| Outcome 区分 | ✓ 4 种 outcome | +0.5 |
| Tracing（trace_id） | ✗ 无 | - |
| 错误聚合（Sentry 等） | ✗ 无 | - |
| 可视化面板 | ✗ 无 | - |
| 可回放 | ✗ 无 | - |

**关键证据**：

- 强项：structlog + 模块级 logger + 关键事件埋点 + token 统计
- 弱项：缺聚合层（trace_id / Sentry / dashboard）

**与行业标准差距**：

- 学习路线建议："[观测层] 日志、追踪、成本统计 | Langfuse / Sentry"
- GEO2 用了 structlog，但没接 Langfuse / Sentry —— 缺"数据 → 洞察"的最后一公里

## 5. 面试讲点

### 30 秒版本

> 用 structlog 24.4 做结构化日志，每个模块独立 logger；Phase 1 指标埋点记录 tokens / iterations / outcome；缺 trace_id 串联和错误聚合（Sentry/Langfuse）。

### 2 分钟版本

1. **已建立**：
   - structlog 24.4.0（行业标准结构化日志库）
   - 每个核心模块独立 logger
   - 关键事件埋点（agent_turn_metrics / llm_timeout / llm_error 等）
   - Token 计量（每次 turn 都记录 prompt/completion/total）
2. **未建立**：
   - trace_id 串联（一次 turn 多事件难关联）
   - Sentry / 错误聚合
   - Langfuse / LLM 调用可视化
   - Prometheus / dashboard
3. **影响**：
   - 生产问题排查靠 grep 日志
   - 错误模式难聚合
   - 成本统计需手动聚合

### 追问预判

| 追问 | 回答要点 |
| --- | --- |
| 为什么没接 Sentry？ | 项目阶段聚焦功能；Sentry 接入计划在 P1 |
| trace_id 如何实现？ | 在 LLMClient 入口生成 trace_id，注入 logger contextvars |
| 成本如何监控？ | 当前只能事后统计 logs；可加 Prometheus 指标 |
| 怎么发现 LLM 慢响应？ | 当前靠 warning 日志；可加慢查询告警 |

## 6. 改进建议

| 优先级 | 改进项 | 关联 |
| --- | --- | --- |
| P1 | 接入 Sentry（异常聚合 + 用户上下文） | 见 `99-improvement-plan.md` |
| P1 | 接入 Langfuse（LLM 调用可视化 + 成本分析） | 见 `99-improvement-plan.md` |
| P1 | trace_id 串联（contextvars 注入 logger） | 见 `99-improvement-plan.md` |
| P2 | Prometheus 指标导出（token / latency / error rate） | 见 `99-improvement-plan.md` |
| P2 | 慢查询告警（LLM > 30s, crawler > 10s） | 见 `99-improvement-plan.md` |