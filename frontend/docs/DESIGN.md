# GEO 优化系统前端 — 设计系统速查

> v0.6 P0 设计基础。本文档随 Phase 推进持续更新。

## 1. 颜色 Tokens

| Role | Hex | Tailwind class | CSS var |
|---|---|---|---|
| 主色 brand primary | `#0D9488` | `bg-primary` / `text-primary` | `--color-primary` |
| CTA / accent | `#EA580C` | `bg-accent` | `--color-accent` |
| 背景 | `#FFFFFF` | `bg-bg` | `--color-bg` |
| 次背景 | `#F8FAFC` | `bg-bg-subtle` | `--color-bg-subtle` |
| 流水线底栏背景 | `#ECFEFF` | `bg-bg-stage` | `--color-bg-stage` |
| 文字主 | `#0F172A` | `text-fg` | `--color-fg` |
| 文字辅 | `#475569` | `text-fg-muted` | `--color-fg-muted` |
| 文字弱 | `#94A3B8` | `text-fg-dim` | `--color-fg-dim` |
| 描边 | `#E2E8F0` | `border-border` | `--color-border` |
| 成功 | `#10B981` | `text-success` | `--color-success` |
| 警告 | `#F59E0B` | `text-warning` | `--color-warning` |
| 错误 | `#DC2626` | `text-danger` | `--color-danger` |
| 信息 | `#0EA5E9` | `text-info` | `--color-info` |

数据来源：`frontend/src/lib/tokens.ts` + `frontend/src/index.css` `:root` + `frontend/tailwind.config.js` 三处保持一致。`tokens.test.ts` 做单测防漂移。

## 2. Typography

- **字体**：Inter（400/500/600/700），CJK fallback `PingFang SC, Microsoft YaHei, sans-serif`
- **Tailwind class**：`font-sans`（已全局默认）
- **大小刻度**：Tailwind 默认 (`text-xs 12 / sm 14 / base 16 / lg 18 / xl 20 / 2xl 24 / 3xl 30`)
- **行高**：标题 `leading-tight`（1.2），正文 `leading-normal`（1.5）

## 3. 半径 / 阴影 / 焦点

| | 值 | Tailwind |
|---|---|---|
| 圆角 sm | `6px` | `rounded-sm` |
| 圆角 md | `10px` | `rounded-md` / `rounded` |
| 圆角 lg | `16px` | `rounded-lg` |
| 圆角 pill | `9999px` | `rounded-pill` |
| 阴影 card | 0 1px 3px + 0 4px 12px | `shadow-card` |
| 阴影 popover | 0 8px 32px | `shadow-popover` |
| 焦点环 | `0 0 0 3px rgba(13,148,136,0.35)` | 自动（`* :focus-visible`） |

## 4. 公共组件清单（`src/components/ui/`）

> **v0.6 已采用 shadcn/ui (Slate base + New York style) 重写组件层。**
> 组件文件命名小写（`button.tsx` / `card.tsx` 等），沿用 shadcn 的命名约定。

| 组件 | 来源 | 主要 props |
|---|---|---|
| `Button` | shadcn | `variant` (default / destructive / outline / secondary / ghost / link / **accent**), `size` (default / sm / lg / icon) |
| `Card` + 5 slots | shadcn | `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter` |
| `Badge` | shadcn + v0.6 扩展 | `variant` (default / secondary / destructive / outline / success / warning / info), `dot` |
| `Input` | shadcn | 标准 input props |
| `Textarea` | shadcn | 标准 textarea props |
| `Label` | shadcn (Radix) | 标准 label |
| `Skeleton` | shadcn | `className` |
| `Tooltip` + `TooltipProvider` / `TooltipTrigger` / `TooltipContent` | shadcn (Radix) | 复合组件 |
| `Dialog` + 6 slots | shadcn (Radix) | 受控/非受控 |
| `Sheet` + slots (右侧抽屉) | shadcn (Radix) | `side` (top/bottom/left/right) |
| `Tabs` + 3 slots | shadcn (Radix) | 受控/非受控 |
| `Spinner` | 项目保留 | `size` (sm/md/lg), `label` |
| `EmptyState` + `DefaultEmptyIllustration` | 项目保留 | `title`, `description`, `icon`, `action` |
| `Sonner Toaster` | shadcn | App.tsx 已挂载 |

## 5. 流程可视化组件（`src/components/flow/`）

| 组件 | 用途 | 数据来源 |
|---|---|---|
| `StageCard` | 单阶段进度卡（带 icon、status badge、progress bar、meta） | 输入 prop |
| `LiveSignal` | 提供商实时状态（圆点 + 状态标签） | 输入 prop |
| `RankBadge` | 排名 #1 金 / #2 银 / #3 铜 + trend | 输入 prop |
| `KnowledgeChunkCard` | 知识 chunk 卡片（v0.5 hybrid 分数 + 引用数） | `MentionResult` |
| `MentionMatrix` | 品牌 × 问题 × provider 热力图 | `MentionResult[]` |
| `ReasoningTrace` | Agent ReAct 推理时间线 | SSE events (`tool_call_start/result`, `human_confirmation_required`) |

## 6. Layout Shell

```
┌───────────────────────────────────────────────────────────┐
│ TopBar: Logo + "GEO 优化系统" + 🔔 + ⚙                    │
├──────────┬─────────────────────────────┬─────────────────┤
│ SideNav  │ Breadcrumb                  │ ContextPane (xl) │
│ (主导航)  │ ────────                   │ (per-page 可选)  │
│          │ Page content                │                 │
├──────────┴─────────────────────────────┴─────────────────┤
│ PipelineRail: 6 节点全局优化流水线 (底部 60px)           │
└───────────────────────────────────────────────────────────┘
```

## 7. 信息架构（IA）

7 个一级分组 + 子项，详见 `frontend/src/App.tsx` 的 `navItems`。所有 19 个旧 URL 兼容通过 React Router `<Route>` 维持；新增 `/settings`。

| 旧 URL | 新的 IA 位置 |
|---|---|
| `/` (原 ReportList) | 侧边「诊断 / 历史报告」 |
| `/new` | 侧边「诊断 / 新建诊断」 |
| `/reports/:id` | 维持 |
| `/knowledge` `/knowledge/:kbId` | 侧边「知识库」 |
| `/tasks` `/tasks/new` `/tasks/:id` | 侧边「生成」 |
| `/reviews` `/reviews/:id` | 侧边「生成 / 审核队列」 |
| `/publishers` `/publishes` | 侧边「发布」 |
| `/monitors` `/monitors/new` `/monitors/:id` | 侧边「监测」 |
| `/notifications` | 侧边「监测 / 阈值通知」 |
| `/agent` `/agent/:sessionId` | 侧边「智能助手」 |
| 新增 `/settings` | 侧边「设置」(P1+ 实现) |

## 8. PipelineRail 6 节点

| Key | Label | Default to |
|---|---|---|
| `diagnose` | 诊断 | `/` |
| `generate` | 生成 | `/tasks` |
| `review` | 审核 | `/reviews` |
| `publish` | 发布 | `/publishes` |
| `monitor` | 监测 | `/monitors` |
| `track` | 跟踪 | `/monitors` |

数据来源：`usePipelineState`（P0 stub — 全部 pending；P1 替换为真实聚合）

## 9. 如何在 page 中使用 token

```tsx
import { cn } from '@/lib/utils';
import { tokens } from '@/lib/tokens';

// Tailwind class 方式（推荐）
<button className={cn('bg-primary text-primary-fg hover:bg-primary/90', 'rounded-md h-10 px-4')}>保存</button>

// 直接读常量（用于 inline style / 计算场景）
<div style={{ background: tokens.color.bgStage }}>...</div>

// CSS 变量（用于第三方库 / 动画）
<div style={{ boxShadow: 'var(--shadow-focus)' }}>...</div>
```

## 10. 焦点环与 a11y

- 全局 `*:focus-visible` 自动应用 `--shadow-focus`
- 颜色对比遵循 WCAG AA 4.5:1（primary #0D9488 vs white = 4.78:1）
- 尊重 `prefers-reduced-motion`（关闭动画）
- 全交互带 `aria-label` / `role`

## 11. 测试

- **单测**：vitest + @testing-library/react；`*.test.tsx`
- **e2e**：playwright；`tests/e2e/*.spec.ts`
- **a11y**：axe-core + playwright；`p0-a11y.spec.ts` 等
- 跑：
  ```bash
  npm test          # 单测
  npm run test:e2e  # e2e
  ```

## 12. 知识库全局搜索面板（`/knowledge` 页面顶部 — v0.6 P1.3）

> **RAG 召回语义**:全语料池召回,用户不报 KB 名,命中带来源标签。

```
┌─ /knowledge ───────────────────────────────────────────┐
│ ┌────────────────────────────────────────────────────┐ │
│ │ 🔍  [跨知识库全文检索（无需选 KB，回车搜索） ]  [搜索] │ │  ← 全局搜索面板（v0.6 P1.3）
│ └────────────────────────────────────────────────────┘ │
│                                                          │
│   命中（KB-badge · 文档名 · sources chip · score）：       │
│   ┌────────────────────────────────────────────────────┐ │
│   │ [北北云吞]  来自 北北云吞.md  [vector][keyword]  score 0.054 │ │
│   │   「脆马蹄陈皮捶打大肉云吞…」                              │ │
│   │   打开知识库 →                                            │ │
│   └────────────────────────────────────────────────────┘ │
│                                                          │
│  ─── 我的知识库 ─────────────────────────────────────── │
│  + 新建知识库                                            │
│  ┌─ 北北云吞  ──────────────────── 2026-07-10  [删除]  ┐ │  ← 原 KB 列表不变
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

| 元素 | 行为 |
|---|---|
| 输入框 | `<input type="search">` + aria-label，回车才触发；空 query 不发请求（`enabled: false`） |
| KB 名 badge | `bg-primary/10 text-primary` 小药丸 |
| 来源 chip | `border-border text-[10px]` 显示 `vector` / `keyword` |
| Score | RRF fused score，保留 3 位小数 |
| 「打开知识库 →」 | `<Link to={/knowledge/${kb_id}}>` 直跳详情 |

**API**：`GET /api/knowledge/search?q=&limit=`（不需要 kb_id）
**响应**：`{ query, hits: [{ kb_id, kb_name, doc_id, doc_filename, chunk_id, content, score, sources }] }`
