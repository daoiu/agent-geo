# 新会话启动话术

> **目的**：让新打开的 Claude Code 会话（零上下文）能立即理解项目并开始按 plan 实施。

## 使用方法

打开新会话，把下面"完整版启动话术"整段复制粘贴发送即可。如果上下文紧张，用"极简版"。

---

## 完整版启动话术

```
# 项目背景
我要实施 GEO 优化 Agent v0.1。这是一个 Web 应用，给非技术市场人员用的 GEO（生成引擎优化）诊断工具。

# 必读文档
请先并行读取以下两个文件：
1. 设计文档：D:/GEO2/docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md
2. 实施计划：D:/GEO2/docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md

# 你需要遵循的流程
1. 第一步必须调用 superpowers:using-superpowers skill（这是 superpowers 插件的强制规则）
2. 阅读完两个文档后，询问我执行方式（subagent-driven-development 推荐 / executing-plans 二选一）
3. 获得我的选择后，按对应 skill 开始执行
4. 不要重新 brainstorming —— 设计已经定稿，不要再问"用 Web 还是 CLI"这种问题

# 项目硬性约束（违反就是 bug）
- 语言：所有对话、代码注释、commit message、UI 文案必须用简体中文（项目 CLAUDE.md 规定）
- 提交规范：Conventional Commits（feat/fix/test/chore/docs/refactor）
- TDD 纪律：每个 task 第一步必须是"写失败测试"，禁止先写实现
- commit 频率：每完成一个 task 立即 commit，不要攒
- 进度反馈：每完成 3-5 个 task 主动汇报一次进度，列出已完成/进行中/下一步
- 代码质量：保持每个文件单一职责，单文件超过 500 行需要拆分

# 环境信息
- 工作目录：D:/GEO2
- 平台：Windows 11
- 当前是空的（除 docs/ 外），git 已初始化，main 分支
- Python 3.11+ 可用
- Node.js 20+ 可用
- Docker + docker-compose 可用

# 关键技术决策（不要再讨论）
- 后端：FastAPI 0.115+ 单体 + asyncio 后台任务 + SQLite
- 前端：React 18 + TypeScript + Vite + Tailwind + Recharts
- LLM：DeepSeek（默认）+ Kimi（可选）
- PDF：WeasyPrint（后端预渲染）
- 测试：pytest + pytest-asyncio + respx（HTTP mock）+ Playwright（E2E）

# Plan 里有 28 个 task，按 Phase 0→10 顺序执行
- Phase 0 脚手架（4 个 task，最先做）
- Phase 10 收尾测试 + 文档（最后做）

# 阻塞时怎么办
- 如果发现 plan 有错（接口对不上、类型冲突、缺失文件），停下来告诉我，不要自行脑补
- 如果测试 mock 不对，先告诉我失败的测试名 + 错误信息
- 如果需要选 A/B 方案（plan 没规定），停下来问我，不要默认

# 开始
确认收到后：
1. 调 using-superpowers skill
2. 读两个文档
3. 报告"已读完，准备就绪，请选择执行方式"
4. 等我选
```

---

## 极简版（上下文紧张时用）

```
按 D:/GEO2/docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md
实施 GEO Agent v0.1。先：
1. 调 superpowers:using-superpowers
2. 读 plan + 同目录 specs/ 下的设计文档
3. 报告读完，问执行方式（subagent-driven / inline）
4. 简体中文回复，Conventional Commits，TDD 严格
```

---

## 预期新会话的响应

正常情况下，新会话会按以下顺序回复：

1. **调用 `superpowers:using-superpowers` skill**（无可见输出）
2. **读取两个文档**（可能用 Read 工具）
3. **回复一段确认**：报告"已读完，准备就绪"，列出关键决策摘要
4. **问执行方式**：用 AskUserQuestion 提供两个选项
5. **等您选择**（subagent-driven 或 inline）

## 如果新会话卡住怎么办

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 新会话又问"用 FastAPI 还是 Django" | 没读到 spec | 让它"先读 D:/GEO2/docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md" |
| 新会话又 brainstorm | 误以为还在设计阶段 | 让它"读 HANDOFF.md（你发的文档），设计已定稿" |
| 新会话用英文回复 | 没遵守语言约束 | 提醒"项目语言规范：所有对话用简体中文" |
| 新会话跳过测试直接写实现 | 没遵守 TDD | 提醒"每个 task 第一步必须是写失败测试" |
| 新会话上来就要装 npm 依赖 | 没读 plan | 让它"按 plan Phase 0 Task 0.1 开始" |

## 关键文件清单

新会话应该只读以下文件，其他文件按 plan 逐步创建：

| 文件 | 路径 |
|---|---|
| 设计文档 | `D:/GEO2/docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md` |
| 实施计划 | `D:/GEO2/docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md` |
| 全局约束 | `D:/GEO2/CLAUDE.md`（如果存在） |
| 本文件 | `D:/GEO2/docs/HANDOFF.md` |

## Phase 顺序速查

```
Phase 0  → 项目脚手架（gitignore, FastAPI hello, React+Vite, docker-compose）  4 task
Phase 1  → 数据层（SQLAlchemy async + Pydantic + Repository）                 3 task
Phase 2  → 异常 + LLM Client（DeepSeek + Kimi）                              3 task
Phase 3  → 爬虫（基础 + Schema/EEAT/Structure + robots.txt + 综合 audit）      4 task
Phase 4  → 评分引擎（5 维 + 建议生成，IP 核心）                               1 task
Phase 5  → PDF 渲染（Jinja2 + WeasyPrint）                                   1 task
Phase 6  → 服务层（DiagnosisService 编排 + ReportService）                   2 task
Phase 7  → API 层（POST /diagnosis, GET /status, /reports, /pdf）            1 task
Phase 8  → 异步 Worker（asyncio.Lock 单飞）                                  1 task
Phase 9  → 前端（API client + Wizard + Status + Report View + List + App）   6 task
Phase 10 → E2E + 手动验证 + README                                           4 task
```

## 手动验证清单（v0.1 完成判定）

完整版见 `D:/GEO2/docs/MANUAL_VERIFICATION.md`。4 个场景全过才算完成：

1. ✅ 完整诊断流程（小米品牌，90s 内完成）
2. ✅ 网站无法访问（错误处理友好）
3. ✅ LLM 部分失败（mention_rate 显示 N/A）
4. ✅ PDF 下载与中文渲染（不乱码）

## 项目当前状态

- ✅ 设计文档：已 commit（`5885226`）
- ✅ 实施计划：已 commit（`68d4314`）
- ✅ 本文档（handoff）：commit 见 git log
- ❌ 代码：尚未开始（这是新会话要做的事）
