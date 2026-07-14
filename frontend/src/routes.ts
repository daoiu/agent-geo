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
