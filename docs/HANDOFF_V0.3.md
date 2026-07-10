# v0.3 实施启动话术

> **新会话复制下面整段即可启动 v0.3 实施**

---

```
按 D:/GEO2/docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.3.md
实施 GEO Agent v0.3（~21 个 task：WordPress 发布 + 监测 + 趋势图 + 邮件通知）。

前置条件：v0.1 + v0.2 代码已存在并测试通过。

流程：
1. 调 superpowers:using-superpowers skill
2. 读 plan + specs/2026-07-10-geo-agent-v0.3-design.md
3. 报告读完，问执行方式（subagent-driven / inline）
4. 简体中文回复，Conventional Commits，TDD 严格

约束：
- 复用 v0.1 的 LLMClient / v0.2 的 KnowledgeRepository / 共享 _EXEC_LOCK
- 不引入 Redis / Celery（用 APScheduler 单进程）
- 发布平台只 WordPress（公众号推到 v0.4+）
- 监测任务用户独立创建（与发布解耦）
- 通知渠道只邮件（Slack / 企业微信推到 v0.4+）
- APScheduler 嵌在 FastAPI lifespan 里
- 启动时从 DB 恢复监测调度
- 加密：Fernet 存 WordPress app_password
```

---

## 关键文件

| 文件 | 路径 | 用途 |
|---|---|---|
| 设计文档 | `docs/superpowers/specs/2026-07-10-geo-agent-v0.3-design.md` | v0.3 做什么 + 为什么 |
| 实施计划 | `docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.3.md` | ~21 个 task 的 TDD 步骤 |
| 手动清单 | `docs/MANUAL_VERIFICATION_V0.3.md` | 发布前必跑 11 个场景 |

## 关键决策摘要

- **范围**：WordPress 发布（只此一家）+ AI 答案监测 + 趋势图 + 邮件通知
- **调度**：APScheduler（单进程内），startup 时从 DB 加载 active 任务
- **通知**：SMTP（aiosmtplib），失败静默（不阻断监测）
- **写类操作**：发未审核文章 → 422
- **凭证管理**：app_password 用 Fernet 加密后存 DB，**API 响应永不含 app_password**
- **发布状态机**：pending → running → success / failed / cancelled

## 实施注意事项

- **Phase 0 任务 0.2 (ORM)**：4 张新表（publisher_configs / publish_jobs / monitor_tasks / mention_snapshots）
- **Phase 0 任务 0.3 (加密)**：Fernet 必须从 `ENCRYPTION_KEY` 读取，启动时检查，**缺失则启动失败**
- **Phase 1 WordPress 客户端**：用 `httpx` + Basic Auth + Application Password；4xx 错误映射到 `PublishError` 子类
- **Phase 1 Repository**：注意 `ON DELETE RESTRICT` 防止删除有 publish_job 的凭证
- **Phase 2 调度器**：`schedule_monitor_task` / `unschedule_monitor_task` / `load_all_monitor_tasks` 三个核心函数
- **Phase 3 Service**：单次监测执行 = 调 v0.1 LLMClient + jieba 关键词 + 算 mention_rate + 写 snapshot
- **Phase 4 通知**：触发点 2 个（发布成功 / 监测变化），失败不阻断主流程
- **Phase 5 API**：SSE 不需要（v0.3 用普通 REST），但 v0.4 SSE 会复用 main.py 结构
- **Phase 5 main.py lifespan**：必须先 `init_db()` → `start_scheduler()` → `load_all_monitor_tasks()`，顺序重要
- **Phase 6 前端**：7 个新页面，最复杂是 `MonitorDetail`（含 Recharts 趋势图）

## 不要做的事

- ❌ 引入 Redis / Celery（保持单进程）
- ❌ 微信公众号发布（推到 v0.4+）
- ❌ Slack / 企业微信 / 钉钉通知（只邮件）
- ❌ 向量检索（推到 v0.5）
- ❌ 多用户 / 鉴权 / 团队（推到 v1.0）
- ❌ Playwright SPA 渲染（推到 v0.6）
- ❌ 自动重试失败发布（用户手动重试）
- ❌ API 限额（保持无限）

## 测试重点

- WordPress 错误映射（401/403/404）
- 发布状态机
- 监测阈值判断
- 启动恢复（DB → scheduler）
- 通知失败不阻断
