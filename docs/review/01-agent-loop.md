# 01. Agent Loop

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义

Agent Loop 是从用户输入到最终输出全链路的清晰度与可追溯性，包括：状态保存、最大轮次限制、上下文裁剪、错误处理、断点续跑、审计轨迹。

依据：[`00-learning-summary.md` §6.1](./00-learning-summary.md)

## 2. 评分标准（0-5 分制）

| 分数 | 含义 | 触发条件 |
| --- | --- | --- |
| 0 | 缺失 | 完全没有 Loop |
| 1 | 雏形 | 仅有意向，未落地 |
| 2 | 基础 | 有最简实现但不健壮 |
| 3 | 达标 | 链路完整、有状态保存、最大轮次限制、上下文裁剪 |
| 4 | 良好 | 错误注入可控、Loop 可视化、断点续跑 |
| 5 | 卓越 | Loop 抽取可复现、可回放、每次运行有审计轨迹 |

## 3. GEO2 现状调研

### 3.1 关键文件

| 文件 | 行数 | 职责 |
| --- | --- | --- |
| `backend/app/domain/agent/react_loop.py` | 576 | ReAct 主循环、入口、断点续跑 |
| `backend/app/domain/agent/build_messages` 函数 | ~110 | 历史 → OpenAI 协议，含窗口裁剪 + 配对保证 |
| `backend/app/domain/agent/_drive_react_loop` 函数 | ~200 | 共享循环体（被 run_agent_turn 和 run_agent_turn_from_checkpoint 委托） |
| `backend/app/domain/agent/session_manager.py` | 40 | 标题自动生成 |

### 3.2 关键设计

来源：[`react_loop.py` L1–L36 注释 + L277–L413](./../backend/app/domain/agent/react_loop.py)

- **自写循环（不引 LangGraph / LangChain）** —— 显式选择，提升可控性
- **`MAX_REACT_ITERATIONS = 7`** —— v0.6 P1.4: 5 → 7，留余量给 list → search → create_task
- **流式 SSE 事件**：`assistant_message` / `tool_call_start` / `tool_call_result` / `human_confirmation_required` / `turn_complete` / `max_iterations_reached` / `error`
- **写类工具抛 `HumanConfirmationRequired`** —— 暂停循环，等用户决策
- **断点续跑**：`run_agent_turn_from_checkpoint` 从 `pending_confirmation` 消息恢复
- **Phase 1 埋点**：prompt_tokens / completion_tokens / total_tokens / iterations / llm_calls / tool_calls / outcome（`agent_turn_metrics` 日志）
- **Phase 3 上下文预算**：window_messages / tool_result_max_chars / tool_result_keep_recent 由 Settings 注入
- **L2 跨会话记忆**：memory_index_segment + load_relevant_memories + fire-and-forget `_do_extract_after_turn`

### 3.3 共享循环体（关键架构选择）

来源：[`react_loop.py` L277–L413](./../backend/app/domain/agent/react_loop.py)

```python
async def _drive_react_loop(session_id, history, device_id) -> AsyncIterator[dict]:
    """共享 ReAct 循环体。两入口做完各自起点差异后委托到此。"""
    settings = get_settings()
    llm = LLMClient(settings)
    factory = get_session_factory()
    scope = scope_key(device_id, session_id)

    async with factory() as session:
        memory_service = MemoryService(session)
        memory_index_segment = await memory_service.build_memory_segment(scope)
        memory_block = await memory_service.load_relevant_memories(scope, history)

    agg = _new_metrics()
    for _iteration in range(MAX_REACT_ITERATIONS):
        messages = build_messages(history, memory_index_segment=memory_index_segment, ...)
        messages = _apply_memory_prepend(messages, memory_block)
        response = await llm.chat_with_tools(messages=messages, tools=TOOLS)
        ...
```

**优点**：

- DRY：两个入口（run_agent_turn / run_agent_turn_from_checkpoint）都委托到 `_drive_react_loop`，行为完全一致
- 显式事件契约：SSE 事件 schema 在注释中明确定义
- Phase 1/2/3 演进叠加在同一个循环体（埋点 → 上下文预算 → 记忆）

### 3.4 错误处理

来源：[`react_loop.py` L352–L393](./../backend/app/domain/agent/react_loop.py)

```python
try:
    result = await executor.execute(tool_name, tool_args)
except Exception as exc:
    from app.domain.exceptions import HumanConfirmationRequired
    if isinstance(exc, HumanConfirmationRequired):
        _emit_metrics(agg, ..., "human_confirmation")
        yield {"event": "human_confirmation_required", ...}
        return
    err_payload = {"error": f"{type(exc).__name__}: {exc}"}
    # 写错误为 tool 消息,继续下一轮
    ...
    yield {"event": "tool_call_result", "result": err_payload}
    continue
```

**优点**：

- `HumanConfirmationRequired` 单独识别，触发确认事件并暂停
- 其他异常包装为 tool 消息并继续下一轮（不中断 Loop）
- 异常信息带类型名（便于 LLM 决策）

**潜在风险**：

- `noqa: BLE001` 宽泛捕获，可能吞掉编程错误（KeyError、TypeError）当作业务失败
- `_do_extract_after_turn` 失败静默（仅 warning 日志）—— 记忆可能丢失但用户无感

### 3.5 配对保证（值得点赞）

来源：[`react_loop.py` L82–L98](./../backend/app/domain/agent/react_loop.py)

```python
# 只保留有对应 tool 结果的 tool_call；丢弃 dangling 的
# (HumanConfirmation / 被中断的流会留下无结果的 tool_call)，
# 并跳过孤儿 tool 结果。
# 否则严格 provider 报 'tool call result does not follow tool call' 400。
resolved_ids = {msg["tool_call_id"] for msg in history ...}
declared_ids = set()
for msg in history:
    if msg.get("role") == "assistant" and msg.get("tool_calls"):
        ...
kept_ids = resolved_ids & declared_ids
```

这是**容易被忽视但很关键的工程细节**：HumanConfirmation 中断后历史可能不完整，直接发给 provider 会 400。GEO2 在 build_messages 层做了显式配对保证。

## 4. 评分与理由

**评分：4 / 5（良好）**

| 维度 | 现状 | 评分贡献 |
| --- | --- | --- |
| 链路完整 | ✓ 用户输入 → LLM → tool → LLM → ... → turn_complete | +1 |
| 状态保存 | ✓ 每个事件后写 DB | +1 |
| 最大轮次限制 | ✓ MAX_REACT_ITERATIONS=7（但硬编码） | +0.5 |
| 上下文裁剪 | ✓ Phase 3 已落地 | +1 |
| 断点续跑 | ✓ run_agent_turn_from_checkpoint | +1 |
| 审计轨迹 | ✓ agent_turn_metrics 结构化日志 | +0.5 |
| 错误注入可控 | ✗ 无故障注入工具 | - |
| Loop 可视化 | ✗ 仅 metrics，无 replay/debug 工具 | - |
| 可回放 | ✗ 历史可重放但无显式 replay API | - |

**关键证据**：

- 强项在"工程化基础"（链路、状态、限轮、断点续跑、埋点）
- 弱项在"可观测性与可调试性"（故障注入、可视化、回放）

**与行业标准差距**：

- 与 LangGraph / Claude Agent SDK 比：缺内置可视化与 checkpoint UI
- 与 OpenAI Swarm 比：断点续跑更强（DB 持久化）
- 与内部"卓越"标准（5 分）比：缺 replay 工具

## 5. 面试讲点

### 30 秒版本

> 我们自写 ReAct 循环（不引 LangGraph），MAX=7 防无限循环，SSE 流式 7 类事件，写类工具抛 HumanConfirmationRequired 暂停 + 断点续跑，Phase 1/2/3 演进叠加在共享循环体。

### 2 分钟版本

1. **架构选择**：为什么不引 LangGraph？（可控性 + 学习价值 + 依赖最小化）
2. **核心机制**：
   - SSE 事件契约（7 类事件，schema 在注释）
   - `HumanConfirmationRequired` 异常驱动暂停
   - 断点续跑从 `pending_confirmation` 消息恢复
3. **Phase 演进**：
   - Phase 1：埋点（tokens / iterations / outcome）
   - Phase 2：L2 记忆（memory_index_segment + fire-and-forget extract）
   - Phase 3：上下文预算（窗口 + 工具截断）
4. **关键工程细节**：`build_messages` 的"配对保证"——防止 dangling tool_call 触发 provider 400

### 追问预判

| 追问 | 回答要点 |
| --- | --- |
| 为什么 MAX=7？ | 业务路径分析：list → search → create_task 是最长的"读 → 读 → 写"链路 |
| LLM 调用失败怎么办？ | 目前依赖 `await llm.chat_with_tools` 自然抛出，没有显式降级（**诚实回答**） |
| 上下文超限怎么处理？ | Phase 3 滑动窗口 + 工具结果截断；保全最近 N 个工具结果全量 |
| 断点续跑能跨实例吗？ | 依赖 DB 历史，可以（同一 session_id 即可），无显式 checkpoint 机制 |

## 6. 改进建议

| 优先级 | 改进项 | 关联 |
| --- | --- | --- |
| P1 | 提取 MAX_REACT_ITERATIONS 到 Settings（与上下文预算对齐） | 见 `99-improvement-plan.md` |
| P1 | 提取嵌套 `async with factory() as session` 为依赖注入 | 见 `99-improvement-plan.md` |
| P1 | LLM 调用失败的显式降级（超时 / 429 / provider error） | 见 `99-improvement-plan.md` |
| P2 | 故障注入工具（错误注入、断点模拟） | 见 `99-improvement-plan.md` |
| P2 | 显式 replay API（基于历史回放整个 turn） | 见 `99-improvement-plan.md` |
| P2 | 移除 `noqa: BLE001` 宽泛捕获，区分业务异常与编程异常 | 见 `99-improvement-plan.md` |

> 注：v0.6 已通过 `d3315d9 refactor(memory): 消除代码审查发现的重复与死码` 处理部分重复，本维度的"嵌套 async with"仍是改进候选。