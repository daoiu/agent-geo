# 设计:②a Agent 路径统一到 LangGraph(重构)

> 日期:2026-07-17
> 范围:本 spec 只覆盖「②a 路径统一重构」。②b 编排层(Plan-Execute + Reflection + 复杂度 router)依赖本 spec 完成后另立。
> 性质:**纯重构,行为等价**,不加用户可见新功能。

## 背景

当前 agent 有两条并行执行路径:

- `react_loop.py`(**725 行**):手写 ReAct 驱动 `_drive_react_loop` + `run_agent_turn`(主入口)+ `run_agent_turn_from_checkpoint`(HITL 续跑)+ 消息构建 / token 截断 / 记忆 prepend / metrics。
- `react_graph.py`:LangGraph `StateGraph`(`START → memory_snapshot → agent →(tools|END)→ truncate → agent`),复用 `memory_snapshot_node` / `truncate_messages_node` 等节点。
- `dispatch.py`:按 `Settings.langgraph_enabled`(**默认 False**)在两者间路由 → **react_loop 才是当前生产路径**。
- `api/agent_chat.py`:HITL 续跑 `run_agent_turn_from_checkpoint` **硬绑 react_loop**,未走 dispatch。

代码注释("保留 1 个里程碑后删除"、"Task 14 前保留")表明代码库既定意图即最终全量转 LangGraph。两条路径重复实现、双 HITL 机制,维护成本高。

## 目标

LangGraph 成为**唯一** agent 执行路径,删除 `react_loop.py` 驱动逻辑;对外行为(8 类 SSE 事件、HITL 交互、降级语义)完全不变,用既有 `compare_evals` 证明等价后硬删旧路径。

## 决策记录(来自澄清)

- 统一方向:**统一到 LangGraph**(白拿 checkpoint / interrupt / streaming,契合 ②b 图编排)。
- 拆分:② = **②a 重构(本 spec)** + ②b 编排(后续)。
- parity gate:`compare_evals` 的 `overall_match ≥ 0.95`,且 `tool_call_match` / `handoff_match` 全等、`sse_event_count_equal` 为真。
- react_loop:**本期直接删**(不留逃生舱),`langgraph_enabled` flag 一并移除。

## 现状缺口(深读代码后的完整清单)

> ⚠️ LangGraph 路径是「结构 diff 里程碑」的骨架,非生产就绪。深读后确认缺口比初版大:

| 能力 | react_loop | LangGraph 现状 | 处置 |
|---|---|---|---|
| ReAct 主循环 | `_drive_react_loop` | ✅ react_graph | 保留图 |
| **DB 持久化(每条 assistant/tool 落库)** | `AgentRepository.create_message` | ❌ **完全缺失,历史不累积** | 图节点内补落库 |
| **记忆加载**(memory_chunk 填充 + index_segment) | `MemoryService.build_memory_segment` / `load_relevant_memories` | ❌ memory_chunk 恒 None | 补记忆预热节点 |
| 消息构建 / 记忆 prepend | `build_messages` / `_apply_memory_prepend` | 部分(memory_snapshot_node) | 抽纯函数共享 |
| token 截断 | `_truncate_by_tokens` | ✅ truncate_messages_node | 抽纯函数共享 |
| metrics 汇总 / 发射 / 成本 | `_emit_metrics` / `_accumulate` / `compute_cost` | ❌ 缺 | 补到图链路 |
| turn 后记忆蒸馏(fire-and-forget) | `_do_extract_after_turn` | ❌ 缺 | 补到图结束后 |
| **HITL 三种 kind** | decision / input / progress_confirm 全支持 | ⚠️ bridge 仅 `human_confirmation_required` | 补 input_required / progress_confirm |
| **HITL generate_article 确认续跑** | `run_agent_turn_from_checkpoint`(130 行) | ❌ 缺 | 图 resume + Command 重建 |
| assistant_message 事件 | 直接 yield | ⚠️ bridge 听 `on_chat_model_stream`,但 `_agent_node` 用非流式 `chat_with_tools`,可能不触发 | 改 bridge 从节点输出取 |
| tool_call_id 语义 | 真实 tc id | ⚠️ bridge 用工具名当 id | 对齐真实 id |
| 8 类 SSE 事件完整性 | ✅ | ⚠️ 需逐一核对 | 核对补齐 |

> 决策(仍本期直接删 react_loop):以上全部在图上重建到生产级 → parity gate 达标 → 同期删除 react_loop + flag。风险由 parity gate + 全绿测试 + 手动 HITL 走查兜底。

## 重构策略(消除重复,不重写)

1. **抽共享纯函数** → 新 `app/domain/agent/turn_helpers.py`:`build_messages` / `_truncate_by_tokens` / `_orm_to_dict` / `_apply_memory_prepend` / `_emit_metrics` / `_accumulate`。两路径先都 import 之,消除重复(此步零行为变化)。
2. **补齐缺口为图能力**:
   - metrics:在 `sse_bridge` 汇总 token/耗时并发 `turn_complete` 附带 metrics(对齐 react_loop 的 `_emit_metrics`)。
   - 记忆蒸馏:图结束后 fire-and-forget 调 `_do_extract_after_turn` 等价逻辑(持后台 task 防 GC)。
   - HITL 续跑:实现图的 checkpoint resume 入口(基于既有 `checkpoint_adapter` + LangGraph `MemorySaver`)。
3. **API 改线**:`agent_chat.py` 的 HITL resume 改调图 resume,不再 import react_loop。
4. **dispatch 简化**:`run_agent_turn` 直接走 LangGraph;移除 flag 分支与 `_run_react_loop_turn`。
5. **移除**:`Settings.langgraph_enabled` 字段 + react_loop 驱动函数(纯函数已迁走)。

## 安全网(行为等价怎么证)

- **`compare_evals`(已存在于 `evals/runner.py`)**:重构关键步骤前后跑 react_loop vs LangGraph diff,直至删除前最后一次证 `overall_match ≥ 0.95` 且 tool/handoff 全等、SSE 数一致。
- 现有 pytest 全绿(agent tools / langgraph flag / checkpoint_adapter / L2 memory 等)。
- 手动 HITL 走查:确认 / 拒绝 / 续跑三路径。

## 数据流 & 错误处理

- 对外**完全不变**:同样 8 类 SSE 事件(`assistant_message` / `tool_call_start` / `tool_call_result` / `human_confirmation_required` / `input_required` / `progress_confirm` / `turn_complete` / `llm_error`)、同样 HITL、同样降级。仅内部收敛为单图。
- LangGraph 工具错误映射到与现状一致的 `tool_call_result(error)` / `llm_error` 事件;transient / 编程错误分离保持不变。

## 测试

- **parity gate**:`compare_evals` diff 达标(见上)。
- **迁移单测**:图 HITL resume 节点(续跑产出与 react_loop 等价)、metrics 发射、extract-after-turn 触发。
- **回归**:现有 agent 测试不改语义全绿;删 react_loop 后无悬空 import。

## 风险与回滚

- 小步提交:抽纯函数(零行为)→ 补缺口 → 切默认 → parity 证一致 → 删 react_loop + flag。每步独立 commit,出问题按 commit 回滚。
- 直接删 react_loop 的风险由 parity gate + 全绿测试 + 手动 HITL 走查共同兜底。

## 交付物

1. `app/domain/agent/turn_helpers.py`(共享纯函数)+ 单测。
2. LangGraph 补齐:metrics / 记忆蒸馏 / HITL resume。
3. `dispatch.py` 简化、`agent_chat.py` 改线、`config.py` 删 flag。
4. 删除 `react_loop.py` 驱动逻辑。
5. parity 报告(`compare_evals` 结果留档)。

## 非目标(归 ②b 或明确排除)

- Plan-Execute 模式、ReflectionAgent 评分重试、复杂度 router、运行时升降级 → **②b**。
- 不改工具集、不改 SSE 契约、不改前端、不改记忆三层架构。
