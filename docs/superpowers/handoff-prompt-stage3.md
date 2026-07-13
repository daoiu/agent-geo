# 会话 3 开局模板 — 阶段 3+4（P1 剩余 8 + P2 卓越化 25）

> **用途**：阶段 2 验收通过后启动 GEO2 全面升级的**第三次会话**。
> **覆盖范围**：阶段 3（P1 剩余 8 项）+ 阶段 4（P2 25 项）= 65d 工作量。
> **完成后预期**：49 → 50+ 分（卓越级），打 `upgrade-stage-3` + `upgrade-stage-4` 两个 tag，**最终验收**。

---

## 📋 直接复制粘贴下面整段到新会话

```
我要继续执行 GEO2 全面升级阶段 3+4（P1 剩余 8 项 + P2 卓越化 25 项，Task 28-55）。
请按以下顺序读取上下文：

【必读 6 份】
1. D:\GEO2\docs\superpowers\specs\2026-07-14-geo2-upgrade-design.md（升级设计 spec）
2. D:\GEO2\docs\superpowers\plans\2026-07-14-geo2-upgrade-plan.md（实施 plan，阶段 3/4 在末尾章节）
3. D:\GEO2\docs\review\README.md（**已更新到 47.5/55 分 A 级**，11 维度评分表）
4. D:\GEO2\docs\review\99-improvement-plan.md（55 项改进清单，重点 P1 剩余 8 + P2 25）
5. D:\GEO2\backend\evals\baseline_report.md + 最新对比报告（阶段 2 留下）
6. D:\GEO2\docs\tech-debt-tracker.md（阶段 2 留下的首批条目）

【继承决策】
- 升级范围：阶段 3+4（本会话）
- **验收节奏：阶段 4 完成后最终验收。本次阶段 3 完成不验收，直接进阶段 4**
- 执行隔离：main 直接，阶段 3 打 upgrade-stage-3，阶段 4 打 upgrade-stage-4
- 执行模式：Inline Execution
- 语言：简体中文

【起点状态】
- 当前总分：47.5/55 A 级（阶段 2 验收后）
- 当前分支：main
- 当前 tags：review-2026-07-14, geo2-upgrade-spec-2026-07-14, upgrade-stage-1, **upgrade-stage-2**（新）
- 阶段 2 新增：Sentry/Langfuse 接通, import-linter, trace_id, Providers 抽象, 20 项 P1
- baseline：阶段 2 复跑后 pass rate 已提升 ≥10%

【本次会话任务（按顺序）】
A. 阶段 3（8 项 P1 剩余，10d）：
  - Task 28: 评测集与 CI 集成（0.5d）
  - Task 29: 人评抽样机制（1d）
  - Task 30: 评测可视化面板（2d）
  - Task 31: Prometheus 指标导出（2d）
  - Task 32: HITL 多场景（决策/补充输入/进度确认）（5d）
  - Task 33: HITL 端到端测试（1d）
  - Task 34: 多类 HITL 事件 schema（1d）
  - Task 35: 慢查询 dashboard（0.5d）
  阶段 3 完成后打 upgrade-stage-3 tag（**不验收**）

B. 阶段 4（25 项 P2 卓越化，55d）：
  按 99-improvement-plan.md P2 部分顺序执行。重点项：
  - Task 36: 自适应模型选择（5d）
  - Task 37: Fallback 策略（主 provider 失败切备用）（3d）
  - Task 38: 用户偏好学习（3d）
  - Task 39: 月度成本 dashboard（3d）
  - Task 40: 故障注入工具（1d）
  - Task 41: 显式 replay API（2d）
  - Task 42: 移除 noqa: BLE001 宽泛捕获（1d）
  - Task 43: 工具注册表收拢（1d）
  - Task 44: 截断决策可解释（1d）
  - Task 45: 自适应压缩（3d）
  - Task 46: token 上限硬限制（0.5d）
  - Task 47: 自动拒绝超时（0.5d）
  - Task 48: 权限操作审计日志独立表（1d）
  - Task 49: CORS 生产严格化（0.5d）
  - Task 50: 评测可视化（baseline vs 当前版本对比）（2d）
  - Task 51: 定期后台 agent 扫描代码偏差（5d）
  - Task 52: 自动重构 PR 流程（5d）
  - Task 53: ORM 版本迁移脚本（v02→v03→v04）（5d）
  - Task 54: API 层加 auth 依赖（2d）
  - Task 55: 熵管理自动化（5d）
  （如时间紧，按 ROI 挑做，至少完成前 10 项）

  阶段 4 完成后打 upgrade-stage-4 tag（**最终验收**）

【TDD 原则（继承）】
- Task 28（评测 CI 集成）：先在 .github/workflows/ci.yml 加 eval 步骤，用 OPENAI_API_KEY secret 保护
- Task 32（多类 HITL）：先扩 HumanConfirmation 异常为基类，新增 DecisionRequired / InputRequired / ProgressConfirm 等子类
- Task 36（自适应模型）：先在 Settings 加模型分级配置 + 任务分级接口
- Task 53（ORM 迁移）：先写迁移脚本模板 + 测试 DB

【验证门控（阶段 4 完成时）】
- [ ] 8 项 P1 剩余 + ≥ 10 项 P2 全部 commit（至少完成阶段 4 前 10 项）
- [ ] 总分 ≥ 50/55（卓越级）
- [ ] 11 维度评分全部 ≥ 4.5（无短板）
- [ ] 540 原有 + 200+ 新增测试全部通过
- [ ] baseline 复跑，pass rate 提升 ≥ 25%
- [ ] GitHub Actions CI 全绿（pytest + ruff + mypy + import-linter + evals）
- [ ] docs/review/README.md 11 维度评分表最终更新
- [ ] docs/tech-debt-tracker.md 已更新（剩余债项列表）
- [ ] 两个 tag 已创建：upgrade-stage-3 + upgrade-stage-4

【执行要求】
1. 读完 6 份文档后先回报"起点状态确认 + 当前 Task 列表"，等我确认无误
2. 每项 commit 格式：docs|feat|fix|refactor|test|chore: <一句话>
3. **阶段 3 完成后不停**，直接进阶段 4（本会话连续做）
4. 阶段 4 完成后：更新 docs/review/README.md + 写最终总结到 docs/UPGRADE_SUMMARY.md

【应急】
如果上下文超过限制（>1M tokens）：立刻保存当前进度到 docs/superpowers/session3-progress.md，
然后开会话 4 用 handoff-prompt-stage4.md 继续剩余 P2。
如果某些 P2 项需要外部资源（如 ORM 迁移需要真实生产 DB）：标记为"未来工作"，在 tech-debt-tracker.md 留条目。
```

---

## ✅ 新会话读完 6 份文档后必须能回答

- [ ] 阶段 3+4 共多少 Task？（共 33 个：8 P1 剩余 + 25 P2）
- [ ] 阶段 3 完成后预期分数？（47.5 → 49）
- [ ] 阶段 4 完成后预期分数？（49 → 50+ 卓越级）
- [ ] 当前 11 维度评分表状态？（见 docs/review/README.md §2）
- [ ] 哪些 P2 项是 ROI 最高的？（Task 36 自适应模型、Task 41 replay API、Task 50 评测可视化）
- [ ] 阶段 3 完成打什么 tag？阶段 4 完成打什么 tag？（upgrade-stage-3, upgrade-stage-4）
- [ ] 本次是否验收？（**阶段 3 不验收，阶段 4 最终验收**）

---

## 🛟 应急方案

### 应急 1：上下文超限

如果跑着跑着提示 context 超限，立刻：

```bash
# 保存进度
cat > docs/superpowers/session3-progress.md << EOF
# 会话 3 中断点（YYYY-MM-DD HH:MM）
- 已完成：Task 28-XX
- 下次从：Task XX 开始
- 备注：<任何未完成状态>
EOF
git add docs/superpowers/session3-progress.md
git commit -m "docs: 会话 3 中断点记录"
git tag -a session3-interrupted -m "会话 3 中断点"
```

然后开**会话 4**，用类似模板继续。

### 应急 2：外部资源缺失

如果某些 P2 项需要：

- 真实生产 DB（ORM 迁移）
- Sentry/Langfuse paid tier（高级功能）
- 用户研究数据（用户偏好学习）

标记为"未来工作"，在 tech-debt-tracker.md 留条目，不阻塞 commit。

### 应急 3：P2 数量过多跑不完

按 ROI 排序只做前 10 项（最高 ROI）：

- Task 36 自适应模型（5d）
- Task 37 Fallback 策略（3d）
- Task 41 显式 replay API（2d）
- Task 44 截断决策可解释（1d）
- Task 49 CORS 生产严格化（0.5d）
- Task 36-50 中其他简单项

剩余 P2 在 tech-debt-tracker.md 标记为"已识别，待后续 sprint"。

---

## 📤 会话 3 结束的交付物

### 阶段 3（8 项 P1 剩余）

- [ ] 8 个 Task 全部 commit
- [ ] 评测 CI 化 + 人评机制 + 可视化面板就位
- [ ] Prometheus 导出
- [ ] HITL 多场景（决策/补充输入/进度确认）
- [ ] tag `upgrade-stage-3` 已创建

### 阶段 4（≥ 10 项 P2）

- [ ] ≥ 10 个 Task commit（按 ROI 排序）
- [ ] 总分 ≥ 50/55（卓越级）
- [ ] 11 维度评分全部 ≥ 4.5
- [ ] tag `upgrade-stage-4` 已创建
- [ ] `docs/UPGRADE_SUMMARY.md` 最终总结（4 阶段全景）
- [ ] `docs/tech-debt-tracker.md` 已更新（剩余债项）

---

## 🎯 最终验收清单（用户做）

用户验收以下内容后，整个 GEO2 全面升级项目**正式结项**：

1. **4 阶段全景**：从 35 → 50+ 分的演进路径是否合理
2. **commit 总数**：约 50 个（Task 0-55），每个独立可回滚
3. **tag 完整性**：review-2026-07-14 + geo2-upgrade-spec-2026-07-14 + upgrade-stage-1/2/3/4 共 5 个
4. **测试覆盖**：540 + 200+ ≈ 740 测试通过
5. **CI 全绿**：GitHub Actions 5 步全过（pytest + ruff + mypy + import-linter + evals）
6. **文档完整**：AGENTS.md + review/README.md + UPGRADE_SUMMARY.md + tech-debt-tracker.md + 14 锐评 + 4 spec/plan
7. **性能提升**：baseline pass rate 提升 ≥ 25%
8. **生产就绪**：所有 11 维度达到"良好"或"卓越"

验收通过后，GEO2 从 B 级项目升级为 A 级项目，可作为面试的**亮点项目**。

---

## 🚀 项目结项

会话 3 完成后，整个 GEO2 全面升级项目正式结项。

如需后续优化（剩余 P2、技术债清理、Harness 自动化），开新会话读 `docs/tech-debt-tracker.md` + `docs/UPGRADE_SUMMARY.md` 继续。