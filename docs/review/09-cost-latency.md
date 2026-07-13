# 09. 成本 / 延迟

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义

Token 成本与延迟的可见性与控制。包括：每次调用的 token / latency 记录、成本计算、告警阈值、自适应模型选择、可解释成本结构。

依据：[`00-learning-summary.md` §6.9](./00-learning-summary.md)

## 2. 评分标准（0-5 分制）

| 分数 | 含义 | 触发条件 |
| --- | --- | --- |
| 0 | 缺失 | 无任何记录 |
| 1 | 雏形 | 偶尔记录 |
| 2 | 基础 | 关键调用有 token 记录 |
| 3 | 达标 | 每次调用记录 token + 延迟 |
| 4 | 良好 | 有成本/延迟告警阈值 |
| 5 | 卓越 | 自适应模型选择、可解释成本结构 |

## 3. GEO2 现状调研

### 3.1 Token 计量（强项）

来源：[`_emit_metrics` L258–L269](./../backend/app/domain/agent/react_loop.py)

```python
def _emit_metrics(agg, session_id, device_id, outcome):
    logger.info(
        "agent_turn_metrics",
        session_id=session_id, device_id=device_id,
        outcome=outcome,
        iterations=agg["iterations"], llm_calls=agg["llm_calls"],
        tool_calls=agg["tool_calls"],
        prompt_tokens=agg["prompt_tokens"] if agg["usage_seen"] else None,
        completion_tokens=agg["completion_tokens"] if agg["usage_seen"] else None,
        total_tokens=agg["total_tokens"] if agg["usage_seen"] else None,
    )
```

**优点**：

- ✓ 每次 turn 记录 prompt_tokens / completion_tokens / total_tokens
- ✓ `usage_seen` 标志处理 provider 不返回 usage 的情况
- ✓ 结构化日志（可被聚合）

### 3.2 Timeout 配置（达标）

来源：[`config.py` L53–L77](./../backend/app/core/config.py)

```python
diagnosis_total_timeout_s: int = 90
llm_call_timeout_s: int = 120  # v0.6 P1.5: MiniMax + 长 prompt + RAG chunks 30s 不够
crawl_timeout_s: int = 10
publish_timeout_s: int = 30
```

**优点**：

- ✓ 多场景 timeout 配置
- ✓ v0.6 P1.5 调高 llm_call_timeout_s（30s → 120s），注释说明原因
- ✓ Pydantic Settings 注入（env 可覆盖）

### 3.3 Crawler 内部延迟记录（部分达标）

来源：[`crawler.py` L27, L87, L94, L102](./../backend/app/domain/crawler.py)

```python
# CRAWLER L27
elapsed_ms: int | None

# CRAWLER L87
elapsed_ms = int(response.elapsed.total_seconds() * 1000)
```

**优点**：

- ✓ 爬虫响应记录 elapsed_ms
- ✓ timeout 场景下 elapsed_ms=None
- ✓ error 场景下 elapsed_ms=None

**弱项**：

- ✗ 仅爬虫内部使用，未导出到 metrics
- ✗ 无 LLM 调用延迟记录（chat_with_tools 耗时）

### 3.4 ⚠️ 缺失：端到端 turn 延迟

`agent_turn_metrics` 记录了 iterations / llm_calls / tokens，但**没有** turn 整体耗时。

实际场景：用户问"生成文章"，从 user message 入队到 turn_complete SSE 事件 emit 的总耗时，对评估响应体验至关重要。

**当前状态**：可在 SSE 事件流中测量（`turn_start` / `turn_complete` 事件时间差），但**未记录到 metrics**。

### 3.5 ⚠️ 缺失：LLM 调用延迟

`llm_calls` 计数有，但**每次 LLM 调用的耗时**未记录。

实际场景：

- DeepSeek 平均响应 2s，MiniMax 平均 30s —— 用户体感差异巨大
- 长 prompt + RAG chunks 时，单次 LLM 调用可能超过 30s（v0.6 P1.5 调高 timeout 的原因）

**当前状态**：日志中只能从 `llm_timeout` warning 反推超时事件，无法统计 P50 / P95 / P99。

### 3.6 ⚠️ 缺失：成本计算

**当前状态**：

- ✓ token 计量
- ✗ 无 provider 单价配置（`MODEL_PRICING` 之类）
- ✗ 无 cost 字段（每次 turn 的 USD/CNY 花费）
- ✗ 无月度成本聚合
- ✗ 无按用户/会话的成本分摊

### 3.7 ⚠️ 缺失：告警阈值

**当前状态**：

- ✗ 无慢查询告警（LLM > 30s, crawler > 10s）
- ✗ 无 token 超限告警（单次 turn > 50k tokens）
- ✗ 无成本超限告警（每日 > ¥X）

### 3.8 ⚠️ 缺失：自适应模型选择

**当前状态**：

- 模型在 `LLM_PROVIDERS` 配置中固定
- 无任务分级（简单任务用小模型、复杂任务用大模型）
- 无 fallback 策略（主 provider 失败切备用）

## 4. 评分与理由

**评分：3 / 5（达标，但缺延迟和成本维度）**

| 维度 | 现状 | 评分贡献 |
| --- | --- | --- |
| Token 记录 | ✓ 每次 turn 都记录 | +1 |
| Timeout 配置 | ✓ 多场景配置 | +1 |
| Crawler 延迟 | 部分（仅内部） | +0.5 |
| 端到端 turn 延迟 | ✗ 无 | - |
| LLM 调用延迟 | ✗ 无 | - |
| 成本计算 | ✗ 无 | - |
| 告警阈值 | ✗ 无 | - |
| 自适应模型 | ✗ 无 | - |

**关键证据**：

- 强项：token 计量 + timeout 配置
- 弱项：延迟仅在 crawler 内部、成本无计算、告警无阈值

**与行业标准差距**：

- 学习路线 §6.9 卓越：自适应模型选择 —— 完全缺失
- 学习路线 §6.9 良好：成本/延迟告警 —— 完全缺失
- GEO2 处于"达标"档（每次调用记录 token + 延迟）但实际只达标 token 部分

## 5. 面试讲点

### 30 秒版本

> 每次 turn 记录 prompt/completion/total tokens；多场景 timeout 配置（llm 120s / crawl 10s）；crawler 内部 elapsed_ms。缺端到端 turn 延迟、LLM 调用延迟、成本计算和告警。

### 2 分钟版本

1. **已建立**：
   - Phase 1 指标埋点 tokens（每次 turn）
   - 多场景 timeout（llm / crawl / diagnosis / publish）
   - Crawler 内部 elapsed_ms
2. **未建立**：
   - 端到端 turn 延迟（turn_start → turn_complete）
   - 每次 LLM 调用的耗时（P50 / P95 / P99）
   - 成本计算（provider 单价 × tokens）
   - 告警阈值（慢查询 / token 超限 / 成本超限）
   - 自适应模型选择（按任务分级）
3. **影响**：
   - 用户体感（响应延迟）无法量化
   - 成本只能事后统计
   - 长 prompt + RAG chunks 的性能回归无法告警

### 追问预判

| 追问 | 回答要点 |
| --- | --- |
| 单次 turn 平均多少 token？ | 不知道（没聚合） |
| 最贵的 turn 多少 token？ | 不知道（**改进候选 P1**） |
| 慢查询怎么发现？ | 靠日志 warning（llm_timeout），无系统告警（**改进候选 P1**） |
| 月度成本怎么算？ | 手动聚合 logs（**改进候选 P1**） |
| 不同模型怎么选？ | 当前固定配置；可按任务分级（**改进候选 P2**） |

## 6. 改进建议

| 优先级 | 改进项 | 关联 |
| --- | --- | --- |
| P1 | 端到端 turn 延迟（turn_start / turn_complete 时间差） | 见 `99-improvement-plan.md` |
| P1 | 每次 LLM 调用的耗时（time.perf_counter() 包裹 chat_with_tools） | 见 `99-improvement-plan.md` |
| P1 | Provider 单价配置 + cost 字段 | 见 `99-improvement-plan.md` |
| P1 | 慢查询告警（LLM > 60s 触发 warning） | 见 `99-improvement-plan.md` |
| P2 | 月度成本 dashboard（按用户/会话分摊） | 见 `99-improvement-plan.md` |
| P2 | 自适应模型选择（按任务分级） | 见 `99-improvement-plan.md` |
| P2 | Fallback 策略（主 provider 失败切备用） | 见 `99-improvement-plan.md` |