# GEO Agent Phase 1 — 循环收敛 + 埋点 设计

| 字段 | 值 |
|---|---|
| 版本 | 优化路线图 Phase 1 |
| 日期 | 2026-07-13 |
| 状态 | 设计已批，待实施 |
| 前置 | v0.6 P1.6（L2 跨会话偏好）已上线 |
| 路线图 | `2026-07-13-memory-context-optimization-roadmap.md` |
| 后端变更 | `llm_client.py` usage 透出 / `react_loop.py` 抽共享循环 + metrics 日志 |
| 前端变更 | 无 |
| DB / SSE | 不变 |

---

## 1. 背景与目标

### 1.1 背景

`react_loop.py` 有两个入口函数，ReAct 循环体近乎逐行重复（各 ~200 行）：

- `run_agent_turn` —— 新 turn：加载历史 → 保存 user 消息 → 跑循环
- `run_agent_turn_from_checkpoint` —— 从 `pending_confirmation` 恢复：执行 confirmed
  `generate_article` → 保存 tool 结果 → 跑**同一个**循环

L2 接入时（v0.6 P1.6）两处循环都要加"索引段 + relevant 注入 + fire-and-forget
extract"，已经被迫双改一次。后续 Phase 3（#4 工具结果瘦身 / #5 L0 窗口摘要）还要
反复动循环。不收敛成一处，每次 context 策略调整都要改两遍且容易漂移。

同时，`chat_with_tools` / `simple_chat` 丢弃了 `response.usage`
（`llm_client.py:284、297-300`），导致无法量化 token 开销 —— 而 Phase 2/3
的收益（"优化了多少 token / 少了几次 LLM 调用"）必须有基线才能验证。

### 1.2 目标

1. 把两个入口的重复循环体抽成单一共享驱动，两入口只保留各自"起点差异"
2. 让 `LLMClient` 透出 usage，并在每轮 turn 收尾打一行 metrics 日志
3. **严格行为等价**：除"usage 字段 + 一行日志"两处加法外，不改任何可观测行为

### 1.3 范围（In Scope）

| 模块 | 行为 |
|---|---|
| `_drive_react_loop`（新，`react_loop.py` 内） | 共享 ReAct 循环体：算 memory 上下文 + 迭代 + 工具子循环 + 落库 + SSE yield |
| `run_agent_turn` | 瘦身为"起点差异 + 委托" |
| `run_agent_turn_from_checkpoint` | 瘦身为"起点差异 + 委托" |
| `chat_with_tools` | 返回值加 `usage` 字段 |
| `simple_chat` | 签名不变（仍返回 `str`），仅内部 log usage（见 §5.2） |
| metrics 日志 | 每轮三个出口打 `agent_turn_metrics` |
| 测试 | usage 透出 + metrics 日志用例；现有 442 全回归 |

### 1.4 范围外（Out of Scope）

| 项 | 原因 |
|---|---|
| 埋点持久化 / SSE 回传 | 用户拍板"仅 structlog 日志" |
| tiktoken 估算 token | provider 不返回 usage 时记 None，不估算 |
| 拆 `loop_core.py` 独立文件 | 两入口与共享体同域，拆文件增跳转 |
| 顺手修重构中发现的 bug | 严格行为等价；发现只记录不改（见 §10） |
| 工具结果瘦身 / L0 窗口摘要 | Phase 3 |
| 记忆层向量化 | Phase 2 |

## 2. 架构

### 2.1 收敛前后

```
[前]
run_agent_turn ──────────────┐  ~200 行循环体
run_agent_turn_from_checkpoint┘  ~200 行几乎相同的循环体

[后]
run_agent_turn ───────────────┐ 起点差异
                              ├─ 委托 → _drive_react_loop(共享)
run_agent_turn_from_checkpoint┘ 起点差异
```

### 2.2 起点差异（各入口保留）

| 入口 | 起点差异 |
|---|---|
| `run_agent_turn` | 加载历史 → 保存 user 消息 → `history = rows + [user]` |
| `run_agent_turn_from_checkpoint` | 找 ckpt → 校验 pending → 执行 `_execute_generate_article_confirmed` → 保存 tool 结果 → `yield tool_call_result` → reload history |

两者产出统一的 `history: list[dict]` 后，委托给共享驱动。

### 2.3 共享驱动职责

```
_drive_react_loop(session_id, history, device_id):
  scope = scope_key(device_id, session_id)
  memory_index_segment = build_memory_segment(scope)     # 原两处重复
  memory_block         = load_relevant_memories(scope, history)

  agg = {iterations:0, llm_calls:0, tool_calls:0,
         prompt_tokens:0, completion_tokens:0, total_tokens:0,
         usage_seen:False}

  for _ in range(MAX_REACT_ITERATIONS):
     messages = build_messages(history, memory_index_segment)
     messages = _apply_memory_prepend(messages, memory_block)
     resp = llm.chat_with_tools(messages, TOOLS)
     _accumulate(agg, resp["usage"])                      # 埋点累计
     存 assistant → yield assistant_message
     if tool_calls:
        执行工具子循环:
          HumanConfirmation → _emit_metrics(agg,"human_confirmation") → yield → return
          其它异常 → err payload 落 tool 消息 → yield tool_call_result → continue
          成功 → 落 tool 消息 → yield tool_call_result
        reload history
     else:
        fire-and-forget extract
        _emit_metrics(agg, "turn_complete")
        yield turn_complete → return
  _emit_metrics(agg, "max_iterations_reached")
  yield max_iterations_reached
```

### 2.4 关键设计原则

| 原则 | 选择 | 理由 |
|---|---|---|
| 收敛粒度 | 共享循环体 = memory 上下文 + for 循环 | 两处逐行相同的部分，起点差异留在各入口 |
| ToolExecutor 生命周期 | 每 turn 建一次 | `__init__` 仅存 `session_id`，无跨轮状态，等价且更简 |
| 文件放置 | `react_loop.py` 内 | 同域，不拆文件 |
| 埋点侵入度 | 累计 + 三出口一行日志 | 不动 DB / SSE，最小侵入 |
| 行为契约 | 严格等价（仅两处加法） | 靠现有 442 测试当 oracle |

## 3. 埋点字段

`agent_turn_metrics`（structlog info）：

| 字段 | 含义 |
|---|---|
| `session_id` / `device_id` | 归属 |
| `outcome` | `turn_complete` / `max_iterations_reached` / `human_confirmation` |
| `iterations` | 本轮实际迭代数 |
| `llm_calls` | 本轮 `chat_with_tools` 次数 |
| `tool_calls` | 本轮工具执行次数 |
| `prompt_tokens` / `completion_tokens` / `total_tokens` | 累计；provider 无 usage 时为 `None` |

## 4. usage 透出

### 4.1 提取助手

```python
def _extract_usage(response) -> dict | None:
    u = getattr(response, "usage", None)
    if u is None:
        return None
    return {
        "prompt_tokens": getattr(u, "prompt_tokens", None),
        "completion_tokens": getattr(u, "completion_tokens", None),
        "total_tokens": getattr(u, "total_tokens", None),
    }
```

### 4.2 累计（usage=None 容错）

```python
def _accumulate(agg, usage):
    agg["iterations"] += 1
    agg["llm_calls"] += 1
    if usage is None:
        return
    agg["usage_seen"] = True
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if usage.get(k) is not None:
            agg[k] += usage[k]
```

出口打日志时，`usage_seen=False` → token 字段输出 `None`（区分"0 tokens"与"未知"）。

## 5. 接口规范

### 5.1 `chat_with_tools` 新返回

```python
return {
    "content": message.content,
    "tool_calls": tool_calls,
    "usage": _extract_usage(response),   # 新
}
```

已有调用方（`react_loop.py`）只多读一个可选 key，向后兼容。

### 5.2 `simple_chat`

`simple_chat` 现返回 `str`，被记忆层（`memory.py`）多处调用。为不牵动 Phase 2
范围，本 Phase **保持 `simple_chat` 返回 `str` 签名不变**，仅在其内部 `logger.info`
打一行 usage（供日后统计），不改返回值。

> 决策：Phase 1 只保证 agent 主循环（`chat_with_tools`）的 token 可量化；
> `simple_chat` 的调用方改造留待 Phase 2 记忆层重构时一并处理。

### 5.3 两入口签名

不变：

```python
async def run_agent_turn(session_id, user_message, device_id=None) -> AsyncIterator[dict]
async def run_agent_turn_from_checkpoint(session_id, checkpoint_message_id, device_id=None) -> AsyncIterator[dict]
```

## 6. 数据流

DB 落库时机、SSE 事件序列、HumanConfirmation 暂停语义**完全不变**。共享驱动逐字节
产出与收敛前相同的事件流。

## 7. 文件地图

```
backend/app/
├── domain/
│   ├── llm_client.py          # 改: _extract_usage + chat_with_tools 加 usage + simple_chat 内部 log
│   └── agent/
│       └── react_loop.py      # 改: 抽 _drive_react_loop + _accumulate + _emit_metrics; 两入口瘦身
└── tests/
    ├── test_llm_client_usage.py            # 新: chat_with_tools 返回带 usage / provider 无 usage → None
    └── test_react_loop_metrics.py          # 新: 三出口各打 agent_turn_metrics(mock LLM 喂带 usage 响应)
```

## 8. 错误处理

| 场景 | 行为 |
|---|---|
| provider 不返回 usage | `_extract_usage` → None；累计跳过；出口 token 字段 = None |
| usage 部分字段缺失 | 缺的字段不累加，其余照加 |
| HumanConfirmation 暂停 | 打 `outcome=human_confirmation` 后 return（原语义不变） |
| 工具异常 | err payload 落 tool 消息（原语义不变），不额外埋点 |

## 9. 测试

| 层 | 文件 | 用例 |
|---|---|---|
| LLM client | `test_llm_client_usage.py` | ① 有 usage → 三字段透出；② 无 usage → None；③ 部分字段缺失 |
| 循环 metrics | `test_react_loop_metrics.py` | ① turn_complete 出口打日志且 token 累计正确；② max_iterations 出口；③ human_confirmation 出口；④ usage=None 时 token 记 None |
| 回归 | 现有 442 全量 | 两入口行为等价，尤其 `build_messages` 配对 + 断点续跑用例 |

mock LLM 模板：`AsyncMock` 返回带 `usage` 的对象（`SimpleNamespace(prompt_tokens=..)`）。

## 10. 重构中发现的观测（只记录，不在本 Phase 改）

> 重构时若发现潜在 bug / 坏味，登记在此，交由后续 Phase 或独立修复，保持本 Phase 严格等价。

- **死变量 `should_continue`**（原两处循环）：设为 `True` 后仅有 `if not should_continue: break`，无处置为 `False`，是死代码。抽 `_drive_react_loop` 时直接省略——行为等价。
- **checkpoint 内 `settings = get_settings()` 变为未用**：原仅喂给第二循环的 `llm = LLMClient(settings)`，委托后删除，故一并移除。
- **测试隔离脆弱（既有，未修）**：`test_react_loop.py` 与 `test_react_loop_memory_integration.py` 同进程运行时，`test_system_prompt_includes_memory_index` 偶发失败；根因是 `_PENDING_EXTRACTS` 的 fire-and-forget 后台协程跨测试泄漏，污染后一测试的 memory scope 并留下 "no active connection" / "coroutine ignored GeneratorExit" 噪音。各文件单独跑均绿，全量 515 亦绿。属测试基建问题，非本 Phase 目标——建议后续给 fire-and-forget extract 加测试期 drain/禁用开关。

## 11. 决策日志

| 决策 | 选项 | 选择 | 理由 |
|---|---|---|---|
| 埋点落地 | 日志 / 持久化 / SSE 回传 | 仅 structlog 日志 | 用户拍板；DB 已存全量历史，前后对比 grep 日志即可 |
| token 缺失 | 记 None / tiktoken 估算 | 记 None | 不引依赖；区分未知与 0 |
| 文件放置 | 内联 / 拆 loop_core.py | 内联 react_loop.py | 同域，减跳转 |
| ToolExecutor 生命周期 | 每轮建 / 每 turn 建 | 每 turn 建一次 | 无跨轮状态，等价更简 |
| simple_chat 改造 | 本 Phase 改 / 押后 | 押后 Phase 2 | 不牵动记忆层范围 |
| 重构中发现的 bug | 顺手改 / 只记录 | 只记录（§10） | 保严格行为等价，便于回归定位 |

## 12. 退出标准

- [ ] 现有 442 后端单测全 pass（两入口行为等价）
- [ ] `chat_with_tools` 返回带 usage；provider 无 usage 时为 None
- [ ] 每轮 turn 三个出口打出 `agent_turn_metrics`，token / 调用次数正确
- [ ] 无 DB schema 变更、无 SSE 协议变更、无前端变更
- [ ] `_drive_react_loop` 为唯一循环体，两入口仅保留起点差异
