# 新会话启动话术

> **目的**：让新打开的 Claude Code 会话（零上下文）能立即理解项目状态、v0.4 完成情况、v0.5 准备工作。

## 当前项目状态（2026-07-10）

- ✅ **v0.1 诊断** + **v0.2 知识库 + 内容生成** + **v0.3 发布 + 监测闭环** + **v0.4 自主决策 Agent** 全部设计 + 实施完成
- 🎯 **v0.5** 是下一步：行业基准 / 竞品对比 + 向量检索升级（已有 spec + plan）
- 后端 **387 个测试通过**，前端 `tsc --noEmit` 0 errors

详细版本演进见 [ROADMAP.md](ROADMAP.md)，变更记录见 [CHANGELOG.md](CHANGELOG.md)。

---

## 启动 v0.5 实施（最新版）

```
按 D:/GEO2/docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.5.md
实施 GEO Agent v0.5（行业基准 + 竞品对比 + 向量检索升级）。

前置条件：v0.1 + v0.2 + v0.3 + v0.4 代码已存在并测试通过。

流程：
1. 调 superpowers:using-superpowers skill
2. 读 plan + specs/2026-07-10-geo-agent-v0.5-design.md
3. 报告读完，问执行方式（subagent-driven / inline）
4. 简体中文回复，Conventional Commits，TDD 严格

约束：
- 复用 v0.1-v0.4 的所有模块（不重写）
- 不引入新 LLM SDK（用 v0.1 的 LLMClient 扩展）
- 沿用 v0.4 的 SSE / 持久化模式
- 写类工具（如果有）需 human confirmation
- v0.4 SSRF 守卫继续生效（环境变量控制 dev/prod）
```

---

## 启动 v0.4 实施（已完成 — 仅当 v0.4 之前未实施时使用）

如果新会话需要重新理解 v0.4 的设计，可读 v0.4 spec 和 plan：

```
按 D:/GEO2/docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.4.md
实施 GEO Agent v0.4（~22 个 task：自主决策 Agent 层）。

流程：
1. 调 superpowers:using-superpowers skill
2. 读 plan + specs/2026-07-10-geo-agent-v0.4-design.md
3. 报告读完，问执行方式（subagent-driven / inline）
4. 简体中文回复，Conventional Commits，TDD 严格
```

---

## 关键文件清单

按文件类型分类，所有新会话都可读：

### 当前项目状态

| 文件 | 路径 | 用途 |
|---|---|---|
| 产品路线图 | `D:/GEO2/docs/ROADMAP.md` | 跨版本演进方向（v0.1 → v0.6+） |
| 变更日志 | `D:/GEO2/docs/CHANGELOG.md` | v0.1-v0.4 完整变更记录 |
| 启动话术 | `D:/GEO2/docs/HANDOFF.md` | 本文件 |
| 全局约束 | `C:/Users/p'q'y/.claude/CLAUDE.md` | 全局规则（语言规范等） |
| README | `D:/GEO2/README.md` | 功能列表 + 快速开始 |

### v0.4（已完成）

| 文件 | 路径 | 用途 |
|---|---|---|
| 设计文档 | `D:/GEO2/docs/superpowers/specs/2026-07-10-geo-agent-v0.4-design.md` | v0.4 做什么 + 为什么 |
| 实施计划 | `D:/GEO2/docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.4.md` | 22 个 TDD task |
| 手动验证清单 | `D:/GEO2/docs/MANUAL_VERIFICATION_V0.4.md` | 8 个发布前必跑场景 |
| 启动话术 | `D:/GEO2/docs/HANDOFF_V0.4.md` | v0.4 专用启动话术（历史） |

### v0.5（下一步）

| 文件 | 路径 | 用途 |
|---|---|---|
| 设计文档 | `D:/GEO2/docs/superpowers/specs/2026-07-10-geo-agent-v0.5-design.md` | v0.5 做什么 + 为什么 |
| 实施计划 | `D:/GEO2/docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.5.md` | v0.5 实施步骤 |
| 启动话术 | `D:/GEO2/docs/HANDOFF_V0.5.md` | v0.5 专用启动话术 |

### 历史版本

| 版本 | spec | plan | verify | handoff |
|---|---|---|---|---|
| v0.1 | [link](superpowers/specs/2026-07-09-geo-optimization-agent-design.md) | [link](superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md) | [MANUAL_VERIFICATION.md](MANUAL_VERIFICATION.md) | [HANDOFF_V0.1](HANDOFF_V0.1.md)（如果存在） |
| v0.2 | [link](superpowers/specs/2026-07-09-geo-agent-v0.2-design.md) | [link](superpowers/plans/2026-07-09-geo-optimization-agent-v0.2.md) | [MANUAL_VERIFICATION_V0.2.md](MANUAL_VERIFICATION_V0.2.md) | [HANDOFF_V0.2.md](HANDOFF_V0.2.md) |
| v0.3 | [link](superpowers/specs/2026-07-10-geo-agent-v0.3-design.md) | [link](superpowers/plans/2026-07-10-geo-optimization-agent-v0.3.md) | [MANUAL_VERIFICATION_V0.3.md](MANUAL_VERIFICATION_V0.3.md) | [HANDOFF_V0.3.md](HANDOFF_V0.3.md) |

---

## 项目硬性约束（违反就是 bug）

- **语言**：所有对话、代码注释、commit message、UI 文案必须用简体中文（项目 CLAUDE.md 规定）
- **提交规范**：Conventional Commits（feat/fix/test/chore/docs/refactor）
- **TDD 纪律**：每个 task 第一步必须是"写失败测试"，禁止先写实现
- **commit 频率**：每完成一个 task 立即 commit，不要攒
- **进度反馈**：每完成 3-5 个 task 主动汇报一次进度，列出已完成/进行中/下一步
- **代码质量**：保持每个文件单一职责，单文件超过 500 行需要拆分
- **SSRF 守卫**：新工具涉及外部 URL 必须用 `app.domain.security.ssrf.validate_url_for_ssrf()` 校验
- **不引 LangChain / LangGraph / Claude SDK**：v0.4 决定，用 OpenAI SDK + 自己写 ReAct
- **复用优先**：v0.5 不要重写 v0.1-v0.4 的代码，必要时扩展现有模块

## 环境信息

- 工作目录：`D:/GEO2`
- 平台：Windows 11
- git 已初始化，main 分支
- Python 3.11+ 可用
- Node.js 20+ 可用
- Docker + docker-compose 可用

## 关键技术决策（已固化，不要再讨论）

- 后端：FastAPI 0.115+ 单体 + asyncio 后台任务 + SQLite
- 前端：React 18 + TypeScript + Vite + Tailwind + Recharts
- LLM：DeepSeek（默认）+ Kimi（可选），OpenAI SDK 兼容
- PDF：WeasyPrint（后端预渲染）
- 测试：pytest + pytest-asyncio + respx（HTTP mock）+ Playwright（E2E）
- Agent：原生 ReAct 循环 + SSE + 3 工具 + Human-in-the-loop
- 数据库迁移：v0.4 起每版本新建 `orm_v0X.py` 文件，由 conftest 顶层 import 注册到 Base.metadata

## 阻塞时怎么办

- 如果发现 plan 有错（接口对不上、类型冲突、缺失文件），停下来告诉我，不要自行脑补
- 如果测试 mock 不对，先告诉我失败的测试名 + 错误信息
- 如果需要选 A/B 方案（plan 没规定），停下来问我，不要默认
- 如果发现 v0.4 文件被 reset（与本 HANDOFF 描述不符），先看 git log 确认历史

## 历史背景（v0.1 启动话术已被替换）

v0.4 是 v0.1 "GEO 诊断" → v0.5 "向量检索" 演进路径上的"自主决策 Agent"层。
v0.4 方向变更：原计划"多用户 + 权限"被用户重新定位为"自然语言入口"。
原 v0.4 (多用户) → 推迟到 v1.0。
原 v0.5 (向量检索) → 现在是真正的 v0.5。
原 v0.6 (Agent 化) → 提前到 v0.4 完成。

详细见 [ROADMAP.md §13](ROADMAP.md)。
