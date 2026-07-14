# GEO2 引入 LangGraph 替换 react_loop 主循环 — 设计 spec

| 字段 | 值 |
| --- | --- |
| 日期 | 2026-07-14 |
| 状态 | 设计完成,待用户复核 |
| 关联 spec | [`2026-07-14-geo2-multi-agent-design.md`](./2026-07-14-geo2-multi-agent-design.md) / [`2026-07-14-geo2-upgrade-design.md`](./2026-07-14-geo2-upgrade-design.md) |
| 项目地图 | [`../../AGENTS.md`](../../AGENTS.md) |
| 锐评基线 | 总分 50/55 A+ 卓越(多 Agent 改造后) |

---

## 0. 与既有决策的关系(必须先看)

本次引入与既有两条硬约束相接,**scope 严格锁定为单点替换**:

### 0.1 与 AGENTS.md §6.5「不引入 LangGraph」的修订

§6.5 当前禁令:**❌ LangGraph / LangChain / LlamaIndex — 自写 ReAct 循环可控性 + 学习价值**。

本次修订:**§6.5 增加一条例外** — 当且仅当用于替换 `app/domain/agent/react_loop.py` 主循环时可引入 LangGraph。其余范围(领域服务 / 工具实现 / handoff 协议 / specialists)继续遵循原禁令。

> AGENTS.md 修订内容详见附录 A。

### 0.2 与 multi-agent spec §1.3 的边界

multi-agent spec §1.3 当前非目标:**不引入 LangGraph / LangChain / CrewAI / AutoGen 等任何外部框架**。

本次不修改该条款。本次 spec 与 multi-agent spec 的关系:

| 层 | LangGraph | 备注 |
|---|---|---|
| **主循环层**(本次替换区域) | ✅ | 单点替换 `react_loop.py` |
| **specialists 实现层**(`content_writer` / `monitor`) | ❌ | 仍手写 + handoff 协议 |
| **handoff 协议层**(`handoff.py` / `handoff_log_repo`) | ❌ | 仍手写 |
| **工具实现层**(`tools.py` / `tool_executor.py`) | ❌ | 仍手写 |

也就是说,**LangGraph 的边界严格止于 `react_loop.py` 单文件**。这条边界在 spec 全文多次复述,实施时必须用 import-linter 阻断越界。

### 0.3 为什么「范围锁定」而不是「全栈 LangGraph」

- 刚定稿的 multi-agent spec(50/55 A+,740 测试)是基于「手写 specialist + handoff 协议」的简历定稿
- 全栈 LangGraph 会重写 handoff 协议与 2 specialist,覆盖简历定稿
- 范围锁定可拿到「正确评估框架并生产化整合」这张简历牌,而保留多 Agent 改造的当前形态
- 回滚路径短:flag 一行即可

---

## 1. 背景与目标

### 1.1 多 Agent 改造后现状(2026-07-14)

- 总分 **50/55 A+ 卓越**
- 测试覆盖 **740 个**,pytest 全绿
- handoff 协议 + 2 specialists(5 条工程纪律全部完整实现)
- LLM-as-judge 评测基线(spec A1 关键修复)
- 主循环仍是手写 `react_loop.py`(725 行)

### 1.2 改造动机

**两层动机**:

1. **工程动机(主)**:`react_loop.py` 维护成本继续上升(7 类 SSE 事件 / L2 prepend / 4 策略压缩 / token 截断可解释 / pending_confirmation 持久化都耦合在一个 .py 文件),正确评估框架并生产化整合能在控制风险前提下降低主循环维护成本
2. **简历动机(辅)**:在「自写 ReAct + 多 Agent」已打下底子的项目里**正确选型引入 LangGraph**,展示 senior 工程师最稀缺的判断力 — 「何时用 / 何时不用 / 怎么回滚」

### 1.3 目标

1. `react_loop.py` 主循环用 `create_react_agent` + 自定义 node 替换
2. 7 类 SSE 事件字节级兼容(前端零改动)
3. `pending_confirmation` 字段 ↔ LangGraph checkpoint 双向兼容(已有会话可恢复)
4. L2 memory / 4 策略压缩 / token 截断可解释 行为对齐
5. evals 双跑通过 95% 一致门槛 + 灰度 1 周后切流
6. 一行 flag 回滚

### 1.4 非目标(防扩散)

- ❌ 不重写 multi-agent specialist 实现
- ❌ 不重写 handoff 协议
- ❌ 不引入 LangChain 链式 API(`Chain` / `LCEL`)
- ❌ 不重写 SSE 协议字节级事件
- ❌ 不动 `LLMClient` 多 provider 抽象
- ❌ 不重写 ORM 会话表(仅加 1 个可空列)
- ❌ 不修改 `import-linter` 反向依赖规则

---

## 2. 范围与边界

### 2.1 替换区域(单点)

| 文件 | 现状 | 替换后 |
|---|---|---|
| `backend/app/domain/agent/react_loop.py` | 725 行手写主循环 | 拆分为 LangGraph 入口 + 6 个自定义 node;725 → ~250 行 |

### 2.2 不变区域(白名单)

```
backend/app/domain/agent/
  ├── prompts.py              ← 不动
  ├── session_manager.py      ← 不动(只加 langgraph_thread_id 字段读取)
  ├── memory.py               ← 不动(L2 逻辑整包给 MemorySnapshotNode 用)
  ├── memory_vector.py        ← 不动
  ├── summarizer.py           ← 不动
  ├── pending_timeout.py      ← 不动
  ├── adaptive_compression.py ← 不动(整包给 TruncateMessagesNode 用)
  ├── truncation_explainable.py ← 不动
  ├── tool_executor.py        ← 不动(7 类 SSE 事件继续产出,但 SSEBridge 接)
  ├── tools.py                ← 不动(5 个 schema 升级为 @tool 包装)
  ├── handoff.py              ← 不动
  ├── content_writer_specialist.py ← 不动
  ├── monitor_specialist.py   ← 不动(MonitorSpecialist 在 monitor/ 子目录)
backend/app/domain/llm_client.py   ← 不动(LangGraph 调用 LLMClient,不替换)
backend/app/api/agent_chat.py      ← 不动(只在 dispatch 加 flag)
backend/evals/                     ← 不动(只新增 --compare 子模式)
backend/data/                      ← 不动
```

### 2.3 数据 schema 最小变更

`agent_sessions` 表新增 1 个可空列:

```sql
ALTER TABLE agent_sessions ADD COLUMN langgraph_thread_id TEXT;
```

列用途:LangGraph `MemorySaver` 的 thread_id 必须稳定才能 `Command(resume=...)`;直接复用 `id` 也可,但拆开列便于将来切换 `PostgresSaver`。nullable 默认 NULL。

---

## 3. 架构

### 3.1 架构总览

```
User message
     │
     ▼
api/agent_chat.py                 ← API 入口,不改
     │
     ▼
run_agent_turn()                  ← dispatch by Settings.langgraph_enabled
     │
     ├─ False → _drive_react_loop (现有路径,保留 1 个里程碑)
     │
     └─ True  → react_graph.astream_events(state, config={"thread_id": session_id_or_langgraph_thread_id})
                     │
                     ▼
                 react_graph (CompiledStateGraph)
                   ├─ agent_node           ← LangGraph prebuilt 的 ReAct 单步
                   ├─ tool_node            ← 5 个 @tool schema
                   ├─ interrupt_guard      ← interrupt() ↔ HumanConfirmationRequired
                   ├─ MemorySnapshotNode   ← 自定义:build_messages + L2 prepended
                   ├─ TruncateMessagesNode ← 自定义:adaptive_compression + token truncation
                   ├─ PolicyNode           ← 自建 retry 策略(transient/programming)
                   ├─ SSEBridge            ← 自建:astream_events → 7 类 SSE 输出
                   └─ CheckpointAdapter    ← 自建:checkpoint ↔ pending_confirmation + langgraph_thread_id

外部不变:
  tool_executor.execute()
  handoff / specialists / services / repositories / models
```

### 3.2 三层抽象边界

| 层 | 谁拥有 | 不变量 |
|---|---|---|
| **主循环(替换区域)** | LangGraph `CompiledStateGraph` | 单 turn 内的 state transitions,可观测、可回放 |
| **工具调用(specialist 委派)** | `tool_executor.py`(不动) | handoff 协议与降级保持完全一致 |
| **领域服务(services / repositories / models)** | 全部不动 | `import-linter` 不破 |

---

## 4. 组件设计

### 4.0 LLM 链路(明确)

`react_graph` 内的 `agent_node` **不**直接调用 LangGraph 自带的 `init_chat_model(provider:model)` 字符串,而是调用现有 `LLMClient(...)`。理由:

- `LLMClient` 已封装 provider 抽象 + retry + cost 计算 + transient 区分
- 替换会导致多 provider 抽象破坏(被 §1.4 非目标明确禁止)
- LangGraph 的 model 接收签名仍可用:`react_graph(ChatModel, tools=...)` 把 `LLMClient` 包成 LangChain `BaseChatModel` 适配即可

### 4.1 LangGraph prebuilt 组件(直接用,不包装)

| 组件 | import 路径 | 用法 |
|---|---|---|
| `create_react_agent` | `langgraph.prebuilt` | agent 主入口,接 LLMClient + 5 个 @tool |
| `MessagesState` | `langgraph.graph.message` | 状态基类,`messages` 自动 add reducer |
| `ToolNode` | `langgraph.prebuilt` | 5 个工具 schema 的 dispatch |
| `MemorySaver` | `langgraph.checkpoint.memory` | 内存 checkpointer,本期先用(PostgresSaver 留 §13 风险) |
| `interrupt` / `Command(resume=...)` | `langgraph.types` | HITL 暂停 / 恢复 |

pin 版本:`langgraph>=1.0,<2.0`(v1.0+ API 稳定,避免 v2 breaking)。

### 4.2 自定义节点(自建,完整 spec)

#### 4.2.1 `SSEBridge`(7 类事件字节级兼容)

位置:`backend/app/domain/agent/langgraph_nodes/sse_bridge.py`(新目录)

```python
class SSEBridge:
    """把 LangGraph astream_events 输出映射回 react_loop 7 类 SSE 事件。

    契约:输出字节级兼容现有前端 SSE 协议(responses/sse_v04/)。
    """

    async def __call__(self, state, config) -> dict:
        # astream_events + get_stream_writer
        # 映射规则见 §7
        ...
```

#### 4.2.2 `CheckpointAdapter`(双向持久化桥接)

位置:`backend/app/domain/agent/langgraph_nodes/checkpoint_adapter.py`

```python
class CheckpointAdapter:
    """agent_sessions.pending_confirmation ↔ LangGraph checkpoint 双向投影。"""

    async def load_or_init(self, session_id: str) -> tuple[StateSnapshot, str]:
        """读 agent_sessions;首次发起写 langgraph_thread_id(uuid4)并落表。"""

    async def persist(self, session_id: str, snapshot: StateSnapshot) -> None:
        """把 LangGraph checkpoint 投影到 pending_confirmation JSONBlob。"""

    async def round_trip(self, session_id: str) -> bool:
        """测试用:持久化 → 重新加载,深比较是否一致。"""
```

#### 4.2.3 `MemorySnapshotNode`(L2 记忆 prepend)

位置:`backend/app/domain/agent/langgraph_nodes/memory_snapshot.py`

```python
class MemorySnapshotNode:
    """对接 app/domain/agent/memory.py 的全部既有公开函数:
    - MemoryService.select_relevant(scope, query) -> top-k
    - build_messages(scope, conversation, memory_chunk)
    - _apply_memory_prepend(...)
    输入:state 中的 user message
    输出:state.messages 在 user 前 prepend 记忆(NOT 进 system,保留 react_loop 现有语义)
    """
```

#### 4.2.4 `TruncateMessagesNode`(adaptive compression + truncation)

位置:`backend/app/domain/agent/langgraph_nodes/truncate_messages.py`

```python
class TruncateMessagesNode:
    """对接 app/domain/agent/adaptive_compression.py 4 策略:
    noop / truncate / drop / summarize + truncation_explainable 的 TruncationResult。
    保留 state.messages 字节级一致;产出 TruncationResult dict 用于日志与 metrics。
    """
```

#### 4.2.5 `PolicyNode`(transient/programming 区分 + retry)

位置:`backend/app/domain/agent/langgraph_nodes/policy.py`

```python
class PolicyNode:
    """复用 _LLM_TRANSIENT_EXCEPTIONS 与 _TOOL_TRANSIENT_EXCEPTIONS。
    - transient:LangGraph 自带 RetryPolicy(max_retries >= 3, exp backoff)
    - programming:不重试,直接产 llm_error SSE
    """
```

### 4.3 状态 schema

```python
# backend/app/domain/agent/state.py (新)
from langgraph.graph.message import MessagesState
from app.domain.agent.memory import MemoryChunk

class AgentState(MessagesState):
    # LangGraph 标准 messages 字段(由 MessagesState 提供 add reducer)
    # 项目专属字段(可选)
    session_id: str
    memory_chunk: MemoryChunk | None
    truncation_result: dict | None
    tool_call_log: list[dict]  # 仅用于 Langfuse 追踪 / SSEBridge 聚合
```

---

## 5. 数据流

### 5.1 Turn 发起

```
POST /api/agent/chat { session_id?, message, device_id }
  ├─ api/agent_chat.run_agent_turn(...)
  ├─ if Settings.langgraph_enabled:
  │    ├─ factory = _get_session_factory()
  │    ├─ config = {"configurable": {"thread_id": session_id_or_langgraph_thread_id}}
  │    └─ async for event in react_graph.astream_events(state, config, version="v2"):
  │         └─ SSEBridge.dispatch(event)
  │              → yield "assistant_message" / "tool_call_start" / ... SSE 事件
  └─ else: 现有 react_loop._drive_react_loop(...)
```

### 5.2 单步流转(以 tool 调用为例)

```
agent_node(model_decision)
     │
     ├─ 是 tool_call → tool_node(tool_call_id, name, args)
     │      │
     │      ├─ HumanConfirmationRequired?(tool 抛)
     │      │      └─ interrupt(payload=...)
     │      │           └─ checkpoint persist + yield human_confirmation_required SSE
     │      │
     │      ├─ 走 specialist handoff(tool_executor 内部)
     │      │      └─ tool_executor._execute_generate_article(...)
     │      │           ├─ ContentWriterSpecialist.handoff(request)
     │      │           │      ├─ success → return result
     │      │           │      └─ failed / timeout → 降级 _execute_*_legacy
     │      │
     │      └─ 返回普通结果
     │
     └─ 是 final answer → end → yield turn_complete SSE
```

### 5.3 HITL 暂停 / 恢复

```
暂停:tool 抛 HumanConfirmationRequired
      └─ interrupt(payload={tool_call_id, args, resume_token})
           ├─ LangGraph checkpoint 自动持久化(snapshot 含 interrupt payload)
           ├─ CheckpointAdapter.persist 投影到 agent_sessions.pending_confirmation
           └─ yield human_confirmation_required SSE

恢复:POST /api/agent/sessions/{id}/resume { decision, args }
      ├─ resume_token + user decision 注入
      ├─ CheckpointAdapter.load 读取 thread_id
      ├─ react_graph.invoke(Command(resume=user_decision), config)
      │      └─ 从中断点继续走,产出 7 类 SSE
      └─ 完成后 CheckpointAdapter.persist 清空 pending_confirmation
```

---

## 6. Checkpoint 与持久化

### 6.1 表结构变化(最小)

```sql
-- 仅新增 1 个 nullable 列
ALTER TABLE agent_sessions ADD COLUMN langgraph_thread_id TEXT;
```

数据迁移:已有 session 行 `langgraph_thread_id = NULL`;首次发起时 CheckpointAdapter 写 uuid4 落表。

### 6.2 CheckpointAdapter 双向映射

| LangGraph 概念 | 现状字段 |
|---|---|
| `thread_id` | `langgraph_thread_id` (新) |
| `checkpoint_ns` | 默认 "" |
| `state_snapshot.values["__interrupt__"]` | `pending_confirmation` JSON |
| `state_snapshot.values["messages"]` | 暂不持久化(由 react_loop 现有 messages 表承担) |

限制:LangGraph `MemorySaver` 内存级,不重启。**生产环境需切到 `PostgresSaver`(留 §13 风险条目,不在本期实现)。**

### 6.3 持久化策略

- **每步写**:持久化太频繁,只持久化 pending_confirmation 与 langgraph_thread_id
- **turn end**:写入一次 final snapshot(用于断点续跑 / replay)
- **checkpoint purge**:handoff_log_retention_days 到期清理(沿用 v0.7+# 配置)

---

## 7. SSE 事件桥接(SSEBridge)

### 7.1 映射表

| react_loop SSE 事件 | LangGraph 事件源 | SSEBridge 行为 |
|---|---|---|
| `assistant_message` | `on_chat_model_stream` chunk | 拼 token → emit;满阈值/换行则断流 |
| `tool_call_start` | `on_tool_start` | emit 名字 + args |
| `tool_call_result` | `on_tool_end` | emit 返回值(剔除 PII) |
| `human_confirmation_required` | `__interrupt__` 触发 | emit payload + langgraph_thread_id |
| `turn_complete` | graph 终态 | emit final response metadata |
| `max_iterations_reached` | `recursion_limit` exceeded | emit 与 react_loop 完全相同文案 |
| `llm_error` | chat_model 异常 | emit `transient` / `programming` 标志 |

### 7.2 字节级兼容性

保证 `responses/sse_v04/` snapshot 全等(snapshot 测试):

```python
# backend/tests/test_sse_bridge_compat.py
async def test_sse_bridge_outputs_byte_identical_to_react_loop():
    """输入同一组 user / LLM stub → SSEBridge 输出与 react_loop 输出 byte-identical"""
```

### 7.3 异常事件格式

```json
{
  "type": "llm_error",
  "transient": true,
  "error": "rate_limit_exceeded",
  "retry_count": 2
}
```

与 react_loop 现有格式保持一致,不破坏前端解析。

---

## 8. 记忆与压缩

### 8.1 L2 memory prepend

react_loop 现有契约:`_apply_memory_prepend` 把 `memory_chunk` 拼到 user 消息**之前**,不进 system。

迁移:`MemorySnapshotNode` 在每次 LLM call 前消费 `state.memory_chunk`,prepend 到最后一条 user 消息。LangGraph `MessagesState` 不限制这种 prepend 行为。

### 8.2 4 策略自适应压缩

```python
# 走 react_loop 现有 adaptive_compression.select_strategy(state.messages)
# 4 策略:noop / truncate / drop / summarize
# TruncateMessagesNode 内部直接调用
```

### 8.3 Token 级截断可解释

`truncation_explainable.TruncationResult` 字段:

```python
@dataclass
class TruncationResult:
    saved_tokens: int
    decisions: list[dict]  # 每条消息的 decision + 节省 token 数
```

`TruncateMessagesNode` 把 TruncationResult 写回 `state.truncation_result`,用于日志与前端 metrics。

---

## 9. 失败处理与重试

### 9.1 Transient 异常

沿用 react_loop 现有 `_LLM_TRANSIENT_EXCEPTIONS` / `_TOOL_TRANSIENT_EXCEPTIONS`:

```python
# PolicyNode 内部
@retry(
    retry=retry_if_exception_type(_LLM_TRANSIENT_EXCEPTIONS),
    stop=stop_after_attempt(settings.max_retries),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def call_llm_node(state): ...
```

`settings.max_retries` 默认 ≥3(env 可覆盖)。

### 9.2 Programming 异常

不重试,直接产 `llm_error` SSE(transient=False),由 SSEBridge emit。

### 9.3 Tool 调用失败

不修改 `tool_executor.py` 现有降级路径。`tools.py` 的工具 schema 升级为 LangChain `@tool` 包装,但 executor 内部分发逻辑保留。

---

## 10. 灰度与回滚

### 10.1 Evals 双跑灰度(本 spec 最关键不变量)

```
backend/evals/runner.py --compare
  ├─ 同一 cases 分别跑 react_loop + langgraph
  ├─ 输出两份 text snapshot + tool_call_match + handoff_event_match + SSE_event_count
  ├─ diff 报告 reports/eval/diff/<date>.md
  └─ 通过门槛:
       - overall_text_match ≥ 95% (LLM 输出本质非确定性)
       - tool_call_match = 100%
       - handoff_event_match = 100%
       - SSE_event_count 相等
```

实施步骤:
1. Sprint 0 跑 baseline react_loop(同 input 多次取平均)
2. Sprint 4 跑 langgraph 同样 input
3. diff 报告归档
4. 通过门槛才允许切流

### 10.2 Feature flag

```python
# backend/app/core/config.py (Settings 新增)
class Settings(BaseSettings):
    # 现有字段...
    langgraph_enabled: bool = False  # 默认 False,沿用 react_loop
```

```python
# backend/app/domain/agent/dispatch.py (新增)
async def run_agent_turn(...):
    if get_settings().langgraph_enabled:
        async for sse in run_langgraph_turn(...):
            yield sse
    else:
        async for sse in run_react_loop_turn(...):  # 现有路径
            yield sse
```

### 10.3 回滚策略

| 阶段 | 回滚成本 | 操作 |
|---|---|---|
| 双跑灰度(react=primary, langgraph=shadow) | 一行 flag | `langgraph_enabled = False` |
| 切流后发现 bug | 一行 + 数据迁移 | flag 切回 + 用 checkpoint 恢复中转 |
| 切流 2 周后稳定 | git revert | revert 替换主循环的 PR;`react_loop.py` 不删保留 1 个里程碑 |
| 1 个里程碑后 | 删 react_loop.py | 全部路径走 LangGraph;`react_loop.py` 注释为 deprecated,提醒下游 consumer |

### 10.4 切流前置条件

- [ ] evals 双跑 diff 通过 ≥ 95% 一致门槛
- [ ] `pytest backend/tests/` 全绿
- [ ] ruff + mypy 干净
- [ ] `responses/sse_v04/` snapshot 字节级一致
- [ ] 灰度期至少 5 天无生产事件
- [ ] checkpointer 内嵌 thread_id 持久化已上线

---

## 11. 测试策略

| 层级 | 必跑 | 工具 |
|---|---|---|
| **单元** | LangGraph 自定义 6 个 node | pytest |
| **集成** | `react_graph.astream_events` 跑固定输入,产出 SSE event 流 | snapshot 测试 |
| **adapter** | CheckpointAdapter round-trip 双向 | pytest + frozen fixtures |
| **e2e** | `POST /chat` 全链路(含 specialist handoff 触发) | pytest |
| **evals** | `evals/runner.py --compare` | LLM-as-judge + diff |
| **import-linter** | `tests/test_no_repo_to_service.py` | 阻断反向依赖 |
| **lint/types** | ruff + mypy | CI |
| **byte-identical SSE** | `responses/sse_v04/` snapshot | pytest snapshot |

---

## 12. 实施顺序(Sprint 级别,Sprint 2 周)

### Sprint 1:基础设施
- T1 写本 spec + plan(本轮已完成到 T6)
- T2 [RED] `evals/runner.py --compare` 双跑入口(无实现)
- T3 [GREEN] 最小 `react_graph`(单 chat + 5 个工具 stub),输出骨架 SSE
- T4 [GREEN] SSEBridge 把 LangGraph astream_events 投影对齐

### Sprint 2:HITL / checkpoint
- T5 CheckpointAdapter 双向 round-trip + 测试 + `langgraph_thread_id` 列迁移
- T6 `interrupt()` / `Command(resume=...)` 桥接 + `human_confirmation_required` 事件对齐
- T7 `agent_sessions` 表 `langgraph_thread_id` 列迁移 + 兼容老 session

### Sprint 3:L2 记忆 / 压缩 / 截断
- T8 MemorySnapshotNode(包 `build_messages` + L2 prepended)
- T9 TruncateMessagesNode(包 `adaptive_compression` + `truncation_explainable`)
- T10 PolicyNode(包 transient/programming 区分 + retry)

### Sprint 4:双跑灰度 / 切流
- T11 evals 双跑 diff 报表 ≥ 95%
- T12 Settings.`langgraph_enabled` 默认 False,前线不动
- T13 灰度期 1 周,日志/指标观测 langgraph path
- T14 flag 切 True,`react_loop.py` 标 deprecated
- T15 `react_loop.py` 标记保留 1 个里程碑(本期不删)

---

## 13. 风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| LangGraph v1 → v2 breaking | 中 | pin `langgraph>=1.0,<2.0`;订阅 release notes |
| LLMClient 多 provider 抽象被打破 | 中 | `react_graph` 调用 `LLMClient`,不替代 |
| `MemorySaver` 进程内不持久 | 高 | 生产化需 `PostgresSaver`(本期留 TODO) |
| LangGraph 1.x prebuilt API 改签名 | 中 | 订阅 release notes;`create_react_agent` 签名锁版 |
| 灰度期与 multi-agent 改造重合导致 diff 难以定位 | 低 | 灰度必须在 multi-agent 改造完成 ≥ 1 周后启动 |
| `pending_confirmation` 老 schema 不带 LangGraph 兼容字段 | 低 | CheckpointAdapter 首次加载时 lazy 补 `langgraph_thread_id` |
| evals diff 因 LLM 非确定性失败 | 中 | diff 用 95% token-Rouge 阈值,track 多 run 平均 |
| LangGraph 引入拖慢 P95 延迟 | 中 | 灰度期 P50/P95 埋点观测;失败转回 react_loop |
| import-linter 越界(react_loop 引入 langgraph 类型反向泄漏) | 中 | 单测 + linter 双向检查 |
| LangGraph 生态依赖体积增长 | 低 | 仅 langgraph SDK 入 requirements.txt |

---

## 14. 成功标准

- ✅ evals 双跑 diff ≥ 95% 一致
- ✅ `responses/sse_v04/` snapshot 字节级一致
- ✅ `pytest backend/tests/` 全绿(740 → 800+)
- ✅ `ruff check app/` + `mypy` 干净
- ✅ `import-linter` 不破
- ✅ LangGraph + 现有 telemetry(Sentry/Langfuse/Prometheus)兼容
- ✅ `langgraph_enabled = True` 后 ≥ 5 天线上无降级
- ✅ 一个里程碑后 `react_loop.py` 可删除

---

## 15. 附录

### 附录 A:AGENTS.md §6.5 修订草案

```diff
 ### 6.5 不引入新框架

-❌ LangGraph / LangChain / LlamaIndex — 自写 ReAct 循环可控性 + 学习价值
+❌ LangGraph / LangChain / LlamaIndex — 自写 ReAct 循环可控性 + 学习价值
+✅ 例外:`app/domain/agent/react_loop.py` 主循环可使用 `langgraph>=1.0,<2.0`
+  (详见 `docs/superpowers/specs/2026-07-14-langgraph-react-loop-design.md`)
 ❌ 改 ORM 版本结构(orm_v02-v04 演进历史保留)
 ❌ 改业务逻辑(仅工程化补强)
```

### 附录 B:multi-agent spec §1.3 保持不变

multi-agent spec §1.3「不引入 LangGraph / LangChain / CrewAI / AutoGen」条款**整体保持**,仅适用于 specialist / handoff 协议层。

### 附录 C:react_loop.py 被替换的接口清单

```
_drive_react_loop        → 由 react_graph.astream_events + ainvoke 取代
run_agent_turn           → api/agent_chat.dispatch
run_agent_turn_from_checkpoint → 由 react_graph.invoke(Command(resume=...)) + CheckpointAdapter 取代
_build_messages          → MemorySnapshotNode
_apply_memory_prepend    → MemorySnapshotNode 内部
adaptive_compress        → TruncateMessagesNode(选策略 + 实施)
truncate_messages        → TruncateMessagesNode
LLM call + retry         → PolicyNode
pending_confirmation 持久化 → CheckpointAdapter + agent_sessions.pending_confirmation
流式 SSE 7 事件           → SSEBridge
max_iterations 守卫       → LangGraph recursion_limit = Settings.max_react_iterations + 1
```

### 附录 D:为什么不直接走 Deep Agents

LangGraph 仓库新近发布 **Deep Agents** 包(built on LangGraph,带 planning / subagents / file system)— 是更高层抽象。本次不引入,理由:
- scope 锁定 react_loop 主循环单点;Deep Agents 会把 multi-agent 编排权也接管,与 multi-agent spec §1.3 冲突
- Deep Agents 内置 subagent 调度,与项目「主 Agent → 工具 → specialist handoff」的三层架构不相容
- 留给未来选项(spec §1.4 排除项 「不引入 LangChain 链式 API」仍生效)
