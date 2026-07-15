/**
 * v0.7 routes — single source of truth for the canonical IA + the legacy
 * redirect table.
 *
 * Two exports:
 *
 *   `ROUTES` (canonical)
 *     Object literal whose keys are stable identifiers (e.g. `diagnose`)
 *     and whose values are URL strings.  All route references in the
 *     app — `Link to={...}`, `navigate(...)`, `crumbsFor(...)`, NavDrawer
 *     sections, etc. — should pull from here so a rename edits one
 *     place.
 *
 *   `ROUTE_REDIRECTS` (legacy compatibility)
 *     The 19 legacy URLs from v0.6 (spec §5.3) mapped to their canonical
 *     replacements.  App.tsx mounts a `<Route path={from} element={
 *     <Navigate to={to} replace />}/>` for each row so the legacy
 *     link surface keeps working for 1-2 release cycles.
 *
 * Adding/removing entries here invalidates `routes.test.ts` (intentional).
 */

export const ROUTES = {
  // 6 drawer category roots (used by the NavDrawer + section landing pages).
  diagnose: '/diagnose',
  knowledge: '/knowledge/bases',
  generate: '/generate/tasks',
  publish: '/publish/jobs',
  monitor: '/monitor/tasks',
  settings: '/settings/general',

  // Sub-routes surfaced when each category is expanded.
  diagnoseNew: '/diagnose/new',
  diagnoseRun: '/diagnose/runs/:taskId',
  diagnoseReports: '/diagnose/reports',
  diagnoseReport: '/diagnose/reports/:reportId',

  knowledgeDetail: '/knowledge/bases/:kbId',
  knowledgeSearch: '/knowledge/search',

  generateTasks: '/generate/tasks',
  generateTaskNew: '/generate/tasks/new',
  generateTask: '/generate/tasks/:taskId',
  generateReviews: '/generate/reviews',
  generateReview: '/generate/reviews/:articleId',

  publishConfigs: '/publish/configs',
  publishJobs: '/publish/jobs',

  monitorTasks: '/monitor/tasks',
  monitorTaskNew: '/monitor/tasks/new',
  monitorTask: '/monitor/tasks/:monitorId',

  settingsGeneral: '/settings/general',
  settingsNotifications: '/settings/notifications',
  settingsModels: '/settings/models',
  settingsDevTools: '/settings/dev-tools',

  cost: '/cost',
  agent: '/agent',
  agentSession: '/agent/:sessionId',
} as const;

/**
 * 19 legacy URL → v0.7 redirect map. The substring `:name` is preserved
 * by `<Navigate replace>` when the target URL also carries a `:name`;
 * components that want richer dynamic substitution should build a
 * dedicated component instead of using this flat map.
 */
export const ROUTE_REDIRECTS: Record<string, string> = {
  '/': '/diagnose',
  '/new': '/diagnose/new',
  '/diagnosis/:taskId/status': '/diagnose/runs/:taskId',
  '/reports': '/diagnose/reports',
  '/reports/:reportId': '/diagnose/reports/:reportId',
  '/knowledge': '/knowledge/bases',
  '/knowledge/:kbId': '/knowledge/bases/:kbId',
  '/tasks': '/generate/tasks',
  '/tasks/new': '/generate/tasks/new',
  '/tasks/:taskId': '/generate/tasks/:taskId',
  '/reviews': '/generate/reviews',
  '/reviews/:articleId': '/generate/reviews/:articleId',
  '/publishers': '/publish/configs',
  '/publishes': '/publish/jobs',
  '/monitors': '/monitor/tasks',
  '/monitors/new': '/monitor/tasks/new',
  '/monitors/:monitorId': '/monitor/tasks/:monitorId',
  '/notifications': '/settings/notifications',
  '/settings': '/settings/general',
};

export type RouteKey = keyof typeof ROUTES;

/**
 * ROUTE_META — display metadata for every route key.  Consumed by
 * `breadcrumbFor()` so the page header (and any future title chip)
 * stays in sync with the URL table.
 */
type RouteMeta = { label: string; description?: string; parent?: RouteKey };

export const ROUTE_META: Record<RouteKey, RouteMeta> = {
  // 6 drawer category roots.
  diagnose: { label: '诊断', description: '诊断首页 + 最近活动' },
  knowledge: { label: '知识库', description: '上传 PDF / Word / MD 用于内容生成' },
  generate: { label: '生成任务', description: '批量内容生成 · 由专家代理驱动' },
  publish: { label: '发布中心', description: '平台配置 + 发布历史' },
  monitor: { label: '监测', description: '品牌提及率监测与阈值通知' },
  settings: { label: '设置', description: '后端连通性、版本信息与各模块入口' },

  // diagnose sub-pages.
  diagnoseNew: {
    label: '新建诊断',
    description: '输入品牌信息,60-90 秒获取诊断报告',
    parent: 'diagnose',
  },
  diagnoseRun: {
    label: '诊断进度',
    description: '正在抓取与多 LLM 询问;可在这里看到实时信号',
    parent: 'diagnoseNew',
  },
  diagnoseReports: {
    label: '历史报告',
    description: '所有诊断报告 · 按时间倒序',
    parent: 'diagnose',
  },
  diagnoseReport: {
    label: '诊断报告',
    description: '五维评分、提及位置、情感分布',
    parent: 'diagnoseReports',
  },

  // knowledge sub-pages.
  knowledgeDetail: {
    label: 'KB 详情',
    description: '本 KB 的 chunks 与 hybrid 引用情况',
    parent: 'knowledge',
  },
  knowledgeSearch: {
    label: '跨库检索',
    description: '在所有 KB 中执行 hybrid recall',
    parent: 'knowledge',
  },

  // generate sub-pages.
  generateTasks: { label: '生成任务', parent: 'generate' },
  generateTaskNew: {
    label: '创建任务',
    description: '选 KB → 配置主题与风格 → 启动批量生成',
    parent: 'generateTasks',
  },
  generateTask: { label: '任务详情', parent: 'generateTasks' },
  generateReviews: { label: '审核队列', parent: 'generate' },
  generateReview: { label: '文章审核', parent: 'generateReviews' },

  // publish sub-pages.
  publishConfigs: { label: '平台配置', parent: 'publish' },
  publishJobs: { label: '发布历史', parent: 'publish' },

  // monitor sub-pages.
  monitorTasks: { label: '品牌监测', parent: 'monitor' },
  monitorTaskNew: {
    label: '新建监测',
    description: '配置品牌、问题频率、通知策略',
    parent: 'monitorTasks',
  },
  monitorTask: { label: '监测详情', parent: 'monitorTasks' },

  // settings sub-pages.
  settingsGeneral: { label: '通用设置', description: '后端连通性、版本信息', parent: 'settings' },
  settingsNotifications: { label: '通知设置', parent: 'settings' },
  settingsModels: { label: '模型配置', description: 'Provider API key / 模型 / tier / fallback', parent: 'settings' },
  settingsDevTools: { label: 'DevTools(dev)', parent: 'settingsGeneral' },

  // top-level.
  cost: { label: '月度成本', description: '按 provider / model 拆分成本(P2 #49)' },
  agent: { label: '智能助手', description: '自然语言入口 · ReAct + handoff' },
  agentSession: { label: '会话', parent: 'agent' },
};

/**
 * breadcrumbFor — pick the most specific route matching `pathname`
 * and walk the `parent` chain to produce a 1- or 2-segment crumb
 * trail.  Falls back to `[{ label: pathname }]` (the legacy behaviour)
 * when no ROUTE matches.
 *
 * Parameter matching strips `/:param` placeholders before comparing
 * to the URL, so `/diagnose/reports/abc123` correctly resolves to
 * `diagnoseReport` even though the literal key is `/diagnose/reports/:reportId`.
 */
export function breadcrumbFor(pathname: string): Array<{ label: string; to?: string; description?: string }> {
  // Convert ROUTES pattern → regex by replacing `:name` placeholders.
  const candidates: Array<{ key: RouteKey; re: RegExp }> = (
    Object.entries(ROUTES) as [RouteKey, string][]
  ).map(([key, pattern]) => {
    const re = new RegExp('^' + pattern.replace(/:[a-zA-Z]+/g, '[^/]+') + '$');
    return { key, re };
  });

  // Find the most specific (longest pattern) match.
  const exact = candidates.find(({ re }) => re.test(pathname));
  if (!exact) {
    // Try legacy redirects too — `/new` etc. should still produce a crumb.
    const legacy = Object.entries(ROUTE_REDIRECTS).find(([from]) => from === pathname);
    if (legacy) return breadcrumbFor(legacy[1]);
    return [{ label: pathname }];
  }

  // Walk parent chain.
  const metaByKey: Record<RouteKey, RouteMeta> = ROUTE_META;
  const trail: Array<{ label: string; to?: string; description?: string }> = [];
  let cursor: RouteKey | undefined = exact.key;
  while (cursor) {
    const metaEntry: RouteMeta = metaByKey[cursor];
    const url: string = ROUTES[cursor];
    trail.unshift({
      label: metaEntry.label,
      to: url,
      description: metaEntry.description,
    });
    cursor = metaEntry.parent;
  }
  return trail;
}
