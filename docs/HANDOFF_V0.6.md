# HANDOFF — v0.6 前端全面重设计 (Phase 0)

> 最后更新: 2026-07-10

## 已完成

- **设计系统地基**:tokens + Tailwind + CSS vars + Inter 字体 (`src/lib/tokens.ts`, `tailwind.config.js`, `src/index.css`)
- **公共组件库 (15 个)** in `src/components/ui/`:Button, Input, Select, Textarea, Spinner, FieldWrapper, Card (+5 slots), Badge, EmptyState, Modal, Drawer, ConfirmDialog, Skeleton, SkeletonList, Tooltip, Tabs (+3 slots), Accordion, Stepper
- **流程组件 (6 个)** in `src/components/flow/`:StageCard, LiveSignal, RankBadge, KnowledgeChunkCard, MentionMatrix, ReasoningTrace
- **Layout 组件 (4 个)** in `src/components/layout/`:TopBar (新 Logo), SideNav (7 组 IA), Breadcrumb, LayoutShell, PipelineRail (6 节点底栏, P0 stub 状态)
- **App.tsx 接入**:所有 19 路由保留,新 LayoutShell 包裹,新增 `/settings` 占位
- **62 个单测 + e2e (布局 + a11y)**:全过
- **文档**:`frontend/docs/DESIGN.md` (tokens 速查)
- **CHANGELOG** 增加 v0.6 section

## 验证

```bash
cd frontend
npm test           # 62 tests pass
npx tsc --noEmit   # 类型检查通过
npm run dev        # 启动后访问 / 看 LayoutShell;访问 /new /tasks /agent 等一切 19 个 URL 仍可走
```

## 已知遗留 (留 P1+)

| 项 | 何时做 | 工时估 |
|---|---|---|
| `usePipelineState` 替换 stub 为真实 5 个 React Query 聚合 | P1 | 1h |
| 各 page 用新组件重写 | P1-P5 | P1(诊断页)+P2(agent)+P3(知识库/生成)+P4(发布/监测) |
| Dark mode | v0.7 (本期只预留 `--color-*` token) | — |
| `/settings` 实际内容 | P1 | 1h |
| PDF 排版调整 (新 token) | P1 | 1h |

## 设计决策登记

| 决策 | 选择 | 原因 |
|---|---|---|
| 设计语言 | 温暖生产力 (Teal + Orange) | 用户定 |
| 重构深度 | 全面重设计 | 用户定 |
| IA 顶层 | 侧边 + 面包屑 | 用户定 |
| 字体 | Inter | 兼容中英文 / Google Fonts 易加载 |
| Logo | 极简 SVG (圆心 + 6 脉冲点) | 表达"多源信息发射中心" |
| PipelineRail 数据 | P0 stub (全 pending),P1 接 5 个 query | 避免引入未测量的 API 形态 |
| Modal 实现 | HTML5 `<dialog>` 原生 | 内置焦点陷阱 / ESC / backdrop,零依赖 |
| 测试框架 | vitest 4 + @testing-library/react 16 | 项目原只有 Playwright,补单元层 |
| a11y 范围 (P0) | 仅 layout shell (header/nav/footer/main) | page 内部违规要等 page 重写 |

## 文件地图

```
frontend/
├── docs/DESIGN.md                                              # 新
├── tailwind.config.js                                          # 改
├── index.html                                                  # 改 (title + Inter)
├── src/
│   ├── App.tsx                                                 # 改 (LayoutShell 接入)
│   ├── index.css                                               # 改 (tokens + base reset)
│   ├── lib/
│   │   ├── tokens.ts                                           # 新
│   │   ├── tokens.test.ts                                      # 新
│   │   ├── usePipelineState.ts                                 # 新 (stub)
│   │   └── utils.ts                                            # 沿用
│   ├── test/
│   │   ├── setup.ts                                            # 新
│   │   ├── renderWithRouter.tsx                                # 新
│   │   └── sanity.test.ts                                      # 新
│   ├── components/
│   │   ├── ui/         (15 个公共组件 + 测试)
│   │   ├── flow/       (6 个流程组件 + 测试)
│   │   └── layout/     (4 个 layout 组件 + PipelineRail + 测试)
│   ├── pages/          (全部沿用,内部样式 P1+ 升级)
│   ├── api/client.ts                                          # 沿用
│   └── types/                                                 # 沿用
└── tests/e2e/
    ├── diagnosis-flow.spec.ts                                  # 改 (brand 名 + 加 P0 用例)
    ├── p0-layout-shell.spec.ts                                 # 新
    └── p0-a11y.spec.ts                                         # 新
```

## 提交记录 (本次 PR 涉及 commits)

```
fix(backend): anchor .env to project root + strict Settings validator
chore(frontend/v0.6/P0): vitest+RTL+axe infra, renderWithRouter helper
feat(frontend/v0.6/P0): design tokens (Tailwind+CSS vars+Inter+tests)
feat(frontend/v0.6/P0): Button, Input, Select, Textarea, Spinner, FieldWrapper
feat(frontend/v0.6/P0): Card (+slots), Badge, EmptyState (+DefaultEmptyIllustration)
feat(frontend/v0.6/P0): Modal+Drawer+ConfirmDialog, Skeleton+Tooltip+Tabs+Accordion, Stepper
feat(frontend/v0.6/P0): flow components — StageCard, LiveSignal, RankBadge, KnowledgeChunkCard, MentionMatrix, ReasoningTrace
feat(frontend/v0.6/P0): LayoutShell + TopBar + SideNav + Breadcrumb + PipelineRail (stub state)
feat(frontend/v0.6/P0): App.tsx mounts LayoutShell + navItems + crumbsFor mapper
test(frontend/v0.6/P0): e2e — LayoutShell smoke + a11y axe (header/nav/footer/main)
docs(frontend/v0.6/P0): DESIGN.md tokens guide + CHANGELOG + HANDOFF_V0.6
```

## 退出标准

✅ P0 退出:62 单测 + 5 layout 单测 + Playwright 2 e2e spec 全部通过 + TS strict 通过 + dev server 启动 19 路由可达 + 全 visual 上能看到新 TopBar + SideNav + 6 节点底栏 + 面包屑。

下一阶段入口:P1 仪表盘 + 诊断流程可视化(StageCard + LiveSignal + PipelineRail 真数据)。
