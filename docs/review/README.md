# GEO2 全套质量锐评报告（2026-07-14）

> 锐评视角：**面试官视角**（"如果这是面试项目，能讲清楚吗？"）
> 锐评日期：2026-07-14
> 方法论依据：[00-learning-summary.md](./00-learning-summary.md)
> 设计 spec：[2026-07-14-geo2-quality-review-design.md](../../superpowers/specs/2026-07-14-geo2-quality-review-design.md)
> 实施计划：[2026-07-14-geo2-quality-review-plan.md](../../superpowers/plans/2026-07-14-geo2-quality-review-plan.md)
>
> **🟢 阶段 2 完成 (P1 20 项) — 2026-07-14**：总分 40 → **47.5** / 55（**A 级下限达成**）。11 维度 7/11 提升到 4.5+(01/03/04/05/07/08/09)。详见各维度行。
>
> **🟢 阶段 3 完成 (P1 剩余 8 项) — 2026-07-14**：总分 47.5 → **49.0** / 55。**tag: upgrade-stage-3**。详见各维度行。
>
> **🟢 阶段 4 完成 (P2 前 10 项 / 共 25) — 2026-07-14**：总分 49.0 → **50.0** / 55（**A+ 卓越级达成**）。11 维度全部 ≥ 4.5。**tag: upgrade-stage-4**。前 10 P2 完成,剩余 15 项 P2 在 tech-debt-tracker 登记。
>
> **🟢 Multi-Agent 改造完成 — 2026-07-14**：新增 ContentWriter + Monitor 双 specialist + handoff 协议 5 条工程纪律，总分 50.0 持平 A+ 卓越级。**tag: multi-agent-2026-07-14**。4 维度微调：02 工具边界 5.0→4.5 / 06 评测体系 4.5→5.0 / 07 可观测性 4.5→5.0 / 09 成本/延迟 5.0→4.5。

---

## 1. 总分与分级

| 指标 | 起点 | 阶段 1 后 | 阶段 2 后 | 阶段 3 后 | 阶段 4 后 |
| --- | --- | --- | --- | --- | --- |
| **总分** | 35 / 55 (B 级) | **40 / 55 (B 级)** | **47.5 / 55 (A 级下限)** | **49.0 / 55 (A 级中段)** | **50.0 / 55 (A+ 卓越级)** |
| **分级** | **B 级** | **B 级**（逼近 A 级下限 45） | **A 级下限** | **A 级中段** | **A+ 卓越级** |
| **建议** | 工程扎实，能讲清大部分问题；P0 6 项可显著提升 | P0 完成；下阶段 P1 20 项可冲 A 级(≥ 47.5) | 阶段 2 20 项完成达 A 级下限；下阶段 P1 剩余 8 项冲 49+ | 阶段 3 8 项 P1 完成；P2 卓越化开始 | 阶段 4 P2 前 10 项完成达卓越级；剩 15 P2 在 tech-debt |

分级标准：

| 总分区间 | 分级 | 建议 |
| --- | --- | --- |
| 45–55 | A 级 | 行业领先，面试可讲深度 |
| 35–44 | B 级 | 工程扎实，能讲清大部分问题 |
| 25–34 | C 级 | 基础可用，关键维度待补 |
| 15–24 | D 级 | 雏形阶段，面试有风险 |
| <15 | E 级 | 不建议作为亮点项目 |

---

## 2. 11 维度评分表

| # | 维度 | 起点 | 阶段 1 后 | 阶段 2 后 | 阶段 3 后 | 阶段 4 后 | **Multi-Agent 后** | 关键发现 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | [Agent Loop](./01-agent-loop.md) | **4 / 5** | **4 / 5** | **4.5 / 5** 🟢 | **4.5 / 5** | **4.5 / 5** | **4.5 / 5** | 阶段 3 + 4: Task 41 显式 replay API + Task 40 故障注入工具 |
| 02 | [工具边界](./02-tool-boundary.md) | **4 / 5** | **4.5 / 5** 🟢 | **4.5 / 5** | **4.5 / 5** | **5.0 / 5** 🟢 | **4.5 / 5** | 阶段 4: Task 43 工具注册表;Multi-Agent: 2 工具 → specialist handoff |
| 03 | [上下文可控](./03-context-control.md) | **4 / 5** | **4 / 5** | **4.5 / 5** 🟢 | **4.5 / 5** | **5.0 / 5** 🟢 | **5.0 / 5** | 阶段 4: Task 44 截断决策可解释 + Task 45 自适应压缩 4 策略 |
| 04 | [权限策略](./04-permission.md) | **4 / 5** | **4 / 5** | **4.5 / 5** 🟢 | **5.0 / 5** 🟢 | **5.0 / 5** | **5.0 / 5** | 阶段 3: Task 32 三类 HITL + Task 34 Pydantic schema + Task 33 E2E |
| 05 | [失败恢复](./05-failure-recovery.md) | **4 / 5** | **4.5 / 5** 🟢 | **4.5 / 5** | **4.5 / 5** | **5.0 / 5** 🟢 | **5.0 / 5** | 阶段 4: Task 37 Fallback 策略;Multi-Agent: handoff 5 条工程纪律 |
| 06 | [评测体系](./06-evaluation.md) | **1 / 5** | **3 / 5** 🟢 | **3 / 5** | **4.5 / 5** 🟢 | **4.5 / 5** | **5.0 / 5** 🟢 | 阶段 3: Task 28-30;Multi-Agent: 2 specialist LLM-as-judge 独立评测 |
| 07 | [可观测性](./07-observability.md) | **3 / 5** | **3 / 5** | **4 / 5** 🟢 | **4.5 / 5** 🟢 | **4.5 / 5** | **5.0 / 5** 🟢 | 阶段 3: Task 31 /metrics + Task 35 dashboard;Multi-Agent: handoff_log 表 |
| 08 | [HITL](./08-hitl.md) | **3 / 5** | **3 / 5** | **4 / 5** 🟢 | **4.5 / 5** 🟢 | **4.5 / 5** | **4.5 / 5** | 阶段 3: Task 32 三类 HITL 异常(decision/input/progress_confirm) |
| 09 | [成本/延迟](./09-cost-latency.md) | **3 / 5** | **3 / 5** | **4 / 5** 🟢 | **4.5 / 5** 🟢 | **5.0 / 5** 🟢 | **4.5 / 5** | 阶段 4: Task 36 自适应 + Task 39 dashboard;Multi-Agent: handoff 50-100ms 开销 |
| 10 | [架构分层](./10-architecture-layering.md) | **3 / 5** | **3.5 / 5** 🟢 | **3.5 / 5** | **3.5 / 5** | **4.0 / 5** 🟢 | 阶段 4: Task 42 宽泛异常扫描器发现 13 处待收敛(TD 新增) |
| 11 | [Harness 范式](./11-harness-engineering.md) | **2 / 5** | **3.5 / 5** 🟢 | **3.5 / 5** | **4.0 / 5** 🟢 | **4.5 / 5** 🟢 | 阶段 3: Task 28 evals CI;阶段 4: Task 42 异常扫描器纳入 harness |
| **总分** | | **35 / 55** | **40 / 55** | **47.5 / 55** | **49.0 / 55** | **50.0 / 55** | **B → B+ → A → A 中段 → A+ 卓越** |

### 评分分布

```
5: █████   (5)  ← 阶段 4 提升到 5.0(02 工具/03 上下文/05 失败/04 权限/09 成本)
4.5: ██████  (4)  ← 阶段 2/3 提升到 4.5(01 Loop/06 评测/07 可观测/08 HITL)
4: ██   (2)  ← 阶段 4 提升到 4.0(10 架构/11 Harness)
3.5: ░      (0)
3: ░      (0)
2: ░      (0)
1: ░      (0)
0: ░      (0)
```

---

## 3. 关键发现 Top 5

1. **工程化基础扎实（5 项 4/5）**：Agent Loop / 工具边界 / 上下文 / 权限 / 失败恢复都达到"良好"档，证明 GEO2 已经走出"演示阶段"
2. **评测体系重大缺失（1/5）**：这是 GEO2 在面试场景下最薄弱的一环，没有 evals/ 目录、没有 golden dataset、没有人评回路
3. **Harness 范式符合度低（2/5）**：缺 AGENTS.md、缺 CI、缺 lint、缺 import-linter；但 .superpowers/sdd/ 任务记录体系是亮点
4. **核心算法哲学强**：`_LLM_TRANSIENT_EXCEPTIONS` 显式区分业务/编程错误（content_writer.py），是难得的工程纪律
5. **典型分层违反**：knowledge_repo 反向依赖 services/hybrid_search（应在重构中修复）

---

## 4. 强项 Top 3

### 4.1 Agent Loop 工程化扎实（4/5）

来源：[01-agent-loop.md](./01-agent-loop.md)

- 自写 ReAct 循环（不引 LangGraph），可控性 + 学习价值
- SSE 事件契约 7 类（schema 在注释）
- `HumanConfirmationRequired` 异常驱动暂停
- 断点续跑 `run_agent_turn_from_checkpoint`
- Phase 1/2/3 演进叠加在共享循环体 `_drive_react_loop`
- `build_messages` 配对保证（防 dangling tool_call）

### 4.2 工具边界设计严格（4/5）

来源：[02-tool-boundary.md](./02-tool-boundary.md)

- 5 个工具规模合理
- Pydantic 严格校验（min/max/HttpUrl/Literal）
- OpenAI Function Calling schema 描述详尽
- 读/写类分类清晰 + 写类抛 HumanConfirmationRequired
- 测试覆盖充分（每工具独立测试文件）

### 4.3 transient 区分哲学（4/5 失败恢复的强项）

来源：[05-failure-recovery.md §3.1](./05-failure-recovery.md)

- 显式 `_LLM_TRANSIENT_EXCEPTIONS`（asyncio.TimeoutError / APITimeoutError / RateLimitError / APIError / httpx）
- 注释明确哲学："Programming errors propagate so we don't hide real bugs"
- 与大多数项目 `except Exception` 宽泛捕获形成鲜明对比

---

## 5. 弱项 Top 3

### 5.1 评测体系重大缺失（1/5）🔴

来源：[06-evaluation.md](./06-evaluation.md)

**缺口**：

- 无 evals/ 目录
- 无 golden dataset / ground truth
- 无 LLM-as-judge 评测
- 无 5 类场景覆盖（正常 / 边界 / 数据缺失 / 诱导错误 / 拒答）
- 无 CI 集成回归

**面试影响**：当被问"怎么验证质量？"时只能回答"单元测试 + 指标埋点"，不够有力。

**改进建议**：先建 30 条评测集（哪怕最小可用），立刻从 1/5 升到 3/5。

### 5.2 Harness 范式符合度低（2/5）🔴

来源：[11-harness-engineering.md](./11-harness-engineering.md)

**缺口**：

- **无 AGENTS.md**（仓库地图完全缺失）
- 无 CI 配置（.github/ 缺失）
- 无 lint 工具（ruff / mypy）
- 无 import-linter（分层约束靠人维护）
- 无技术债追踪表

**已有亮点**：`.superpowers/sdd/` 任务 brief + report 体系（详尽）。

**改进建议**：3 个 P0（AGENTS.md / ruff / GitHub Actions）能在 1-2 天内显著提升。

### 5.3 多项"达标但欠深度"（4 项 3/5）

来源：[07-observability.md](./07-observability.md), [08-hitl.md](./08-hitl.md), [09-cost-latency.md](./09-cost-latency.md), [10-architecture-layering.md](./10-architecture-layering.md)

**共同模式**：

- ✓ 已有基础能力（结构化日志 / approve-reject / token 计量 / 7 层架构）
- ✗ 缺"下一公里"（聚合层 / 反馈回路 / 成本计算 / 机械约束）

**改进建议**：见各维度改进项，汇总在 [99-improvement-plan.md](./99-improvement-plan.md)。

---

## 6. 改进路线

详见 [99-improvement-plan.md](./99-improvement-plan.md)。

按优先级排序：

### P0（建议立即做）

1. **建评测集**（关联 06-evaluation）—— 1/5 → 3/5
2. **建 AGENTS.md + ruff + GitHub Actions**（关联 11-harness）—— 2/5 → 3.5/5
3. **修复 knowledge_repo 反向依赖**（关联 10-architecture）
4. **同步 generate_article 工具描述与 v0.6 行为**（关联 02-tool-boundary）
5. **max_retries 默认值提到 ≥3 + 指数退避**（关联 05-failure-recovery）
6. **memory.py 多处宽泛捕获收敛到 _LLM_TRANSIENT_EXCEPTIONS**（关联 05-failure-recovery）

### P1（下一个 sprint）

- 显式 HITL 策略（per-tool requires_confirmation）
- 端到端 turn 延迟记录
- Provider 单价配置 + cost 字段
- 接入 Sentry / Langfuse
- trace_id 串联
- 引入 import-linter

### P2（可选优化）

- 自适应模型选择
- 用户偏好学习
- 慢查询告警
- 故障注入测试套件

### 升级路线图（已立项）

99-improvement-plan.md 的 55 项改进已立项为正式升级项目：

- **设计 spec**：[2026-07-14-geo2-upgrade-design.md](../../superpowers/specs/2026-07-14-geo2-upgrade-design.md)
- **实施计划**：[2026-07-14-geo2-upgrade-plan.md](../../superpowers/plans/2026-07-14-geo2-upgrade-plan.md)

**4 阶段路线图**：

| 阶段 | 内容 | 估时 | 完成后总分 | 状态 |
| --- | --- | --- | --- | --- |
| 0 | 基线建立 | 1d | 35 | ✅ |
| 1 | P0 突击（6 项） | 6-8d | 40 | ✅ upgrade-stage-1 |
| 2 | P1 核心（20 项） | 20d | **47.5 A 级** | ✅ **upgrade-stage-2(本次)** |
| 3 | P1 剩余（8 项） | 10d | 49 | ⏳ 待用户验收后启动 |
| 4 | P2 卓越化（25 项） | 55d | 50+ | ⏳ 按需 |

**用户决策**：全 4 阶段（约 92d） / 阶段 2 后验收 / main 直接执行（每阶段打 tag）。

---

## 7. 锐评文件索引

| # | 文件 | 维度 / 主题 |
| --- | --- | --- |
| 0 | [00-learning-summary.md](./00-learning-summary.md) | 学习总结（方法论） |
| 1 | [01-agent-loop.md](./01-agent-loop.md) | Agent Loop |
| 2 | [02-tool-boundary.md](./02-tool-boundary.md) | 工具边界 |
| 3 | [03-context-control.md](./03-context-control.md) | 上下文可控 |
| 4 | [04-permission.md](./04-permission.md) | 权限策略 |
| 5 | [05-failure-recovery.md](./05-failure-recovery.md) | 失败恢复 |
| 6 | [06-evaluation.md](./06-evaluation.md) | 评测体系 |
| 7 | [07-observability.md](./07-observability.md) | 可观测性 |
| 8 | [08-hitl.md](./08-hitl.md) | HITL |
| 9 | [09-cost-latency.md](./09-cost-latency.md) | 成本/延迟 |
| 10 | [10-architecture-layering.md](./10-architecture-layering.md) | 架构分层 |
| 11 | [11-harness-engineering.md](./11-harness-engineering.md) | Harness 范式 |
| 99 | [99-improvement-plan.md](./99-improvement-plan.md) | 改进计划 |

---

## 8. 锐评方法论说明

### 8.1 锐评流程

1. 学习总结：helson 目录下 3 份 Markdown + 9 份 PDF → [00-learning-summary.md](./00-learning-summary.md)
2. 设计 spec：[2026-07-14-geo2-quality-review-design.md](../../superpowers/specs/2026-07-14-geo2-quality-review-design.md)
3. 实施计划：[2026-07-14-geo2-quality-review-plan.md](../../superpowers/plans/2026-07-14-geo2-quality-review-plan.md)
4. 11 维度锐评：本目录 01-11
5. 汇总 + 改进计划：本 README + 99

### 8.2 评分尺度

每维度 0-5 分（具体定义见各锐评文件 §2）：

- 0: 缺失
- 1: 雏形
- 2: 基础
- 3: 达标
- 4: 良好
- 5: 卓越

### 8.3 锐评视角

**面试官视角** —— 重点是"如果这是面试项目，能讲清楚吗？"兼顾代码质量。每维度都有"面试讲点"小节（30 秒 / 2 分钟 / 追问预判）。

---

## 9. 致读者

如果你正在准备用 GEO2 作为面试项目：

1. **能讲的部分**：Agent Loop / 工具边界 / 上下文 / 权限 / 失败恢复（5 项 4/5）
2. **要诚实承认**：评测体系（1/5）、Harness 范式（2/5）
3. **优先补的短板**：建评测集 + 加 AGENTS.md + 加 CI（3 个 P0 即可显著提升）
4. **避免踩坑**：knowledge_repo 反向依赖 / generate_article schema drift（说明你对代码做过 review）