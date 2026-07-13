# GEO2 全面升级 — 会话交接 Prompt 索引

> 本目录包含 GEO2 全面升级项目的 3 个会话开局模板。每个会话开始时，复制对应模板到新会话的第一条消息即可。

---

## 🎯 三阶段会话分工

| 会话 | 模板 | 覆盖范围 | 估时 | 完成后状态 | 是否验收 |
| --- | --- | --- | --- | --- | --- |
| **会话 1** | [`handoff-prompt-stage1.md`](./handoff-prompt-stage1.md) | 阶段 0+1：基线 + P0 6 项 | 7-8d | 35 → 40 分，打 `upgrade-stage-1` | ❌ 不验收 |
| **会话 2** | [`handoff-prompt-stage2.md`](./handoff-prompt-stage2.md) | 阶段 2：P1 核心 20 项 | 20d | 40 → 47.5 分 A 级，打 `upgrade-stage-2` | ✅ **用户验收** |
| **会话 3** | [`handoff-prompt-stage3.md`](./handoff-prompt-stage3.md) | 阶段 3+4：P1 剩余 8 + P2 25 | 65d | 47.5 → 50+ 分卓越级，打 `upgrade-stage-3` + `upgrade-stage-4` | ✅ **最终验收** |

---

## 📋 怎么用

### 当前是会话 0（已完成）

- ✅ 完成锐评（35/55 B 级）
- ✅ 写出 spec + plan + handoff prompt 模板
- ✅ 全部 commit + 打 tag

### 下一步：会话 1

1. 开新 Claude Code 会话
2. 打开 [`handoff-prompt-stage1.md`](./handoff-prompt-stage1.md)
3. **复制"📋 直接复制粘贴下面整段到新会话"下面的整段**
4. 粘贴到新会话第一条消息
5. 等新会话读完 4 份文档，回报起点状态 + 当前 Task 列表
6. 确认无误，新会话从 Task 0 开始执行
7. 完成后**不等验收**，直接结束会话

### 然后：会话 2

1. 等会话 1 完成（7-8d 后）
2. 开新会话，用 [`handoff-prompt-stage2.md`](./handoff-prompt-stage2.md) 模板
3. 注意：会话 2 完成后**触发用户验收**（这是设计内的 checkpoint）

### 最后：会话 3

1. 等会话 2 用户验收通过
2. 开新会话，用 [`handoff-prompt-stage3.md`](./handoff-prompt-stage3.md) 模板
3. 阶段 3 完成不验收，直接进阶段 4
4. 阶段 4 完成后**最终验收**

---

## 🔗 上下游文档依赖

```
会话 1 必读：
  - 2026-07-14-geo2-upgrade-design.md （spec）
  - 2026-07-14-geo2-upgrade-plan.md    （plan）
  - review/README.md                     （35/55 B 级起点）
  - review/99-improvement-plan.md        （55 项清单）

会话 2 必读：
  - 同上 + backend/evals/baseline_report.md （阶段 1 留下的基线）

会话 3 必读：
  - 同上 + tech-debt-tracker.md （阶段 2 留下的债项）
```

---

## 🛟 信息丢失应急

如果新会话没读到上述文档：

```
请用 Read 工具读取 D:\GEO2\docs\superpowers\handoff-prompts-index.md，
按指引读取必读文档，然后回报你的理解。
```

如果新会话上下文超限（>1M tokens）：

```
保存进度到 docs/superpowers/sessionN-progress.md，
打 sessionN-interrupted tag，
然后开新会话用下一个模板继续。
```

---

## 📊 进度追踪

每个阶段完成时，更新本表的实际状态：

| 阶段 | 计划 | 实际 | 完成日期 | tag |
| --- | --- | --- | --- | --- |
| 0+1 | 7-8d | ⏳ | — | upgrade-stage-1 |
| 2 | 20d | ⏳ | — | upgrade-stage-2 |
| 3 | 10d | ⏳ | — | upgrade-stage-3 |
| 4 | 55d | ⏳ | — | upgrade-stage-4 |

更新时机：每个 tag 创建后立刻填本表。

---

## 🎁 额外资源

- 锐评主页：[`../review/README.md`](../review/README.md)
- 升级 spec：[`2026-07-14-geo2-upgrade-design.md`](./2026-07-14-geo2-upgrade-design.md)
- 升级 plan：[`2026-07-14-geo2-upgrade-plan.md`](./2026-07-14-geo2-upgrade-plan.md)
- 锐评 spec：[`2026-07-14-geo2-quality-review-design.md`](./2026-07-14-geo2-quality-review-design.md)
- 锐评 plan：[`2026-07-14-geo2-quality-review-plan.md`](./2026-07-14-geo2-quality-review-plan.md)
- 55 项改进清单：[`../review/99-improvement-plan.md`](../review/99-improvement-plan.md)

---

## 💡 最佳实践

1. **每会话开始先读模板，必读文档读完再动手**
2. **每项改进独立 commit，便于审查与回滚**
3. **每阶段完成打 tag + 更新 review/README.md 11 维度评分表**
4. **阶段 2 完成用户验收后再开阶段 3+4 会话**
5. **应急方案在每个模板的"🛟 应急方案"小节**