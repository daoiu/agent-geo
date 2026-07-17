# 设计:②b Agent 编排层(复杂度 router + Plan-Execute + Reflection)

> 日期:2026-07-17
> 范围:本 spec 只覆盖「② 编排与反思」的编排部分。**依赖 ②a(Agent 路径统一到 LangGraph)完成**。
> 性质:在 ②a 统一后的单一 LangGraph 路径上新增编排能力,新 flag 灰度,默认不影响既有路径。

## 背景与目标

②a 完成后,LangGraph 成为唯一 agent 执行路径(纯 ReAct)。②b 在其上叠加:

- **入口模式路由**:按查询复杂度选 ReAct 或 Plan-Execute。
- **Plan-Execute 模式**:先规划有序步骤,再逐步执行。
- **运行时升降级**:ReAct 卡住 → 升 Plan-Execute;Plan 失败 → 降 ReAct。
- **ReflectionAgent 质量评分**:LLM-as-Judge 多维打分,低分自动重试。

对应简历「ReAct/Plan-Execute 双模式动态切换与失败降级;ReflectionAgent 质量评分机制(<60 分自动重试)」。

## 决策记录(来自澄清)

- **模式切换**:入口 `classify_complexity` 选初始模式(simple/standard → ReAct,complex → Plan-Execute)+ 运行时升降级。
- **Reflection**:LLM-as-Judge 多维打分(完整性 / 忠实性 / 工具合理性)0-100,**<60 自动重试,最多 2 次,返回最高分那次**。三维权重 **0.4 / 0.4 / 0.2**。
- **接入**:新建独立 orchestrator 图包裹 ②a 统一图,新 flag `agent_orchestrator_enabled`(默认 False)灰度。
- **防震荡**:升级后不再降回(单向升级)。
- **附加事件**:编排新增 `reflection_score` / `mode_switch` 作为**附加** SSE 事件,不破坏既有 8 类。

## 复用点

- `app.core.adaptive_model.classify_complexity(query, tool_count, hint) -> "simple"|"standard"|"complex"`(现成,作 router 判据)。
- `app.domain.agent.tools.TOOLS` / `ToolExecutor`(Plan-Execute executor 复用)。
- `backend/evals/judge.py`(LLM-as-Judge 风格,Reflection 打分参考)。
- ②a 统一图(`react_graph.build_react_graph`)作为 ReAct 子图。

## 拓扑

```
START → router(classify_complexity)
          ├─ simple/standard → react_subgraph(②a 统一图)
          └─ complex        → plan_execute_subgraph
                                   planner → executor(step loop)→ replan? → done
          ↓(两模式产出 answer 汇合)
        reflection(LLM-judge 0-100)
          ├─ score ≥ 60 或重试用尽 → 返回最高分那次 → END
          └─ score < 60 且有余额  → 带 critique 反馈重试(回对应模式)

运行时升降级:
  react 触发 max_iterations / 连续 tool 失败 → 升级 plan_execute
  planner 解析失败 / 无有效步骤        → 降级 react(单向,升级后不降回)
```

## 模块

| 模块 | 职责 |
|---|---|
| `app/domain/agent/orchestrator/router.py` | 入口分类选模式(复用 `classify_complexity`);升降级判定函数 |
| `app/domain/agent/orchestrator/plan_execute.py` | `planner`(LLM 产有序步骤 JSON)+ `executor`(逐步执行,复用 `ToolExecutor`/tools)+ 单次 replan |
| `app/domain/agent/orchestrator/reflection.py` | `ReflectionAgent`:LLM-as-Judge 多维打分 0-100 + 重试决策 |
| `app/domain/agent/orchestrator/graph.py` | 组装 orchestrator StateGraph,包裹 ②a 统一图 |
| `app/domain/agent/dispatch.py` | 按 `agent_orchestrator_enabled` 决定走 orchestrator 还是 ②a 单图 |

## 关键实现

- **router**:`classify_complexity(query, tool_count=len(TOOLS), hint)` → 映射 ReAct/Plan;`hint` 可由 API 透传强制。
- **Plan-Execute**:planner 产 `[{"step": str, "tool_hint": str|None}]`;executor 每步跑一段受限 ReAct(或直接工具调用),结果累积进 state;某步失败 → replan 一次,再失败 → 降级 ReAct;`plan_execute_max_steps` 上限防跑飞。
- **Reflection**:对最终 answer 打分,维度加权(完整性 0.4 / 忠实性 0.4 / 工具合理性 0.2)→ 0-100。<60 把 critique 注入上下文重试,记录每次 `(score, answer)`,**返回 score 最高的那次**;`reflection_max_retries=2`。
- **升降级状态**:state 记 `mode` / `escalated` / `attempts`,升级后不再降回(防震荡)。

## 错误处理(沿用降级风格)

- reflection LLM 失败 → 跳过评分,原样返回 answer(记日志),不阻塞。
- planner 失败 → 降级 ReAct。
- 全程无 key → router 退 ReAct、reflection 关闭。
- 复用 ②a 的 SSE 事件契约;新增 `reflection_score` / `mode_switch` 为附加事件,前端可忽略,不破坏既有 8 类。
- 编程错误向上抛不吞;transient 降级。

## 配置(settings 新增)

- `agent_orchestrator_enabled: bool = False`
- `reflection_enabled: bool = True`
- `reflection_min_score: int = 60`
- `reflection_max_retries: int = 2`
- `plan_execute_max_steps: int = 6`

## 测试

- router 分类 → 模式映射(simple/standard/complex + hint 强制)。
- planner JSON 解析 + 非法降级。
- executor step loop(mock tools,步骤累积 + 单次 replan + 降级)。
- reflection 打分 + 重试(mock judge 先返回 <60 再 ≥60,验证返回最高分那次;LLM 失败跳过)。
- 升级 / 降级路径(单向升级不回退)。
- orchestrator 图集成(mock 子图,验证 router→mode→reflection→END)。

## 交付物

1. `app/domain/agent/orchestrator/` 全套模块 + 单测。
2. `dispatch.py` 接入 flag。
3. settings 新增配置 + `.env.example`。
4. flag 开启后可选:接 ④ 评测观察 Reflection 对质量分的影响。

## 非目标

- 不改 ②a 图内部实现。
- 不动 multi-agent handoff(已存在的 `ContentWriterSpecialist`/`MonitorSpecialist`)。
- Plan-Execute 不做并行步骤(线性 + 单次 replan 足够)。
- ③ OCR/VLM、① 检索(各自 spec)。
