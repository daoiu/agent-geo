# LangGraph vs react_loop Parity Gate — 2026-07-17

**Plan:** ②a agent 路径统一到 LangGraph(plan 2026-07-17-agent-path-unify-langgraph.md,T9)

**目标指标**(硬门槛,plan Task 9):
- `overall_match ≥ 0.95`(ROUGE-L assistant_message 内容相似度)
- `tool_call_match == 1.0`(react_loop vs langgraph 工具集合完全一致)
- `handoff_match == 1.0`(human_confirmation_required 事件数量一致)
- `sse_event_count_equal == True`(两路径 SSE 事件数量完全一致)

---

## 实测结果(2026-07-17 17:42,10 cases from EVAL_CASES[:10])

```
overall_match: 0.018          (目标 ≥0.95)        ❌ 严重不达标
tool_call_match: 0.1          (目标 ==1.0)        ❌ 严重不达标
handoff_match: 1.0            (目标 ==1.0)        ✅ 达标
sse_event_count_equal: false  (目标 ==True)       ❌ 不达标
```

**结论:** parity gate **未通过**,T10 删除 react_loop **暂不执行**。

---

## 根本原因分析(初步)

1. **overall_match 0.018** — 两条路径的 LLM 实际调用产出差异显著(都是真 LLM 调用,
   不同 provider 配置 / cache 命中 / 工具调用次数导致 response 内容不同)。
   真实 LLM 调用是非确定性输出,即使 prompt 完全一致,token-level 也会不同。

2. **tool_call_match 0.1** — 90% cases 工具集合不一致,推测:
   - react_loop 走 handoff 路径(诊断任务 → ContentWriterSpecialist.handoff_batch),
     落 `handoff_log` 表
   - LangGraph 走 _tool_node 路径,直接调 tool_executor.execute,落 `agent_messages`
     表(role=tool)
   - 两条路径的工具暴露面/调用顺序/嵌套粒度差异导致 collection 不同

3. **sse_event_count_equal false** — 事件数量差异,与 tool_call 差异同源。

---

## 建议处置(plan 执行人视角)

按 plan 硬约束"T10 删除 react_loop 之前必须 T9 达标"。

**当前状态:** T1-T8 + T9 实施完成,parity gate 失败。

**可能路径:**
- **A. 接受当前 parity,保留 react_loop 路径**(放弃 plan 单路径目标,react_loop 作为
  fallback 长期共存)— 需用户决策,因为违反 plan 设计意图
- **B. 进一步 debug parity**(深入分析每 case 的 tool_call / event 差异,可能耗时长)— 需
  用户授权时间
- **C. 暂停 plan,人工介入**(parity 0.018 表明两条路径实质差异巨大,需要重新评估 plan)

## 关键证据(日志片段)

```
[17:41:51] agent_turn_metrics  iterations=2 llm_calls=2 tool_calls=2 outcome=turn_complete
       (react_loop: 2 LLM calls, 2 tool calls)
[17:41:51] agent_turn_metrics  iterations=0 llm_calls=0 tool_calls=0 outcome=turn_complete
       (langgraph: 0 LLM calls aggregated — SSEBridge metrics merge bug?)
```

`agent_turn_metrics iterations=0` 表明 LangGraph 路径 metrics 累计未生效(T4 实现
可能有 bug,但 unit 测试通过 — 可能 merge_metrics 逻辑与实际 astream_events 输出
不匹配)。