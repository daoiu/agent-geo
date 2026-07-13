# 会话 1 开局模板 — 阶段 0+1（基线 + P0）

> **用途**：从锐评完成（35/55 B 级）启动 GEO2 全面升级的**第一次会话**。
> **覆盖范围**：阶段 0（基线建立）+ 阶段 1（P0 6 项）= 7-8d 工作量。
> **完成后预期**：40/55 分，打 `upgrade-stage-1` tag，**不验收**直接进阶段 2。

---

## 📋 直接复制粘贴下面整段到新会话

```
我要继续执行 GEO2 全面升级计划（阶段 0+1，Task 0-7）。请按以下顺序读取上下文：

【必读 4 份】
1. D:\GEO2\docs\superpowers\specs\2026-07-14-geo2-upgrade-design.md（升级设计 spec）
2. D:\GEO2\docs\superpowers\plans\2026-07-14-geo2-upgrade-plan.md（实施 plan，Task 0-7 详细步骤 + TDD 测试代码骨架）
3. D:\GEO2\docs\review\README.md（锐评主页，35/55 B 级起点 + 11 维度评分）
4. D:\GEO2\docs\review\99-improvement-plan.md（55 项改进清单）

【用户决策（继承）】
- 升级范围：全 4 阶段（约 92d）
- 验收节奏：阶段 2 后一次性 review（0+1+2），本次不验收
- 执行隔离：main 直接，每阶段打 upgrade-stage-N tag
- 执行模式：Inline Execution
- 语言：所有 commit/文档用简体中文

【起点状态】
- 当前总分：35/55 B 级
- 当前分支：main
- 当前 tags：review-2026-07-14, geo2-upgrade-spec-2026-07-14
- 最近 commit：504fef0 docs(spec+plan): GEO2 全面升级方案
- 关键产出：docs/review/14 个锐评文件 + docs/superpowers/specs+plans 已有升级文档

【本次会话任务】
从 Task 0（建 eval 目录骨架）开始，顺序执行到 Task 7（阶段 1 完成门控 + 打 upgrade-stage-1 tag）。
每完成一项独立 commit。完成后**不要等我验收**，直接结束会话。

【TDD 原则】
每个改进项必须先写测试再写实现。P0 6 项的测试覆盖现状（来自 plan §6.1）：
- Task 5（重试+退避）：测试完全缺失，先写 test_query_single_retries_with_backoff
- Task 4（schema drift）：部分覆盖，加 test_generate_article_schema_drift
- Task 3（反向依赖）：部分覆盖，加 import-linter 阻断测试
- Task 6（memory 捕获）：部分覆盖，加 transient/programming 分类测试

【执行要求】
1. 读完后先回报"起点状态确认 + 当前 Task 列表"，等我确认无误
2. 每项 commit 格式参考之前锐评：docs(review|feat|fix|chore|test): <一句话说明>
3. 阶段完成打 tag：git tag -a upgrade-stage-1 -m "GEO2 升级阶段 1 完成(P0 6 项,总分 35→40)"
4. 最后更新 docs/review/README.md 11 维度评分表（06: 1→3, 10: 3→3.5, 11: 2→3.5）

【应急】
如果读不到 4 份文档或 commit hash 对不上，立刻停下来报告，不要硬跑。
```

---

## ✅ 新会话读完 4 份文档后必须能回答

- [ ] 当前 GEO2 总分是多少？（35/55 B 级）
- [ ] 阶段 0+1 共几个 Task？（共 8 个：Task 0 + Task 1-6 + Task 7 门控）
- [ ] Task 0 的 4 个 step？（建目录 → 建占位 → 建 baseline_report.md → commit）
- [ ] P0 6 项的顺序？（1.evals/ → 2.AGENTS.md+CI → 3.反向依赖 → 4.schema → 5.重试 → 6.memory）
- [ ] 阶段 1 完成后预期分数？（35 → 40）
- [ ] 阶段 1 完成后打什么 tag？（upgrade-stage-1）
- [ ] 用户验收节奏？（本次不验收，阶段 2 后才验收）

---

## 🛟 应急方案

如果新会话没读到 4 份文档，发送：

```
请用 Read 工具读取以下 4 个文件，然后回报你的理解：
1. D:\GEO2\docs\superpowers\specs\2026-07-14-geo2-upgrade-design.md
2. D:\GEO2\docs\superpowers\plans\2026-07-14-geo2-upgrade-plan.md
3. D:\GEO2\docs\review\README.md
4. D:\GEO2\docs\review\99-improvement-plan.md
```

---

## 📤 会话 1 结束的交付物

- [ ] `backend/evals/` 目录 + 30 条评测集 + LLM-as-judge 框架
- [ ] `AGENTS.md`（GEO2 根目录仓库地图）
- [ ] `.github/workflows/ci.yml`（pytest + ruff + mypy）
- [ ] `backend/pyproject.toml` 新增 ruff/mypy 配置
- [ ] `backend/app/repositories/knowledge_repo.py` 修复反向依赖
- [ ] `backend/app/domain/agent/tools.py` 同步 generate_article schema
- [ ] `backend/app/domain/llm_client.py` max_retries=3 + 指数退避
- [ ] `backend/app/domain/agent/memory.py` 8 处 except Exception 收敛
- [ ] `backend/evals/baseline_report.md` 有真实数据
- [ ] `docs/review/README.md` 11 维度评分表更新
- [ ] tag `upgrade-stage-1` 已创建
- [ ] 7-8 个 commit（每个改进项独立一个）

---

## 🚀 下一步

会话 1 结束后，不要新开会话做阶段 2 验收（按设计决策，阶段 2 后才验收）。

直接新开会话 2，用 [`handoff-prompt-stage2.md`](./handoff-prompt-stage2.md) 模板。