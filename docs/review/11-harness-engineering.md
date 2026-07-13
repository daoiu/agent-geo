# 11. Harness 范式符合度

> 面试官视角：本维度在 GEO2 的现状、评分、讲述建议、改进路径。

## 1. 维度定义

项目整体对 Harness Engineering 范式的符合度。包含 6 个子维度：仓库即记录系统、地图非手册、机械化执行、Agent 可读性、吞吐量改变合并理念、熵管理。

依据：[`00-learning-summary.md` §5, §6.11](./00-learning-summary.md)

## 2. 评分标准（0-5 分制）

| 分数 | 含义 | 触发条件 |
| --- | --- | --- |
| 0 | 缺失 | 完全不符合 Harness 范式 |
| 1 | 雏形 | 1-2 个子维度符合 |
| 2 | 基础 | 3 个子维度符合 |
| 3 | 达标 | 4 个子维度符合 + 有 AGENTS.md + 有 lint/CI |
| 4 | 良好 | 5 个子维度符合 + 吞吐量为优先 |
| 5 | 卓越 | 6 个子维度全符合 + 分离构建/评判智能体 |

## 3. GEO2 现状调研

### 3.1 子维度 1：仓库即记录系统

来源：GEO2 顶层结构

```
.superpowers/sdd/         ← 任务 brief/report 体系（详尽）
.superpowers/sdd-v01-v02-history/  ← 历史任务归档
docs/superpowers/specs/   ← 设计 spec（最近新增）
docs/superpowers/plans/   ← 实施计划（最近新增）
docs/review/              ← 锐评产出（本次新增）
```

**优点**：

- ✓ `.superpowers/sdd/` 详尽记录每个任务的 brief + report
- ✓ 历史归档（sdd-v01-v02-history/）
- ✓ 新增 docs/superpowers/specs/ 与 plans/

**弱项**：

- ✗ **无 AGENTS.md**（仓库地图缺失）
- ✗ 无顶层 README.md（git status 显示已删除）
- ✗ Slack 讨论 / 决策不沉淀到仓库

**子评分：2 / 5**

### 3.2 子维度 2：地图非手册

**AGENTS.md 检查**：

```bash
ls AGENTS.md CLAUDE.md
# No such file or directory
```

**评价**：

- ✗ **完全缺失 AGENTS.md**
- ✗ 没有任何 ~100 行的索引文件
- ✗ 新人进入仓库不知道从哪里看起（docs/review/ + docs/superpowers/specs/ + .superpowers/sdd/ 都分散）

**子评分：0 / 5**

### 3.3 子维度 3：机械化执行

来源：GEO2 顶层结构

```
.github/                   ← ✗ 不存在（无 CI 配置）
.gitlab-ci.yml             ← ✗ 不存在
ruff.toml / .ruff.toml     ← ✗ 不存在
.eslintrc                  ← ✗ 不存在
Makefile                   ← ✗ 不存在
pyproject.toml             ← ✓ 存在（pytest 配置）
```

来源：[`backend/pyproject.toml`](./../backend/pyproject.toml)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["app"]
omit = ["tests/*", "data/*"]
```

**评价**：

- ✓ pytest 配置存在（基本测试框架）
- ✓ coverage 配置存在
- ✗ **无 ruff / mypy / black 等 lint 工具**
- ✗ **无 import-linter（无法机械阻断分层违反）**
- ✗ **无 CI 配置（.github/ 缺失）**
- ✗ 无 pre-commit hooks

**子评分：0 / 5**

### 3.4 子维度 4：Agent 可读性

来源：GEO2 技术栈

- ✓ Python 3.11（无聊、稳定、训练集覆盖好）
- ✓ structlog 24.4.0（成熟库）
- ✓ SQLAlchemy（稳定 ORM）
- ✓ FastAPI（行业标准）
- ✓ Pydantic（参数校验标准）

**前端**：需要查看 frontend/，但从 docs 推测可能是 React/Vue。

**评价**：

- ✓ 技术栈选择符合"无聊技术"原则
- ✓ Pydantic 参数校验（LLM-friendly）
- ✓ Tool schemas 描述详尽（见 02-tool-boundary）
- 部分：未明确为 Agent 优化（如 README 给 Agent 看）

**子评分：3 / 5**

### 3.5 子维度 5：吞吐量改变合并理念

来源：commit 历史（最近 5 个 commit）

```
f73343e chore: 提交在途改动
d3315d9 refactor(memory): 消除代码审查发现的重复与死码
8176cce feat(agent): _drive_react_loop 按 Settings 施加上下文预算(窗口+tool截断)
02d3061 feat(agent): build_messages 滑动窗口 + 旧工具结果截断(默认关闭)
d8a362b feat(agent): Phase3 新增上下文预算配置(窗口/tool截断字符/保全量数)
```

**评价**：

- ✓ 频繁提交（小步快跑）
- ✓ refactor 与 feat 混合（持续清理）
- ✗ 无明确"PR 生命周期极短"的证据（无 PR 数据）
- ✗ 无明确"事后修正优于阻塞"的证据

**子评分：2 / 5**

### 3.6 子维度 6：熵管理

来源：commit 历史

```
d3315d9 refactor(memory): 消除代码审查发现的重复与死码  ← 熵管理
```

**评价**：

- ✓ 有一次显式 refactor（清理代码审查发现的死码）
- ✗ 无定期后台 agent 任务扫描偏差
- ✗ 无自动重构 PR 流程
- ✗ 无技术债追踪表（tech-debt-tracker.md）

**子评分：1 / 5**

### 3.7 子维度汇总

| 子维度 | 评分 | 关键证据 / 缺失 |
| --- | --- | --- |
| 仓库即记录系统 | 2 / 5 | .superpowers/sdd/ 详尽；无 AGENTS.md |
| 地图非手册 | 0 / 5 | 完全缺失 AGENTS.md |
| 机械化执行 | 0 / 5 | 无 lint / 无 CI / 无 import-linter |
| Agent 可读性 | 3 / 5 | 技术栈无聊；Pydantic 友好 |
| 吞吐量改变合并理念 | 2 / 5 | 频繁提交；无 PR 证据 |
| 熵管理 | 1 / 5 | 偶有 refactor；无系统化 |
| **综合** | **1.3 / 5** | 平均 1.3 |

## 4. 评分与理由

**评分：2 / 5（基础，但远未达到 Harness 范式）**

| 综合维度 | 现状 | 评分贡献 |
| --- | --- | --- |
| 6 子维度平均 | 1.3 / 5 | +1 |
| 有 .superpowers/sdd 体系 | ✓ 详尽任务记录 | +0.5 |
| 新增 docs/superpowers/specs/plans | ✓ 最近建立 | +0.5 |
| 仓库决策全部版本化 | 部分（缺失 README/AGENTS） | - |

**关键证据**：

- **强项**：.superpowers/sdd/ 任务管理体系是 GEO2 的 Harness 工程亮点
- **弱项**：缺 AGENTS.md / 缺 CI / 缺 lint / 缺 import-linter

**与行业标准差距**：

- 学习路线 §9 卓越标准：6 个子维度全符合 + 分离构建/评判智能体
- GEO2 仅在 1-2 个子维度达标

## 5. 面试讲点

### 30 秒版本

> .superpowers/sdd/ 详尽任务记录体系；最近建立 docs/superpowers/specs+plans；缺 AGENTS.md、无 lint/CI/import-linter，远未达到 Harness 范式。

### 2 分钟版本

1. **已有体系**：
   - `.superpowers/sdd/` 任务 brief + report（详尽）
   - `docs/superpowers/specs/` 设计 spec（最近建立）
   - `docs/superpowers/plans/` 实施计划（最近建立）
   - 频繁提交 + 偶有 refactor
2. **缺失部分**：
   - **AGENTS.md 完全缺失**（仓库地图）
   - **无 lint 工具**（ruff / mypy）
   - **无 CI 配置**（.github/ 缺失）
   - **无 import-linter**（分层约束靠人维护）
   - **无技术债追踪**
3. **诚实承认**：Harness 范式符合度低（~2/5），但有"开始"的迹象（.superpowers/sdd/）

### 追问预判

| 追问 | 回答要点 |
| --- | --- |
| 为什么没 AGENTS.md？ | 项目阶段聚焦功能；Harness 范式符合度改进在路线图中 |
| 为什么没 CI？ | 个人/小团队开发；测试本地跑（**改进候选**） |
| .superpowers/sdd 怎么用的？ | 每个任务前 brief（输入/输出/约束），完成后 report（实际/偏差/学习） |
| 怎么补齐 Harness 范式？ | 3 步：建 AGENTS.md → 加 ruff + import-linter → 加 GitHub Actions |
| 评测体系呢？ | 见 06-evaluation（1/5）；评测与 Harness 是不同维度 |

## 6. 改进建议

| 优先级 | 改进项 | 关联 |
| --- | --- | --- |
| **P0** | 建 AGENTS.md（~100 行索引，指向 docs/、.superpowers/、backend/） | 见 `99-improvement-plan.md` |
| **P0** | 加 ruff（基础 lint）+ mypy（类型检查） | 见 `99-improvement-plan.md` |
| **P0** | 加 GitHub Actions CI（pytest + lint 自动跑） | 见 `99-improvement-plan.md` |
| P1 | 加 import-linter（机械阻断分层违反） | 见 `99-improvement-plan.md` |
| P1 | 建 tech-debt-tracker.md（技术债追踪表） | 见 `99-improvement-plan.md` |
| P2 | 定期后台 agent 扫描代码偏差 | 见 `99-improvement-plan.md` |
| P2 | 自动重构 PR 流程（定期清理死码） | 见 `99-improvement-plan.md` |

> **核心提示**：Harness 范式符合度是 GEO2 的**第二大薄弱环节**（仅次于评测）。3 个 P0 改进（AGENTS.md / lint / CI）能在 1-2 天内显著提升。

## 7. 面试风险提示

如果面试官问"你的项目符合 Harness Engineering 范式吗？"，按当前状态回答：

- ❌ "我们遵循 Harness 范式"（夸大）
- ✅ "我们在 .superpowers/sdd/ 建立了任务记录体系，docs/superpowers/specs+plans 沉淀设计；Harness 范式符合度改进在路线图中（AGENTS.md / lint / CI 是下个迭代的重点）"（诚实 + 改进意向）

**强烈建议**：在产出 `11-harness-engineering.md` 的同时，先建一个最小 AGENTS.md（哪怕 50 行）作为"开始"的证据。