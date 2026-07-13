# 会话 2 开局模板 — 阶段 2（P1 核心 20 项）

> **用途**：阶段 1 完成后启动 GEO2 全面升级的**第二次会话**。
> **覆盖范围**：阶段 2（P1 核心 20 项）= 20d 工作量。
> **完成后预期**：47.5/55 分（A 级下限），打 `upgrade-stage-2` tag，**触发用户验收**。

---

## 📋 直接复制粘贴下面整段到新会话

```
我要继续执行 GEO2 全面升级阶段 2（P1 核心 20 项，Task 8-27）。请按以下顺序读取上下文：

【必读 5 份】
1. D:\GEO2\docs\superpowers\specs\2026-07-14-geo2-upgrade-design.md（升级设计 spec，含阶段 2 任务清单）
2. D:\GEO2\docs\superpowers\plans\2026-07-14-geo2-upgrade-plan.md（实施 plan，本阶段在 §"阶段 2 / 阶段 3 / 阶段 4" 章节）
3. D:\GEO2\docs\review\README.md（**已更新到 40/55 分**，11 维度评分表）
4. D:\GEO2\docs\review\99-improvement-plan.md（55 项改进清单，重点 P1 项 #7-26）
5. D:\GEO2\backend\evals\baseline_report.md（阶段 1 留下的基线数据，用于后续对比）

【继承决策】
- 升级范围：全 4 阶段
- **验收节奏：本次完成（阶段 2）后用户一次性 review 0+1+2 三阶段产出**
- 执行隔离：main 直接，本阶段完成打 upgrade-stage-2 tag
- 执行模式：Inline Execution
- 语言：简体中文

【起点状态】
- 当前总分：40/55（阶段 1 完成后）
- 当前分支：main
- 当前 tags：review-2026-07-14, geo2-upgrade-spec-2026-07-14, **upgrade-stage-1**（新）
- 阶段 1 新增：backend/evals/ + AGENTS.md + .github/workflows/ci.yml + ruff/mypy + 4 处代码修改
- 已知 baseline：见 backend/evals/baseline_report.md

【本次会话任务】
执行阶段 2 全部 20 项 P1 核心改进（Task 8-27），按以下顺序：

| # | 改进项 | 估时 | 关键文件 |
| --- | --- | --- | --- |
| 8 | MAX_REACT_ITERATIONS → Settings | 0.5d | core/config.py + react_loop.py:35 |
| 9 | 嵌套 async with → DI | 1d | react_loop.py:291-398 |
| 10 | LLM 失败显式降级 | 1d | react_loop.py:307 |
| 11 | 工具 schema 防 drift 测试 | 0.5d | 新建 tests/test_tool_schema_drift.py |
| 12 | token 级截断（tiktoken） | 1d | react_loop.py:build_messages + config.py |
| 13 | 历史摘要策略（窗口+摘要双层） | 2d | 新建 domain/agent/summarizer.py |
| 14 | 声明式权限（per-tool requires_confirmation） | 1d | tools.py + tool_executor.py |
| 15 | HumanConfirmation 专项测试 | 1d | 新建 tests/test_human_confirmation.py |
| 16 | react_loop transient/programming 区分 | 1d | react_loop.py:352-393 |
| 17 | 故障注入测试套件 | 2d | 新建 tests/test_fault_injection.py |
| 18 | 接入 Sentry | 0.5d | main.py + requirements.txt |
| 19 | 接入 Langfuse | 0.5d | llm_client.py + requirements.txt |
| 20 | trace_id 串联（contextvars） | 1d | 新建 core/tracing.py + 各 logger |
| 21 | 显式 Providers 抽象 | 3d | 新建 core/providers.py |
| 22 | import-linter | 1d | pyproject.toml + .import-linter |
| 23 | tech-debt-tracker.md | 0.5d | 新建 docs/tech-debt-tracker.md |
| 24 | turn 延迟 + LLM 耗时 + cost 字段 | 1.5d | react_loop.py + llm_client.py + config.py |
| 25 | 慢查询告警（LLM > 60s） | 0.5d | llm_client.py |
| 26 | pending 超时自动取消 | 0.5d | react_loop.py + agent_repo.py |
| 27 | reject 理由进入 LLM 上下文 | 1d | agent_chat.py + react_loop.py |

每项独立 commit。完成后打 upgrade-stage-2 tag，**等我验收**。

【TDD 原则（继承）】
- Task 12 token 级截断：必须先接 tiktoken + 写测试
- Task 14 声明式权限：必须先在 tests/test_tool_schema_drift.py 加断言
- Task 17 故障注入：mock RateLimitError / TimeoutError，验证降级
- Task 22 import-linter：先写阻断测试，再修违反

【验证门控（阶段 2 完成时）】
- [ ] 540 原有测试 + ~100 新增测试全部通过
- [ ] import-linter 阻断测试通过
- [ ] Sentry/Langfuse 接通（看面板有事件）
- [ ] 端到端 turn P95 < 60s 告警正常
- [ ] pytest + ruff + mypy 全绿
- [ ] baseline 复跑，pass rate 提升 ≥ 10%
- [ ] docs/review/README.md 11 维度评分表更新到 47.5

【执行要求】
1. 读完 5 份文档后先回报"起点状态确认 + 当前 Task 列表"，等我确认无误
2. 每项 commit 格式：docs|feat|fix|refactor|test: <一句话>
3. 阶段完成打 tag：git tag -a upgrade-stage-2 -m "GEO2 升级阶段 2 完成(P1 核心 20 项,总分 40→47.5 A 级)"
4. 最后更新 docs/review/README.md 11 维度评分表（预期 7/11 维度提升到 4.5+）

【应急】
如果 Sentry/Langfuse 缺 API key：先把集成代码写好，配置用 env 占位，文档说明"需 OPENAI_API_KEY/LANGFUSE_PUBLIC_KEY secret"。不要阻塞 commit。
如果 mypy 初次跑大量错误：分批修，先保证 strict 模式只对新代码生效。
如果读不到 baseline_report.md：报告用户，可能阶段 1 没完成 baseline。
```

---

## ✅ 新会话读完 5 份文档后必须能回答

- [ ] 阶段 2 共几个 Task？（共 20 个：Task 8-27）
- [ ] 阶段 2 完成后预期分数？（40 → 47.5 A 级）
- [ ] 11 维度评分表当前状态？（见 docs/review/README.md §2）
- [ ] Task 21（Providers 抽象）涉及哪些关注点？（auth / telemetry / feature flag）
- [ ] Task 22（import-linter）机械阻断什么？（repo → service 反向依赖）
- [ ] 阶段 2 完成打什么 tag？（upgrade-stage-2）
- [ ] 本次完成后是否验收？（**是**，这是约定的验收点）

---

## 🛟 应急方案

如果新会话没读到 baseline_report.md：

```
请确认 backend/evals/baseline_report.md 是否存在。
如果不存在，说明阶段 1 未完成或未正确提交 baseline，
请用 git log 检查 upgrade-stage-1 tag 是否存在。
```

如果新会话找不到 review/README.md 的 11 维度评分：

```
请用 grep 在 docs/review/README.md 中搜索 "11 维度评分表" 章节，
找到 §2 节，按行号读取当前最新评分。
```

---

## 📤 会话 2 结束的交付物

- [ ] 20 个 Task 全部 commit
- [ ] 11 维度评分全部 ≥ 4.5（共 7 个提升）
- [ ] 新增 ~100 测试通过
- [ ] Sentry/Langfuse 接通
- [ ] import-linter 阻断测试通过
- [ ] turn 延迟 + cost 字段就位
- [ ] `docs/tech-debt-tracker.md` 首批条目
- [ ] `docs/review/README.md` 11 维度评分表更新到 47.5
- [ ] tag `upgrade-stage-2` 已创建
- [ ] baseline_report.md 复跑对比（pass rate 提升 ≥ 10%）

---

## 🎯 用户验收清单（会话 2 结束后用户做）

用户会基于 review/README.md 更新后的 11 维度评分表 + 20 个 commit + baseline 复跑数据，验收以下内容：

1. **分数提升是否合理**（每个维度的提升是否站得住脚）
2. **Sentry/Langfuse 事件是否合理**（无大量异常噪声）
3. **baseline 提升是否真实**（不是靠降难度）
4. **commit 粒度是否合理**（每个改进项独立可回滚）
5. **新增测试是否有价值**（不是只为了覆盖率）

验收通过后，用户开**会话 3** 用 [`handoff-prompt-stage3.md`](./handoff-prompt-stage3.md) 模板继续阶段 3+4。

如果验收不通过：用户在会话 2 直接说"回滚 Task XX"或"修 X 后再验"。