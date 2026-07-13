# GEO2 全套质量锐评 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 Agent 开发学习路线，对 GEO2 项目做 11 维度全套质量锐评（面试官视角），产出 14 个 Markdown 文件（学习总结 + 11 维度锐评 + 主页 + 改进计划），全部沉淀在 `D:\GEO2\docs\review\`。

**Architecture:** 顺序推进 —— 先产出方法论（学习总结）锁定打分标准，再按 11 维度逐一调研 GEO2 现状并锐评，最后汇总主页和改进计划。每完成一个文件 commit 一次。

**Tech Stack:** Markdown 文档、git commit、文件读写工具。不涉及代码改动。

---

## Global Constraints

- **语言**：所有产出用简体中文（按 `C:\Users\p'q'y\.claude\CLAUDE.md` 项目语言规范）
- **锐评视角**：面试官视角（"如果这是面试项目，能讲清楚吗？"）
- **位置**：所有产出在 `D:\GEO2\docs\review\` 下
- **命名规则**：`NN-<name>.md`，两位前缀保证排序稳定
- **Commit 粒度**：每完成一个 Markdown 文件 commit 一次
- **代码引用**：所有锐评中的代码引用必须包含真实可查的文件路径
- **方法论引用**：所有锐评必须引用 `00-learning-summary.md` 的对应章节
- **不实施改进**：本计划不实施 `99-improvement-plan.md` 中的任何建议，只产出该文件
- **Spec 路径**：`D:\GEO2\docs\superpowers\specs\2026-07-14-geo2-quality-review-design.md`

---

## File Structure

| 序号 | 文件路径 | 职责 |
| --- | --- | --- |
| 1 | `D:\GEO2\docs\review\00-learning-summary.md` | 学习总结：方法论 + 11 维度达标线 + 评测模板 |
| 2 | `D:\GEO2\docs\review\01-agent-loop.md` | 锐评维度 1：Agent Loop 清晰度 |
| 3 | `D:\GEO2\docs\review\02-tool-boundary.md` | 锐评维度 2：工具边界与契约 |
| 4 | `D:\GEO2\docs\review\03-context-control.md` | 锐评维度 3：上下文可控性 |
| 5 | `D:\GEO2\docs\review\04-permission.md` | 锐评维度 4：权限策略与边界 |
| 6 | `D:\GEO2\docs\review\05-failure-recovery.md` | 锐评维度 5：失败恢复与降级 |
| 7 | `D:\GEO2\docs\review\06-evaluation.md` | 锐评维度 6：评测体系 |
| 8 | `D:\GEO2\docs\review\07-observability.md` | 锐评维度 7：可观测性 / 日志 / 追踪 |
| 9 | `D:\GEO2\docs\review\08-hitl.md` | 锐评维度 8：人机协同（HITL） |
| 10 | `D:\GEO2\docs\review\09-cost-latency.md` | 锐评维度 9：Token 成本与延迟 |
| 11 | `D:\GEO2\docs\review\10-architecture-layering.md` | 锐评维度 10：架构分层 |
| 12 | `D:\GEO2\docs\review\11-harness-engineering.md` | 锐评维度 11：Harness 范式符合度 |
| 13 | `D:\GEO2\docs\review\README.md` | 主页：总分 / 11 维度表 / 关键发现 |
| 14 | `D:\GEO2\docs\review\99-improvement-plan.md` | 改进计划：按优先级 + 估时 |

每个锐评文件（02-12）使用统一模板：

```markdown
# NN. <维度名>

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义
## 2. 评分标准（0-5 分制）
## 3. GEO2 现状调研
## 4. 评分与理由
## 5. 面试讲点（如何向面试官讲述）
## 6. 改进建议
```

---

## Task 0: 创建锐评目录骨架

**Files:**
- Create: `D:\GEO2\docs\review\.gitkeep`

**Interfaces:**
- Produces: 空目录 `D:\GEO2\docs\review\`

- [ ] **Step 1: 创建目录**

在 PowerShell 或 Git Bash 中执行：

```bash
mkdir -p "D:/GEO2/docs/review"
```

- [ ] **Step 2: 写入占位文件**

```bash
echo "# GEO2 质量锐评" > "D:/GEO2/docs/review/.gitkeep"
```

- [ ] **Step 3: 验证目录存在**

```bash
ls -la "D:/GEO2/docs/review/"
```

Expected: 目录存在，包含 `.gitkeep` 文件。

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2"
git add "docs/review/.gitkeep"
git commit -m "chore: 创建 docs/review 目录骨架"
```

---

## Task 1: 产出 00-learning-summary.md（学习总结）

**Files:**
- Create: `D:\GEO2\docs\review\00-learning-summary.md`

**Inputs:**
- 源材料：`D:\Agent\学习文档\helson\Agent开发学习指南.md`
- 源材料：`D:\Agent\学习文档\helson\Harness工程核心知识.md`
- 源材料：`D:\Agent\学习文档\helson\agent-development-roadmap-human(2).md`
- 源材料：`D:\Agent\学习文档\helson\*.pdf`（5 篇方法论 + 4 篇配套 PDF，按文件名提示按需精读）

**Produces:**
- 11 维度锐评将引用本文档的"6. 11 维度判断标准"小节
- 每个锐评文件的"1. 维度定义"小节从此处提炼

- [ ] **Step 1: 读取全部源材料**

使用 Read 工具依次读取：
- `D:\Agent\学习文档\helson\Agent开发学习指南.md`
- `D:\Agent\学习文档\helson\Harness工程核心知识.md`
- `D:\Agent\学习文档\helson\agent-development-roadmap-human(2).md`

预期：3 份文件全部成功读取。

- [ ] **Step 2: 按需精读 PDF（按文件名匹配锐评维度）**

对以下 PDF 用 WebFetch / PDF 提取工具按需精读，每份只读与锐评相关的章节：

| PDF 文件名 | 主要相关锐评维度 |
| --- | --- |
| `01-不要一上来学框架，先看懂AgentLoop.pdf` | 01 Agent Loop |
| `02-读完整项目不要从第一行开始，先找五层边界.pdf` | 10 架构分层 |
| `03-Agent库为什么不是一个文件-谈分层设计.pdf` | 10 架构分层 |
| `04-技术栈那么多，你只需要知道每层解决什么问题.pdf` | 10 架构分层 |
| `05-最后别做万能助手，用一个垂直项目验证能力.pdf` | 11 Harness 范式 |
| `什么样的 Agent 项目才算好项目.pdf` | 11 Harness 范式 |
| `Agent 测评怎么做？新人也能看懂的评估体系入门.pdf` | 06 评测体系 |
| `Agent 开发学习路线html版本.pdf` | 全局参考 |
| `怎么判断你的简历是否合格？ (1)(1).pdf` | 11 Harness 范式 |

注：PDF 精读成本高，按需补充，不必每份精读全文。

- [ ] **Step 3: 写入 00-learning-summary.md**

文件位置：`D:\GEO2\docs\review\00-learning-summary.md`

文件结构（严格按此骨架）：

```markdown
# Agent 学习指南：精炼版（面试向）

> 来源：`D:\Agent\学习文档\helson\` 目录下 3 份 Markdown + 9 份 PDF。
> 用途：作为 GEO2 11 维度锐评的方法论依据。

## 1. 核心公式

Agent = Model + Harness

(Harness 包含除模型本身的全部代码、配置、执行逻辑：系统提示、工具/技能/MCP、沙箱、编排、钩子/中间件)

## 2. 关键链路

用户输入 → 模型判断 → 工具调用 → 工具结果返回 → 模型继续推理 → 状态保存

## 3. 工程分层

API 服务 → 会话管理 → Agent 运行时 → 工具层 → 上下文工程 → 观测层 → 评测层

## 4. 严格分层架构

Types → Config → Repo → Service → Runtime → UI
(横切关注点通过显式接口 Providers 访问)

## 5. Harness Engineering 六大核心概念

1. **仓库即记录系统**：不在仓库里的东西对智能体不存在
2. **地图非手册**：AGENTS.md 是 ~100 行索引，不是百科全书
3. **机械化执行**：lint + CI 结构测试机械执行架构约束
4. **Agent 可读性**：优先为智能体推理能力优化代码文档
5. **吞吐量改变合并理念**：修正优于阻塞
6. **熵管理**：技术债持续小增量偿还

## 6. 11 维度的判断标准

(下面 11 个小节一一对应 `01-...md` 到 `11-...md`，作为各锐评文件 §1 维度定义的方法论依据)

### 6.1 Agent Loop（参考：01-agent-loop.md）

**定义**：用户输入到最终输出全链路的清晰度与可追溯性。
**达标线（3 分）**：链路完整、有状态保存、最大轮次限制、上下文裁剪。
**良好（4 分）**：错误注入可控、Loop 可视化、断点续跑。
**卓越（5 分）**：Loop 抽取可复现、可回放、每次运行有审计轨迹。

### 6.2 工具边界

**定义**：工具的参数/返回值/失败模式/调用权限边界是否清晰。
**达标线**：每个工具有 schema、错误返回值、不破坏 Agent Loop。
**良好**：工具可独立测试、文档完整、有降级策略。
**卓越**：工具描述对 LLM 友好、有评测覆盖。

### 6.3 上下文可控

**定义**：上下文窗口管理、压缩、检索的工程能力。
**达标线**：有最大 token 限制、有超限裁剪策略。
**良好**：滑动窗口 + 历史摘要 + 工具结果截断。
**卓越**：自适应压缩、可解释裁剪决策。

### 6.4 权限策略

**定义**：高风险操作的鉴权、确认流、审计。
**达标线**：危险工具有用户确认。
**良好**：权限分级、有审计日志。
**卓越**：策略可声明式配置、有自动化测试覆盖。

### 6.5 失败恢复

**定义**：工具失败、超时、网络错误的降级与重试。
**达标线**：有 try/except + 重试。
**良好**：有降级回答模板、有故障注入测试。
**卓越**：可重放、可恢复会话。

### 6.6 评测体系

**定义**：自动化评测 Agent 输出质量的能力。
**达标线**：≥30 条评测用例、覆盖 5 类场景。
**良好**：失败原因分类、可回归。
**卓越**：与 CI 集成、人评结合。

### 6.7 可观测性

**定义**：日志、追踪、成本统计的完整度。
**达标线**：全链路日志、有 token 成本统计。
**良好**：有 tracing、错误聚合、可视化面板。
**卓越**：可回放、可重跑。

### 6.8 HITL

**定义**：Human-in-the-loop 关键节点的确认流。
**达标线**：高风险操作有确认。
**良好**：确认流可中断可继续。
**卓越**：可配置策略、有用户反馈回路。

### 6.9 成本/延迟

**定义**：Token 成本与延迟的可见性与控制。
**达标线**：每次调用记录 token + 延迟。
**良好**：有成本/延迟告警阈值。
**卓越**：自适应模型选择、可解释成本结构。

### 6.10 架构分层

**定义**：Types → Config → Repo → Service → Runtime → UI 的严格分层。
**达标线**：层间依赖方向正确、跨层有显式接口。
**良好**：横切关注点（认证、遥测）通过 Provider 抽象。
**卓越**：lint + 结构测试机械执行分层约束。

### 6.11 Harness 范式符合度

**定义**：项目整体对 Harness Engineering 范式的符合度。
**达标线**：决策与规范版本化在仓库、有 AGENTS.md 索引。
**良好**：架构约束由 lint/CI 机械执行、有评测体系。
**卓越**：吞吐量为优先、有熵管理机制、分离构建/评判智能体。

## 7. 评测集设计模板

30–50 条覆盖：
- 正常问题（15）
- 边界问题（8）
- 数据缺失（8）
- 诱导错误（8）
- 拒答（5）

评测维度：准确性 / 完整性 / 相关性 / 可执行性 / 幻觉率

## 8. 简历表达样例

❌ "基于大模型实现智能问答系统"

✅ "设计 Agent Loop，支持工具调用、会话状态保存、上下文动态裁剪；接入 N 个工具，工具失败时有降级兜底；为高风险操作增加用户确认流程；构建 50 条评测集覆盖 5 类场景；接入 Langfuse 全链路追踪，Token 成本降低 30%"
```

- [ ] **Step 4: 自检模板完整性**

```bash
grep -c "^## " "D:/GEO2/docs/review/00-learning-summary.md"
```

Expected: 输出 ≥ 8（8 个一级章节标题）

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2"
git add "docs/review/00-learning-summary.md"
git commit -m "docs(review): 产出学习总结(00-learning-summary.md)"
```

---

## Task 2: 产出 01-agent-loop.md（锐评维度 1）

**Files:**
- Create: `D:\GEO2\docs\review\01-agent-loop.md`

**Inputs:**
- `D:\GEO2\docs\review\00-learning-summary.md` §6.1（维度定义）
- GEO2 backend/agent/*.py（重点 `_drive_react_loop` 等）
- GEO2 git log Phase 1 相关 commit
- `D:\Agent\学习文档\helson\01-不要一上来学框架，先看懂AgentLoop.pdf`（按需精读）

- [ ] **Step 1: 调研 GEO2 Agent Loop 实现**

```bash
ls "D:/GEO2/backend/agent/" 2>&1 | head -30
git -C "D:/GEO2" log --oneline --all -- "backend/agent/" 2>&1 | head -20
```

预期：识别 Loop 入口、状态保存位置、最大轮次控制、上下文裁剪逻辑。

- [ ] **Step 2: 读取关键 Loop 文件**

使用 Read 工具读取 `_drive_react_loop` 所在的文件全文，记录：
- Loop 入口函数签名
- 状态保存/恢复机制
- 错误处理路径
- 最大轮次限制实现
- 上下文裁剪触发条件

- [ ] **Step 3: 写入 01-agent-loop.md §1–§2（维度定义 + 评分标准）**

按统一模板的 §1 §2 小节填充，引用 `00-learning-summary.md` §6.1。

- [ ] **Step 4: 写入 §3（现状调研）**

引用具体代码（带文件路径 + 行号），描述 GEO2 现状。

- [ ] **Step 5: 写入 §4（评分与理由）**

基于现状给 0–5 分，给出 3 条证据 + 与行业标准差距。

- [ ] **Step 6: 写入 §5–§6（面试讲点 + 改进建议）**

面试讲点：30 秒版本 + 2 分钟版本 + 3 个追问预判。
改进建议：列出 3–5 条具体改进项，关联到 `99-improvement-plan.md` 编号（占位 P0/P1/P2）。

- [ ] **Step 7: 自检文件完整性**

```bash
grep -c "^## " "D:/GEO2/docs/review/01-agent-loop.md"
```

Expected: 输出 ≥ 6（6 个一级章节：维度定义 / 评分标准 / 现状 / 评分 / 面试讲点 / 改进建议）

- [ ] **Step 8: Commit**

```bash
cd "D:/GEO2"
git add "docs/review/01-agent-loop.md"
git commit -m "docs(review): 锐评 01 Agent Loop"
```

---

## Task 3: 产出 02-tool-boundary.md（锐评维度 2）

**Files:**
- Create: `D:\GEO2\docs\review\02-tool-boundary.md`

**Inputs:**
- `D:\GEO2\docs\review\00-learning-summary.md` §6.2
- GEO2 backend/tools/*.py
- 工具 schema 定义文件（若有）

- [ ] **Step 1: 列出 GEO2 全部工具**

```bash
ls "D:/GEO2/backend/tools/" 2>&1
find "D:/GEO2/backend" -name "*tool*.py" -type f 2>&1 | head -30
```

预期：识别工具数量、每个工具的入口。

- [ ] **Step 2: 抽样读取 3 个工具文件**

挑选一个高频工具、一个数据查询工具、一个写操作工具，记录：
- 参数 schema 是否定义
- 返回值结构
- 错误处理路径
- 是否有单元测试

- [ ] **Step 3: 写入 §1–§2（维度定义 + 评分标准）**

引用 `00-learning-summary.md` §6.2。

- [ ] **Step 4: 写入 §3（现状调研）**

按"工具总数 / schema 完整度 / 错误处理 / 测试覆盖"四维度描述。

- [ ] **Step 5: 写入 §4（评分与理由）**

给出 0–5 分 + 关键证据。

- [ ] **Step 6: 写入 §5–§6（面试讲点 + 改进建议）**

面试讲点要回答："你的 Agent 有几个工具？怎么管理边界？"
改进建议：3–5 条改进项。

- [ ] **Step 7: 自检文件完整性**

```bash
grep -c "^## " "D:/GEO2/docs/review/02-tool-boundary.md"
```

Expected: ≥ 6

- [ ] **Step 8: Commit**

```bash
cd "D:/GEO2"
git add "docs/review/02-tool-boundary.md"
git commit -m "docs(review): 锐评 02 工具边界"
```

---

## Task 4: 产出 03-context-control.md（锐评维度 3）

**Files:**
- Create: `D:\GEO2\docs\review\03-context-control.md`

**Inputs:**
- `D:\GEO2\docs\review\00-learning-summary.md` §6.3
- GEO2 Phase 3 相关代码（最近 3 个 commit）：
  - `8176cce feat(agent): _drive_react_loop 按 Settings 施加上下文预算(窗口+tool截断)`
  - `02d3061 feat(agent): build_messages 滑动窗口 + 旧工具结果截断(默认关闭)`
  - `d8a362b feat(agent): Phase3 新增上下文预算配置(窗口/tool截断字符/保全量数)`
- Phase 3 设计文档：`D:\GEO2\docs\superpowers\specs\2026-07-13-phase3-context-budget-design.md`（按现状实际存在性调整）

- [ ] **Step 1: 读取 Phase 3 三个 commit 的代码变更**

```bash
git -C "D:/GEO2" show 8176cce --stat 2>&1 | head -20
git -C "D:/GEO2" show 02d3061 --stat 2>&1 | head -20
git -C "D:/GEO2" show d8a362b --stat 2>&1 | head -20
```

预期：识别 build_messages / Settings / 滑动窗口 / 截断的实现位置。

- [ ] **Step 2: 读取 build_messages 与上下文预算相关代码**

记录：滑动窗口大小、截断字符阈值、保全消息数等。

- [ ] **Step 3: 写入 §1–§6（完整模板）**

- [ ] **Step 4: 自检**

```bash
grep -c "^## " "D:/GEO2/docs/review/03-context-control.md"
```

Expected: ≥ 6

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2"
git add "docs/review/03-context-control.md"
git commit -m "docs(review): 锐评 03 上下文可控"
```

---

## Task 5: 产出 04-permission.md（锐评维度 4）

**Files:**
- Create: `D:\GEO2\docs\review\04-permission.md`

**Inputs:**
- `D:\GEO2\docs\review\00-learning-summary.md` §6.4
- GEO2 backend/ 中权限相关代码（grep 关键词：permission / auth / authorize / confirm）

- [ ] **Step 1: 调研权限相关代码**

```bash
grep -rEn "permission|authorize|require_auth|allow_" "D:/GEO2/backend" --include="*.py" 2>&1 | head -30
```

预期：识别权限检查点。

- [ ] **Step 2: 读取权限核心模块**

记录：权限策略类型、是否声明式、审计日志位置。

- [ ] **Step 3: 写入 §1–§6（完整模板）**

- [ ] **Step 4: 自检 + Commit**

```bash
grep -c "^## " "D:/GEO2/docs/review/04-permission.md"
```

Expected: ≥ 6

```bash
cd "D:/GEO2"
git add "docs/review/04-permission.md"
git commit -m "docs(review): 锐评 04 权限策略"
```

---

## Task 6: 产出 05-failure-recovery.md（锐评维度 5）

**Files:**
- Create: `D:\GEO2\docs\review\05-failure-recovery.md`

**Inputs:**
- `D:\GEO2\docs\review\00-learning-summary.md` §6.5
- GEO2 backend/agent/*.py 中的 try/except / retry / fallback 模式

- [ ] **Step 1: 调研失败处理模式**

```bash
grep -rEn "except|retry|fallback|backoff" "D:/GEO2/backend/agent" --include="*.py" 2>&1 | head -30
```

- [ ] **Step 2: 识别关键失败路径**

记录：哪些失败有重试、哪些有降级、哪些直接抛错。

- [ ] **Step 3: 写入 §1–§6**

- [ ] **Step 4: 自检 + Commit**

```bash
grep -c "^## " "D:/GEO2/docs/review/05-failure-recovery.md"
```
Expected: ≥ 6

```bash
cd "D:/GEO2"
git add "docs/review/05-failure-recovery.md"
git commit -m "docs(review): 锐评 05 失败恢复"
```

---

## Task 7: 产出 06-evaluation.md（锐评维度 6）

**Files:**
- Create: `D:\GEO2\docs\review\06-evaluation.md`

**Inputs:**
- `D:\GEO2\docs\review\00-learning-summary.md` §6.6 / §7
- GEO2 evals/、tests/ 目录
- PDF：`D:\Agent\学习文档\helson\Agent 测评怎么做？新人也能看懂的评估体系入门.pdf`（按需精读）

- [ ] **Step 1: 调研评测资产**

```bash
ls "D:/GEO2/evals/" 2>&1 | head -20
ls "D:/GEO2/tests/" 2>&1 | head -20
find "D:/GEO2" -name "*eval*" -type d 2>&1 | head -10
```

- [ ] **Step 2: 抽样评测用例**

读 2–3 个评测文件，记录：覆盖场景、评测维度、是否可回归。

- [ ] **Step 3: 写入 §1–§6**

- [ ] **Step 4: 自检 + Commit**

```bash
grep -c "^## " "D:/GEO2/docs/review/06-evaluation.md"
```
Expected: ≥ 6

```bash
cd "D:/GEO2"
git add "docs/review/06-evaluation.md"
git commit -m "docs(review): 锐评 06 评测体系"
```

---

## Task 8: 产出 07-observability.md（锐评维度 7）

**Files:**
- Create: `D:\GEO2\docs\review\07-observability.md`

**Inputs:**
- `D:\GEO2\docs\review\00-learning-summary.md` §6.7
- GEO2 backend/ 中日志、追踪、token 统计相关代码

- [ ] **Step 1: 调研可观测性栈**

```bash
grep -rEn "logging|tracing|sentry|langfuse|trace_id" "D:/GEO2/backend" --include="*.py" 2>&1 | head -30
```

- [ ] **Step 2: 识别关键模块**

记录：日志格式、是否带 trace_id、是否记录 token 成本、是否有可视化面板接入。

- [ ] **Step 3: 写入 §1–§6**

- [ ] **Step 4: 自检 + Commit**

```bash
grep -c "^## " "D:/GEO2/docs/review/07-observability.md"
```
Expected: ≥ 6

```bash
cd "D:/GEO2"
git add "docs/review/07-observability.md"
git commit -m "docs(review): 锐评 07 可观测性"
```

---

## Task 9: 产出 08-hitl.md（锐评维度 8）

**Files:**
- Create: `D:\GEO2\docs\review\08-hitl.md`

**Inputs:**
- `D:\GEO2\docs\review\00-learning-summary.md` §6.8
- GEO2 backend/ 中确认流相关代码

- [ ] **Step 1: 调研 HITL 流程**

```bash
grep -rEn "confirm|approval|user_input|hitl|require_user" "D:/GEO2/backend" --include="*.py" 2>&1 | head -30
```

- [ ] **Step 2: 识别高风险操作与确认点**

记录：哪些操作需要确认、确认 UI 在哪、是否有反馈回路。

- [ ] **Step 3: 写入 §1–§6**

- [ ] **Step 4: 自检 + Commit**

```bash
grep -c "^## " "D:/GEO2/docs/review/08-hitl.md"
```
Expected: ≥ 6

```bash
cd "D:/GEO2"
git add "docs/review/08-hitl.md"
git commit -m "docs(review): 锐评 08 HITL"
```

---

## Task 10: 产出 09-cost-latency.md（锐评维度 9）

**Files:**
- Create: `D:\GEO2\docs\review\09-cost-latency.md`

**Inputs:**
- `D:\GEO2\docs\review\00-learning-summary.md` §6.9
- GEO2 Phase 3 截断后的 token 消耗数据（代码 + 配置）

- [ ] **Step 1: 调研成本/延迟记录**

```bash
grep -rEn "tokens|usage|cost|latency|duration" "D:/GEO2/backend" --include="*.py" 2>&1 | head -30
```

- [ ] **Step 2: 识别成本/延迟暴露点**

记录：是否每次调用记录、是否有聚合、是否有阈值告警。

- [ ] **Step 3: 写入 §1–§6**

- [ ] **Step 4: 自检 + Commit**

```bash
grep -c "^## " "D:/GEO2/docs/review/09-cost-latency.md"
```
Expected: ≥ 6

```bash
cd "D:/GEO2"
git add "docs/review/09-cost-latency.md"
git commit -m "docs(review): 锐评 09 成本/延迟"
```

---

## Task 11: 产出 10-architecture-layering.md（锐评维度 10）

**Files:**
- Create: `D:\GEO2\docs\review\10-architecture-layering.md`

**Inputs:**
- `D:\GEO2\docs\review\00-learning-summary.md` §3 / §4 / §6.10
- GEO2 backend/ 模块结构
- PDF（按需精读）：
  - `D:\Agent\学习文档\helson\02-读完整项目不要从第一行开始，先找五层边界.pdf`
  - `D:\Agent\学习文档\helson\03-Agent库为什么不是一个文件-谈分层设计.pdf`
  - `D:\Agent\学习文档\helson\04-技术栈那么多，你只需要知道每层解决什么问题.pdf`

- [ ] **Step 1: 调研 backend 模块结构**

```bash
ls "D:/GEO2/backend" 2>&1
find "D:/GEO2/backend" -maxdepth 2 -type d 2>&1
```

- [ ] **Step 2: 识别层间依赖**

读 2–3 个核心模块的 import 关系，判断是否遵守 Types → Config → Repo → Service → Runtime → UI。

- [ ] **Step 3: 写入 §1–§6**

- [ ] **Step 4: 自检 + Commit**

```bash
grep -c "^## " "D:/GEO2/docs/review/10-architecture-layering.md"
```
Expected: ≥ 6

```bash
cd "D:/GEO2"
git add "docs/review/10-architecture-layering.md"
git commit -m "docs(review): 锐评 10 架构分层"
```

---

## Task 12: 产出 11-harness-engineering.md（锐评维度 11）

**Files:**
- Create: `D:\GEO2\docs\review\11-harness-engineering.md`

**Inputs:**
- `D:\GEO2\docs\review\00-learning-summary.md` §5 / §6.11
- GEO2 docs/ 仓库化状态（git status 中 docs 清理动作）
- AGENTS.md 是否存在（grep 一下）
- PDF（按需精读）：
  - `D:\Agent\学习文档\helson\05-最后别做万能助手，用一个垂直项目验证能力.pdf`
  - `D:\Agent\学习文档\helson\什么样的 Agent 项目才算好项目.pdf`
  - `D:\Agent\学习文档\helson\怎么判断你的简历是否合格？ (1)(1).pdf`

- [ ] **Step 1: 调研 Harness 范式六维度**

```bash
ls "D:/GEO2/AGENTS.md" 2>&1
ls "D:/GEO2/docs/superpowers" 2>&1
find "D:/GEO2" -name ".eslintrc*" -o -name "pyproject.toml" -o -name "ruff.toml" -o -name ".flake8" 2>&1 | head -10
```

- [ ] **Step 2: 评估六维度符合度**

对 `00-learning-summary.md` §5 的六个 Harness 概念逐一打勾：仓库即记录系统 / 地图非手册 / 机械化执行 / Agent 可读性 / 吞吐量改变合并理念 / 熵管理。

- [ ] **Step 3: 写入 §1–§6**

子结构按六维度分小节。

- [ ] **Step 4: 自检 + Commit**

```bash
grep -c "^## " "D:/GEO2/docs/review/11-harness-engineering.md"
```
Expected: ≥ 6

```bash
cd "D:/GEO2"
git add "docs/review/11-harness-engineering.md"
git commit -m "docs(review): 锐评 11 Harness 范式符合度"
```

---

## Task 13: 产出 README.md（主页）

**Files:**
- Create: `D:\GEO2\docs\review\README.md`

**Inputs:**
- 11 个锐评文件（02-12）的最终评分与关键发现
- `00-learning-summary.md` 总分计算逻辑

- [ ] **Step 1: 汇总 11 维度评分**

从每个锐评文件 §4 提取最终评分。

- [ ] **Step 2: 计算总分与分级**

按 §5 的 0–5 分制汇总，满分 55 分，对应 A/B/C/D/E 分级。

- [ ] **Step 3: 写入 README.md**

文件骨架：

```markdown
# GEO2 全套质量锐评报告（2026-07-14）

> 锐评视角：面试官视角  
> 锐评日期：2026-07-14  
> 方法论依据：[00-learning-summary.md](./00-learning-summary.md)  
> 设计 spec：[2026-07-14-geo2-quality-review-design.md](../../superpowers/specs/2026-07-14-geo2-quality-review-design.md)

## 1. 总分与分级

| 总分 | 分级 | 建议 |
| --- | --- | --- |
| XX / 55 | X 级 | … |

## 2. 11 维度评分表

| # | 维度 | 分数 | 关键发现 |
| --- | --- | --- | --- |
| 01 | Agent Loop | X / 5 | … |
| 02 | 工具边界 | X / 5 | … |
| ... | ... | ... | ... |

## 3. 关键发现 Top 5

1. …
2. …

## 4. 强项 Top 3

1. …

## 5. 弱项 Top 3

1. …

## 6. 改进路线

详见 [99-improvement-plan.md](./99-improvement-plan.md)。

## 7. 锐评文件索引

| # | 文件 | 维度 |
| --- | --- | --- |
| 0 | [00-learning-summary.md](./00-learning-summary.md) | 学习总结 |
| 1 | [01-agent-loop.md](./01-agent-loop.md) | Agent Loop |
| ... | ... | ... |
| 11 | [11-harness-engineering.md](./11-harness-engineering.md) | Harness 范式 |
| 99 | [99-improvement-plan.md](./99-improvement-plan.md) | 改进计划 |
```

- [ ] **Step 4: 自检**

```bash
grep -c "^## " "D:/GEO2/docs/review/README.md"
```
Expected: ≥ 7（7 个一级章节）

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2"
git add "docs/review/README.md"
git commit -m "docs(review): 产出主页(总分 + 维度表 + 关键发现)"
```

---

## Task 14: 产出 99-improvement-plan.md（改进计划）

**Files:**
- Create: `D:\GEO2\docs\review\99-improvement-plan.md`

**Inputs:**
- 11 个锐评文件 §6 改进建议
- README.md 总分

- [ ] **Step 1: 汇总所有改进建议**

从 11 个锐评文件 §6 提取全部改进项，关联维度。

- [ ] **Step 2: 按优先级 + 估时排序**

- 高优先级（建议立即做）：直接影响面试总分 / 安全风险
- 中优先级（下一个 sprint）：补齐关键维度
- 低优先级（可选优化）：体验/卓越化

- [ ] **Step 3: 写入 99-improvement-plan.md**

文件骨架：

```markdown
# GEO2 改进计划（基于锐评 2026-07-14）

> 关联：[README.md](./README.md) 总分 / 11 维度评分

## 高优先级（建议立即做）

- [ ] P0: <改进项> — 关联锐评维度 NN — 估时 Xd — 影响：…

## 中优先级（下一个 sprint）

- [ ] P1: …

## 低优先级（可选优化）

- [ ] P2: …

## 改进项与锐评维度的映射

| 改进项 | 关联锐评 | 当前分 | 目标分 | 估时 |
| --- | --- | --- | --- | --- |
```

- [ ] **Step 4: 自检**

```bash
grep -c "^## " "D:/GEO2/docs/review/99-improvement-plan.md"
```
Expected: ≥ 4（高/中/低优先级 + 映射表）

- [ ] **Step 5: 提交最终 commit 并打 tag**

```bash
cd "D:/GEO2"
git add "docs/review/99-improvement-plan.md"
git commit -m "docs(review): 产出改进计划(99-improvement-plan.md)"
git tag -a review-2026-07-14 -m "GEO2 全套质量锐评完成(2026-07-14)"
```

---

## 验收检查清单（Task 14 后执行）

- [ ] `D:\GEO2\docs\review\` 下存在 14 个文件
- [ ] 每个锐评文件 §1–§6 章节完整（grep -c "^## " ≥ 6）
- [ ] README.md 汇总总分 + 分级 + 维度表
- [ ] 改进计划按优先级排序 + 估时
- [ ] 全部 commit 已落到 main 分支
- [ ] tag `review-2026-07-14` 已创建