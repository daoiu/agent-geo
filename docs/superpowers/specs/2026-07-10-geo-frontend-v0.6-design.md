# GEO 优化系统前端 v0.6 — 设计文档

| 项目 | 内容 |
|---|---|
| 版本 | v0.6（前端全面重设计） |
| 日期 | 2026-07-10 |
| 状态 | 设计已批，待实施 |
| 后端变更 | **无**（本次纯前端） |
| 依赖 | React 18.3 / TypeScript 5.7 / Tailwind 3.4 / React Router 6.28 / TanStack Query 5.62 / Recharts 2.15（沿用） |

---

## 1. Context

GEO 优化系统当前前端存在三个用户可见的体验问题：

1. **定位偏差**：品牌名为 "GEO 诊断 Agent"，主导航和首页（`/`）以"诊断"为中心，让产品看起来只是一个"诊断工具"，而 v0.5 已经覆盖了诊断 → 生成 → 发布 → 监测完整闭环，定位严重落后于产品能力。
2. **智能感缺失**：v0.4 的 Agent ReAct 推理、v0.5 的混合检索（关键词 + 向量 + RRF）、DiagnosisStatus 的多阶段流程——都是后端真实存在的能力，前端却只展示原始 JSON 和扁平进度条。用户感觉不到产品在"思考"。
3. **流程不清晰**：6 阶段优化路线（诊断 → 生成 → 审核 → 发布 → 监测 → 跟踪）没有任何全局视图；19 路由扁平铺开，用户无法定位自己处在流水线哪一阶段。

本次重设计目标是：把前端从"工具集"提升为"可视化的工作流操作系统"，让用户在第一次访问就能感知到产品定位、智能能力、和自己所处的优化阶段。

## 2. 品牌定位

| | 现在 | v0.6 |
|---|---|---|
| 品牌名 | "GEO 诊断 Agent" | "GEO 优化系统" |
| 一句话定位 | 一个诊断工具 | 一个 6 阶段 GEO 优化操作系统 |
| 核心视觉 | 文本标题，无标识 | 标识 + Logo（圆点脉冲图）+ 顶部 brand mark |
| 副标题 | 无 | "诊断 → 生成 → 发布 → 监测 · 全流程可视" |

## 3. 信息架构（IA）

### 3.1 Layout Shell

```
┌─────────────────────────────────────────────────────────────┐
│ TopBar: [Logo] GEO 优化系统                [🔔] [⚙] [👤]   │
├────────────┬──────────────────────────────┬─────────────────┤
│            │  Breadcrumb                  │  ContextPane    │
│ SideNav    │  ─────────────────           │  (per-page,     │
│ (主导航)   │  Page content                │   可选右栏)     │
│            │                              │                 │
├────────────┴──────────────────────────────┴─────────────────┤
│ PipelineRail (固定底栏 60px): 6 节点全局优化流水线          │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 路由重排

所有 19 个路由**保留 URL 兼容性**（避免 bookmark 失效）。前端组织成新 IA，同时通过 `react-router` `navigate` 重定向 + React Router `<Navigate>` 组件给出别名：

- `/` 在新 IA 中指向 **Dashboard**（而非旧的报告列表）；保留旧 `/` 行为于 `/history` 别名
- `/tasks/:id` 是任务详情；`/diagnoses/:id/status` 是诊断进度；其他路径类似
- API client（`src/api/client.ts`）的 endpoint 完全沿用，**前端不调用新 endpoint**

```
🏠 仪表盘                  /
🔍 诊断
   ├─ 新建诊断             /new
   ├─ 历史报告             /  (原 / 改 /history 别名)
   └─ 诊断智能体           /agent/diagnose (alias of /agent)

📚 知识库                  /knowledge (+ /knowledge/:kbId)

✍️ 生成
   ├─ 生成任务             /tasks
   ├─ 创建任务             /tasks/new
   └─ 审核队列             /reviews (+ /reviews/:articleId)

📤 发布
   ├─ 平台配置             /publishers
   └─ 发布历史             /publishes

📈 监测
   ├─ 品牌监测             /monitors (+ /monitors/:id)
   ├─ 新建监测             /monitors/new
   └─ 阈值通知             /notifications

🤖 智能助手               /agent (+ /agent/:sessionId)
⚙️  设置                  /settings  (consolidated, 新建)
```

迁移策略：旧 URL 重定向到新 IA 内的对应路径；侧边与顶部 PipelineRail 按当前上下文高亮。

### 3.3 PipelineRail（新增关键组件）

固定底栏，6 节点反映"全局优化流水线"：

```
诊断 ─●━●─ 生成 ─●━●─ 审核 ─○─ 发布 ─○─ 监测 ─○─ 跟踪
```

每个节点状态：
- `done`（已完成）：实心 + check 标
- `running`（进行中）：脉冲动画 + 实心 + active 蓝绿边
- `blocked`（有失败项待处理）：橙色实心 + 计数徽章（如 `失败 3`）
- `pending`（无活动）：空心灰

数据来源：聚合 `reports` / `tasks` / `reviews` / `publishes` / `monitors` 的最近一单状态。后端无需新增 API——前端通过 React Query 聚合现有 5 个查询即可。

行为：
- 任意节点点击 → 跳到该节点的 dashboard 子页
- 折叠：点 chevron 下沉到 28px 仅显示状态徽章
- mobile：底部改为顶部 Steppers 嵌入页面顶部

## 4. 设计系统地基

### 4.1 颜色 Tokens（CSS Variables + Tailwind bridge）

```css
/* :root, light mode only for v0.6 (dark mode 推 v0.7) */
:root {
  /* Brand */
  --color-primary:        #0D9488;   /* teal-600 */
  --color-primary-50:     #F0FDFA;
  --color-primary-100:    #CCFBF1;
  --color-primary-fg:     #FFFFFF;
  --color-secondary:      #14B8A6;
  --color-accent:         #EA580C;   /* orange-600 */
  --color-accent-fg:      #FFFFFF;

  /* Status */
  --color-success:        #10B981;
  --color-warning:        #F59E0B;
  --color-danger:         #DC2626;
  --color-info:           #0EA5E9;

  /* Surface */
  --color-bg:             #FFFFFF;
  --color-bg-subtle:      #F8FAFC;
  --color-bg-stage:       #ECFEFF;   /* for pipeline rail */
  --color-card:           #FFFFFF;
  --color-overlay:        rgba(15,23,42,0.4);

  /* Text */
  --color-fg:             #0F172A;
  --color-fg-muted:       #475569;
  --color-fg-dim:         #94A3B8;
  --color-fg-on-primary:  #FFFFFF;

  /* Border */
  --color-border:         #E2E8F0;
  --color-border-strong:  #CBD5E1;
  --color-ring:           #0D9488;

  /* Radius */
  --radius-sm: 6px;
  --radius:    10px;
  --radius-lg: 16px;
  --radius-pill: 9999px;

  /* Shadow */
  --shadow-card:     0 1px 3px rgba(15,23,42,0.06), 0 4px 12px rgba(15,23,42,0.04);
  --shadow-popover:  0 8px 32px rgba(15,23,42,0.12);
  --shadow-focus:    0 0 0 3px rgba(13,148,136,0.35);
}
```

Tailwind config 同步扩展（`theme.extend.colors` 指向 CSS 变量），保证 tailwind-merge 仍生效。

### 4.2 Typography

- Font: **Inter** (400/500/600/700)
- CJK fallback: `PingFang SC, Microsoft YaHei, sans-serif`
- 字号刻度：`text-xs 12 / sm 14 / base 16 / lg 18 / xl 20 / 2xl 24 / 3xl 30 / 4xl 36`
- 行高：紧凑 `1.2`（标题）/ 舒适 `1.5`（正文）
- Tailwind config: `fontFamily.sans = ['Inter', 'PingFang SC', 'Microsoft YaHei', 'sans-serif']`

### 4.3 Logo 与 Brand Mark

- SVG（viewBox 24x24，stroke 1.5）：中心实心圆 + 6 个围绕脉冲点 + 1 个扩散波纹
- 颜色用 `--color-primary`；accent 圆点用 `--color-accent`
- 顶部 TopBar 渲染：`<Logo /> GEO 优化系统`

### 4.4 公共组件库（新增，集中 `src/components/ui/`）

| 组件 | 用途 | 替换现有 |
|---|---|---|
| `Button` | 全局按钮 primary/secondary/ghost/danger | 所有内联 Tailwind `<button>` |
| `Input / Select / Textarea` | 表单控件（统一焦点环 + 错误态） | 所有裸 `<input>` |
| `Card / CardHeader / CardBody / CardFooter` | 卡片容器 | 裸 `<div className="bg-white rounded shadow ...">` |
| `Badge` | 状态徽章 | 散见绿/红圆点 |
| `Modal / Drawer / ConfirmDialog` | 弹层 | 现有 `ConfirmDialog.tsx` 重写 |
| `Spinner / Skeleton / EmptyState` | 加载/空态 | 散见 spinner 文字 |
| `Tooltip / Tabs / Accordion` | 通用交互 | — |
| `Stepper` | 步进器（垂直/水平） | `WizardShell` 内嵌步骤条抽离 |
| `PipelineRail` | 6 节点全局流水线底栏 | — |
| `StageCard` | 单阶段进度卡 | `DiagnosisStatus` 内 step 状态重写 |
| `LiveSignal` | 实时信号点 | 单元素状态展示 |
| `MentionMatrix` | 品牌 × 问题矩阵（热力图） | 散见提及标签 |
| `ReasoningTrace` | Agent ReAct 推理流可视化 | `AgentChat` 内 ToolCallCard 升级 |
| `KnowledgeChunkCard` | 知识 chunk 卡片（v0.5 hybrid 分数） | KB 详情内 inline 列表 |
| `RankBadge` | 排名 / 提及位置徽章（金银铜） | 散见提及文本 |

## 5. 流程可视化组件（新增）

### 5.1 PipelineRail（已在 §3.3 说明）

### 5.2 StageCard

```tsx
<StageCard
  icon={<SpiderIcon />}
  title="爬虫抓取"
  status="done"
  meta="12 个页面 · 8.2s · 无错误"
  progress={100}
  duration="8.2s"
/>
```

用于 DiagnosisStatus / TaskDetail 等多阶段页面，每阶段一张卡，按时间排序横排或垂直串接。

### 5.3 MentionMatrix（v0.5 的 hybrid 结果可视化）

热力图：行 = 品牌（含竞品 N 个），列 = 问题（用户 + 系统），单元格 = 提及强度（位置越靠前越饱和）。

辅助行：情感图标（+/○/-/✗）；辅助列：provider 结果（DeepSeek / Kimi 各一列）

数据来源：`MentionResult[]` 已经在 backend（v0.1 `query_mentions`），前端把矩阵渲染出来即可，不需要改后端。

### 5.4 ReasoningTrace（agent 智能感最大落地）

把 AgentChat 当前 SSE 事件序列（`tool_call_start` / `tool_call_result` / `human_confirmation_required` / final text）映射成一个可视化时间线：

```
11:32:01 [思考] 我会先问 3 个 LLM 关于小米定位
   └─ 🔧 search_knowledge("小米 GEO 策略")
      ✓ 找到 5 段引用 · RRF 综合分 0.84
   └─ 🌐 DeepSeek ●●○
   └─ 🌐 Kimi     ●●●
11:32:04 [回答] 小米在 GEO 中等偏上…
   ⚠ 需要确认: 是否基于此生成 5 篇内容?
```

实现：左侧消息流 + 右侧 ReasoningTrace 面板（sticky on desktop, collapsible on mobile）。

### 5.5 KnowledgeChunkCard（v0.5 升级曝光）

每个 chunk 显示：
- 标题（来自 KB chunk）
- 摘要（首 80 字）
- 来源页 + KB 名称
- **hybrid 检索分数**（0–1，圆点进度）
- "在 X 个文章中被引用"

### 5.6 RankBadge

`#1 / #2 / #3+` 金银铜配色徽章，用于报告页的提及位置 + 监测趋势的排名变化。

## 6. 每页重设计要点

| 路径 | 标题 | 改造要点 |
|---|---|---|
| `/` | 仪表盘 | 顶部 4 张大卡：当前品牌 GEO 评分（带 sparkline）/ 进行中任务摘要 / 待审核数 / 最近提及趋势；底部"开始一次优化"主 CTA + 最近活动 feed |
| `/new` | 新建诊断 | 用 Stepper 替换 WizardShell；4 步：品牌 → 问题 → LLM 配置 → 启动；启动按钮橙色 CTA |
| `/diagnosis/:id/status` | 诊断进度 | **重头**：6 步 pipeline（爬虫→问题生成→LLM 询问→打分→聚合→报告）；每步 StageCard 实时更新；LLM provider 实时信号；可中途取消 |
| `/reports/:id` | 诊断报告 | 顶部评分卡 + 5 维雷达（沿用 ScoreRadarChart）+ MentionMatrix + 位置 + 情感表 + 主 CTA"基于此报告生成内容" |
| `/knowledge` | 知识库 | KB 卡片网格；按行业筛选；空态引导上传 |
| `/knowledge/:id` | KB 详情 | 文档列表 + KnowledgeChunkCard 网格；hybrid 检索测试入口 |
| `/tasks` | 生成任务 | 表格 + 进度条 + 阶段标签；右上"创建任务" CTA |
| `/tasks/new` | 新建任务 | 4 步：选 KB → 主题/关键词 → 风格 → 启动 |
| `/tasks/:id` | 任务详情 | **重头**：4 步生成管道（选 chunk → 大纲 → 撰写 → 自审）+ 文章列表用 ArticleCard；批量通过/拒绝 |
| `/reviews` | 审核队列 | 文章卡片含 frontmatter、字数、引用 chunk 数、AI 自审评分 |
| `/reviews/:id` | 单篇审核 | 左：原文（可编辑） / 右：引用 chunks（可点击跳转原文）；diff（原文 vs 修订）；通过/拒绝/编辑/请求 Agent 改写 |
| `/publishers` | 平台配置 | 平台卡片网格（新增/编辑/删除/启用） |
| `/publishes` | 发布历史 | 时间线 + 状态徽章 + 失败原因 |
| `/monitors` | 监测列表 | 品牌监测卡片 + 趋势缩略图 |
| `/monitors/new` | 新建监测 | 3 步：品牌 → 问题频率 → 通知策略 |
| `/monitors/:id` | 监测详情 | **重头**：大趋势图（recharts 加强）+ MentionMatrix + provider 分项 + 情感 + 阈值事件 |
| `/notifications` | 通知 | SMTP 配置 + 默认阈值 + 历史通知列表 |
| `/agent` | 会话列表 | session 卡片网格 + 右上"新会话" |
| `/agent/:id` | Agent Chat | **重头（智能感最大落地）**：左会话 / 中消息 / 右 ReasoningTrace；Human-in-loop 弹 ConfirmModal |
| `/settings` | 设置（新增） | 收纳 LLM 配置、API 状态、SSRF 模式、版本、退出 |

## 7. 错误 / 加载 / 空态

- **错误**：统一 `<ErrorCard onRetry={fn} />` — 卡片化 + 重试按钮 + 折叠详细 stack
- **加载**：Skeleton 列表 + 嵌入按钮 spinner；数据获取用 TanStack `isLoading` 统一
- **空态**：插画（一句话 SVG）+ 解释 + 当前页面专属 CTA（例如 `/tasks` 空："还没生成过内容，先建一个任务" → CTA)

## 8. 响应式 + A11y

- 断点：sm 640 / md 768 / lg 1024 / xl 1280 / 2xl 1536
- 侧边在 < md 折叠为汉堡菜单
- PipelineRail 在 < md 折叠为顶部 Stepper
- 焦点环统一 `--shadow-focus`
- 全交互 `aria-label` / `role` 完整
- 颜色满足 WCAG AA（primary fg #FFF vs primary #0D9488 = 4.78:1）
- 尊重 `prefers-reduced-motion`（关闭脉冲、聚合动画）

## 9. 测试策略

- **单元**：新增 `components/ui/` 每个组件有 `.test.tsx`（用 Vitest + RTL，沿用 `test:id`）
- **e2e（已有 Playwright）**：每页重要路径 1 个用例 + 1 个可视快照用例（snapshot 模式比对）
- **可访问性**：加入 `@axe-core/playwright`，每个 e2e 自动跑 a11y
- **视觉回归**：Playwright `expect(page).toHaveScreenshot()`，关键页 1 张

## 10. 实施分阶段

为了避免 19 页一次性大爆炸的不可控风险，按"设计基底 + 关键页先发"分 5 phase，每 phase 1 个 PR：

| Phase | 内容 | 文件数（估） | 演示效果 |
|---|---|---|---|
| **P0** | 设计令牌 + Layout shell（TopBar / SideNav / PipelineRail / Breadcrumb）+ 公共组件库（15 个） | 20-25 | 空壳但完整 shell，所有路由仍可走 |
| **P1** | `/` 仪表盘 + `/new` + `/diagnosis/:id/status` + `/reports/:id` | 4-6 | "诊断流程"完整可视 |
| **P2** | `/agent/:id` + `/agent` | 2 | 智能感最强烈落地 |
| **P3** | 知识库 + 生成任务链路（5 个：knowledge × 2, tasks × 3） | 5-7 | 内容生成管线可视 |
| **P4** | 监测 + 发布 + 通知 + 历史 + 设置 | 7-9 | 完整闭环可视 |
| **P5** | 视觉回归 + a11y 收尾 | 2-3 | 可访问 + 稳定 |

每个 phase 结束后：
- 后端不动 → 可独立合并到 main
- 可独立 demo 给用户看
- 若发现某 phase 设计不优，可调整后续 phase 而不影响已交付

## 11. 风险与回退

| 风险 | 应对 |
|---|---|
| 19 路由全重工作量大 | P0-P5 分阶段；每阶段后端零变更；早期可"仅 P0 + P1"上线剩余渐进 |
| 公共组件 API 改动影响现有 e2e | 用 `data-testid` 兜底；保留 e2e 中的关键 role / label |
| 颜色 flicker / 主题残留 | 一律 token 化，无硬编码颜色；tailwind config + CSS var 桥接 |
| dark mode 复杂度 | **v0.6 仅 light mode**；dark 推 v0.7（在 tokens 留好接口） |
| PipelineRail 数据聚合失误 | 5 个 React Query 独立 error 边界；任一失败 → 该节点显示 `?` 不阻断整栏 |
| ReasoningTrace 节点爆炸 | 折叠同工具连续调用为 1 行；超过 50 条折叠为 "..." + 视图切换 |
| Inter 字体加载延迟 | `font-display: swap`；fallback 到系统字体（PingFang/Microsoft YaHei） |

## 12. 验证（Verification）

每个 phase 完成后必须通过：

1. **本地**：`pnpm dev` → 浏览器访问相关路由
2. **`pnpm lint`**：tsc 通过
3. **`pnpm test:e2e`**：相关 e2e 通过 + 新增快照测试
4. **A11y**：相关页面 `@axe-core/playwright` 通过
5. **可视对比**：截图新页面与本 spec 第 6 节要点比对

整体完成需：
- 19 个路由全部重写
- 15 个公共组件 + 5 个流程组件完整
- 1 个 PipelineRail 全局底栏
- A11y / 视觉回归 / 性能（LCP < 2s）达标

## 13. 不做（Out of Scope）

- 后端任何变更（包括新增 endpoint / 修改响应字段）
- v0.6 内的 dark mode（接口预留但不发）
- 多语言 / i18n（v0.6 仅中文，与现状一致）
- 移动 app / PWA
- 用户系统 / 鉴权 / 多租户（v1.0+）
- 流式 LLM 输出（v0.4 已经 SSE 但 assistant 文本是一次性；这次也不动）

## 14. 关键文件清单（粗略）

```
frontend/
├── tailwind.config.js                    # +extend colors / fontFamily / boxShadow
├── index.html                            # +Inter link
├── src/
│   ├── main.tsx                          # 不变
│   ├── App.tsx                           # 改为 LayoutShell + 新 routes
│   ├── index.css                         # 加 :root tokens / Inter import / base reset
│   ├── components/
│   │   ├── ui/                           # 新增目录：15 个公共组件
│   │   ├── layout/
│   │   │   ├── TopBar.tsx                # 新
│   │   │   ├── SideNav.tsx               # 新
│   │   │   ├── Breadcrumb.tsx            # 新
│   │   │   ├── PipelineRail.tsx          # 新（全局底栏）
│   │   │   ├── ContextPane.tsx           # 新（可选右栏）
│   │   │   └── LayoutShell.tsx           # 新（组合上面）
│   │   ├── ScoreRadarChart.tsx           # 沿用
│   │   ├── TrendChart.tsx                # 沿用
│   │   ├── SuggestionCard.tsx            # 重写（用新 tokens）
│   │   ├── ToolCallCard.tsx              # 升级为 ReasoningTrace 子组件
│   │   ├── ConfirmDialog.tsx             # 重写（基于 ui/Modal）
│   │   ├── ChatMessage.tsx               # 不变
│   │   └── WizardShell.tsx               # 重写为 ui/Stepper 用法
│   ├── pages/
│   │   ├── Dashboard.tsx                 # 新（替换 ReportList 的角色）
│   │   ├── NewDiagnosis.tsx              # 重写（Stepper）
│   │   ├── DiagnosisStatus.tsx           # 重写（StageCard + LiveSignal）
│   │   ├── ReportView.tsx                # 重写（MentionMatrix + RankBadge）
│   │   ├── ReportList.tsx                # 重命名 → History.tsx
│   │   ├── KnowledgeList.tsx             # 重写
│   │   ├── KnowledgeDetail.tsx           # 重写（KnowledgeChunkCard）
│   │   ├── TaskList.tsx                  # 重写
│   │   ├── NewTask.tsx                   # 重写
│   │   ├── TaskDetail.tsx                # 重写（4 步管线）
│   │   ├── ReviewQueue.tsx               # 重写
│   │   ├── ReviewArticle.tsx             # 重写
│   │   ├── PublisherConfig.tsx           # 重写
│   │   ├── PublishList.tsx               # 重写
│   │   ├── MonitorList.tsx               # 重写
│   │   ├── NewMonitor.tsx                # 重写
│   │   ├── MonitorDetail.tsx             # 重写（强 MentionMatrix + 趋势加强）
│   │   ├── NotificationSettings.tsx      # 重写
│   │   ├── AgentSessionList.tsx          # 重写为 Dashboard /agent
│   │   ├── AgentChat.tsx                 # 重写（ReasoningTrace 主区右栏）
│   │   └── Settings.tsx                  # 新建
│   ├── api/client.ts                     # 不动
│   ├── lib/utils.ts                      # +cn, formatDate, scoreColor, fraction helper
│   ├── types/                            # 不动（已表达 MentionResult 等）
│   └── tests/
│       ├── components/                   # 新增（每个 ui/ 组件 1 文件）
│       └── e2e/                          # +新页面 e2e
└── docs/
    └── DESIGN.md                         # 新增（设计 tokens 速查）
```

## 15. 决策日志

| 决策 | 选项 | 选择 | 理由 |
|---|---|---|---|
| 重构深度 | agent-only / 诊断+生成 / 全面 | 全面 | 用户决策 |
| 视觉语言 | 企业 / AI-native / 温暖生产力 | 温暖生产力 | 用户决策（teal + orange） |
| 信息架构 | 不变 / 侧边+面包屑 / 首页中心 | 侧边+面包屑 | 用户决策 |
| Dark mode | 做 / 不做 | 不做（推 v0.7） | 降风险 |
| 字体 | 系统 / Plus Jakarta / Inter | Inter（Tailwind 默认友好） | 兼容中英文、易加载 |
| 实施分阶段 | 一次 / 5 阶段 | 5 阶段 | 19 页一次性风险高 |
| 公共组件库 | Radix / 自写 | 自写（轻量） | 避免新增依赖 |
| 流程图样式 | 进度条 / 阶段卡 / Sankey | 阶段卡（StageCard） | 与"流程清晰"目标最匹配 |
| Logo | 文字 / 极简 SVG | 极简 SVG | 品牌感 |
