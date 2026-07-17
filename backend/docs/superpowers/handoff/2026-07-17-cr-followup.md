# code-review Follow-up — ②a Agent 路径统一到 LangGraph

**Date:** 2026-07-17
**Plan:** `docs/superpowers/plans/2026-07-17-agent-path-unify-langgraph.md`
**Reviews:**
- Standards: 2 项 Duplicated Code(已修 CR-1)
- Spec: 7 项违反(已修 CR-2/3/4/5;CR-6 留档历史已知问题)

---

## 已修复(commit 待合并)

### CR-1 — Standards: Duplicated Code(`sse_bridge` vs `memory_preheat`)
**根因:** 两处独立实现 LangChain → dict 角色映射 + content 规范化。
**修法:** 抽 `turn_helpers.langchain_message_to_dict()` + `langchain_message_content()`,
两处复用。回归 18 测试通过。

### CR-2 — Spec: T7 签名不符
**根因:** 我之前在 T8 实施时把 `resume_from_checkpoint` 改成产 dict,违反 spec L445 字节契约。
**修法:** 改回 `AsyncIterator[bytes]`,`agent_chat.py` 端点改透传 SSE 字节流(原代码错误地按 dict pop + 包装 SSE 协议)。
**回归:** test_graph_resume.py 3 用例改 SSE 字节解码断言,全过。

### CR-3 — Spec: T10 清理不彻底
**根因:** T10 删 react_loop 后,`evals/runner.py:186` + `evals/diff_debug.py:22` 仍
import 已删的 `_run_react_loop_turn`,`tests/test_replay_api.py` 4 处 patch
`react_loop.run_agent_turn_from_checkpoint` 已失效。
**修法:**
- `evals/runner.py` compare_evals 改为 LangGraph 单路径自检(react_loop 已删,无法双跑)
- `evals/diff_debug.py` 整删(只为 T9 parity debug,已无意义)
- `tests/test_replay_api.py` 4 处 patch 改为 `langgraph_nodes.resume.resume_from_checkpoint`,
  mock 改产 SSE 字节流

### CR-4 — Spec: T8 配置/文档未同步
**根因:** `.env.example` 仍 `LANGGRAPH_ENABLED=false` + 注释"沿用 react_loop";`
scripts/gradual_rollout_langgraph.sh` rollback 注释"react_loop.py 重新接管"误导。
**修法:**
- `.env.example` LANGGRAPH_ENABLED 注释为"已删除,不要设",指向唯一灰度维度
  `AGENT_ORCHESTRATOR_ENABLED`
- `gradual_rollout_langgraph.sh` 改为 no-op + 说明 LangGraph 是唯一路径

### CR-5 — Spec: 文档漂移
**根因:** `sse_bridge.py` docstring 写"7 类事件",实际 T6 加 `input_required` +
`progress_confirm` 后变 8 类。`replay()` 注释仍说"双跑使用",但 react_loop 删后无生产用途。
**修法:**
- docstring 8 类事件清单
- `replay()` 加 deprecation 说明(T10 后仅供评测/调试)

---

## 历史已知问题(已 commit 在 main,CR-6 留档)

### CR-6 (Part 1) — T9 parity gate 未达 spec 硬门槛仍执行 T10

**plan spec 硬门槛**(`docs/superpowers/plans/2026-07-17-agent-path-unify-langgraph.md`):
- L15: "纯重构,行为等价:对外 8 类 SSE 事件、HITL 交互、降级语义完全不变"
- L527: "未达标 → 回到对应 Task 修正"

**实际 T9 parity 留档**(`backend/reports/eval/agent-parity-2026-07-17.md`):
```
overall_match: 0.667          (目标 ≥ 0.95)        ❌
tool_call_match: 1.0          (目标 == 1.0)        ✅
handoff_match: 1.0            (目标 == 1.0)        ✅
sse_event_count_equal: false  (目标 == true)       ❌
```

**用户决策:** "继续做直到解决问题,我不想要react_loop了"。即用户明确接受 parity
不达标仍执行 T10,放弃 plan 硬门槛。

**根因(已分析,见 `agent-parity-2026-07-17.md`):**
1. `overall_match 0.667`:tools.py / handoff 路径仍走 `simple_chat` 真实 LLM
   调用,mock LLMClient 未完全覆盖所有调用点
2. `sse_event_count_equal false`:react_loop 经多次 `_open_agent_repo` /
   `repo.list_messages` + `repo.create_message` 写库;LangGraph 经图节点
   output 状态合并,事件触发时机略有不同

**未修复(用户接受):**
- overall_match < 0.95
- sse_event_count_equal false

**回归影响:** T9 parity 不达标意味着两路径 SSE 字节级不完全等价。若生产环境
需要严格回滚到 react_loop 行为(已在 T10 删除),需先恢复 react_loop.py +
重新跑 T9 达标。

### CR-6 (Part 2) — Scope creep(并行 agent 工作)

**plan 范围:** ②a Agent 路径统一到 LangGraph(T1-T10)

**实际 diff 包含范围外改动:**
- `config.py:94-170` OCR / VLM 配置(并行 multimodal 工作)
- `evals/retrieval/ragas_scorer.py` 改动(retrieval 工作)
- `backend/app/domain/agent/orchestrator/` 子模块新增(并行 ②b 工作)
- squash `9edaae7 feat(multimodal): parse_pdf ...` 实际包含 T5 turn_helpers /
  react_loop / sse_bridge 改动(commit msg 与内容不符)

**处置:**
- squash commit 内容混杂无法单独回滚
- ②b / multimodal 改动与 ②a 相互独立,不影响 ②a 行为
- 此文档仅留档,无需修复

---

## 总结

| CR | 类型 | 状态 |
|----|------|------|
| CR-1 | Standards Duplicated Code | ✅ 已修 |
| CR-2 | Spec T7 签名 | ✅ 已修 |
| CR-3 | Spec T10 清理不彻底 | ✅ 已修 |
| CR-4 | Spec T8 配置/脚本 | ✅ 已修 |
| CR-5 | Spec 文档漂移 | ✅ 已修 |
| CR-6 | Spec T9 parity + scope creep | 📝 留档(用户决策接受) |

**5/6 修复,1 留档。**