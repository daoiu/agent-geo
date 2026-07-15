import { BrowserRouter, Navigate, Route, Routes, Link, useLocation, useParams } from 'react-router-dom';
import { useMemo } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import NewDiagnosis from '@/pages/NewDiagnosis';
import Dashboard from '@/pages/Dashboard';
import Settings from '@/pages/Settings';
import DiagnosisStatus from '@/pages/DiagnosisStatus';
import ReportView from '@/pages/ReportView';
import ReportList from '@/pages/ReportList';
import KnowledgeList from '@/pages/KnowledgeList';
import KnowledgeDetail from '@/pages/KnowledgeDetail';
import TaskList from '@/pages/TaskList';
import NewTask from '@/pages/NewTask';
import TaskDetail from '@/pages/TaskDetail';
import ReviewQueue from '@/pages/ReviewQueue';
import ReviewArticle from '@/pages/ReviewArticle';
import PublisherConfigPage from '@/pages/PublisherConfig';
import PublishList from '@/pages/PublishList';
import MonitorList from '@/pages/MonitorList';
import MonitorDetail from '@/pages/MonitorDetail';
import NewMonitor from '@/pages/NewMonitor';
import NotificationSettings from '@/pages/NotificationSettings';
import AgentWorkspace from '@/pages/AgentWorkspace';

import { LayoutShell } from '@/components/layout/LayoutShell';
import { Toaster } from '@/components/ui/sonner';
import { navItems, navSections } from '@/components/layout/navConfig.tsx';
import { ROUTES, ROUTE_REDIRECTS } from '@/routes';
import { CostDashboard } from '@/components/cost/CostDashboard';
import KnowledgeSearch from '@/pages/KnowledgeSearch';
import DevTools from '@/pages/DevTools';
import { AgentSessionListPanel } from '@/components/layout/AgentSessionListPanel';
import { CommandPalette, useCommandPalette } from '@/components/layout/CommandPalette';
import { useDarkMode } from '@/hooks/useDarkMode';
import type { Crumb } from '@/components/layout/Breadcrumb';
import { usePipelineState } from '@/lib/usePipelineState';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

/**
 * RedirectWithParams — mounts at a legacy path that contains `:param`
 * placeholders (e.g. `/reports/:reportId`) and forwards to the v0.7
 * canonical URL with the captured params substituted in.  Static-only
 * redirects can use `<Navigate to={...} replace />` directly.
 */
function RedirectWithParams({ to }: { to: string }) {
  const params = useParams();
  let resolved = to;
  for (const [k, v] of Object.entries(params)) {
    resolved = resolved.replace(`:${k}`, String(v));
  }
  return <Navigate to={resolved} replace />;
}

/**
 * navItems — moved to `navConfig.ts` so CommandPalette can share it
 * without pulling in the router. Imported above.
 */

/**
 * crumbsFor — path → page-title + (optional) subtitle.  Drives the
 * page-header (single H1 of `last.label`, optional subtitle of
 * `last.description`) seen at the top of every LayoutShell page.
 *
 * v0.7.1: rewritten as a data-driven META table indexed by `ROUTES`
 * keys. The old hard-coded `if` chain was the source of a UX bug
 * where unmatched paths fell through to `return [{ label: path }]`
 * and rendered the literal machine URL (e.g. `/diagnose/new`) as the
 * page title in the breadcrumb.
 */
const CRUMB_META: Record<
  string,
  { sectionLabel: string; sectionTo?: string; pageLabel: string; description?: string }
> = {
  // 诊断 (Dashboard)
  [ROUTES.diagnose]: {
    sectionLabel: '诊断',
    sectionTo: ROUTES.diagnose,
    pageLabel: '诊断',
    description: '全局诊断入口与最近的优化活动。',
  },
  [ROUTES.diagnoseNew]: {
    sectionLabel: '诊断',
    sectionTo: ROUTES.diagnose,
    pageLabel: '新建诊断',
    description: '输入品牌信息，60-90 秒获取诊断报告。',
  },
  [ROUTES.diagnoseRun]: {
    sectionLabel: '诊断',
    sectionTo: ROUTES.diagnose,
    pageLabel: '诊断进度',
    description: '正在抓取与多 LLM 询问；可在这里看到实时信号。',
  },
  [ROUTES.diagnoseReports]: {
    sectionLabel: '诊断',
    sectionTo: ROUTES.diagnose,
    pageLabel: '历史报告',
    description: '所有诊断报告 · 按时间倒序。',
  },
  [ROUTES.diagnoseReport]: {
    sectionLabel: '诊断',
    sectionTo: ROUTES.diagnose,
    pageLabel: '诊断报告',
    description: '五维评分、提及位置、情感分布。',
  },
  // 知识 — `ROUTES.knowledge === '/knowledge/bases'` (类目根 + 全部 KB
  // 共享), entries are added below.
  [ROUTES.knowledge]: {
    sectionLabel: '知识',
    sectionTo: ROUTES.knowledge,
    pageLabel: '知识 / 全部 KB',
    description: '上传 PDF / Word / MD 用于内容生成。',
  },
  [ROUTES.knowledgeDetail]: {
    sectionLabel: '知识',
    sectionTo: ROUTES.knowledge,
    pageLabel: '文档详情',
    description: '本 KB 的 chunks 与 hybrid 引用情况。',
  },
  [ROUTES.knowledgeSearch]: {
    sectionLabel: '知识',
    sectionTo: ROUTES.knowledge,
    pageLabel: '跨库检索',
    description: '在所有 KB 中执行 hybrid recall。',
  },
  // 生成
  [ROUTES.generateTasks]: {
    sectionLabel: '生成',
    sectionTo: ROUTES.generate,
    pageLabel: '生成任务',
  },
  [ROUTES.generateTaskNew]: {
    sectionLabel: '生成',
    sectionTo: ROUTES.generate,
    pageLabel: '创建任务',
    description: '选 KB → 配置主题与风格 → 启动批量生成。',
  },
  [ROUTES.generateTask]: {
    sectionLabel: '生成',
    sectionTo: ROUTES.generate,
    pageLabel: '任务详情',
  },
  [ROUTES.generateReviews]: {
    sectionLabel: '生成',
    sectionTo: ROUTES.generate,
    pageLabel: '审核队列',
  },
  [ROUTES.generateReview]: {
    sectionLabel: '生成',
    sectionTo: ROUTES.generate,
    pageLabel: '文章审核',
  },
  // 发布
  [ROUTES.publishConfigs]: {
    sectionLabel: '发布',
    sectionTo: ROUTES.publish,
    pageLabel: '平台配置',
  },
  [ROUTES.publishJobs]: {
    sectionLabel: '发布',
    sectionTo: ROUTES.publish,
    pageLabel: '发布历史',
  },
  // 监测
  [ROUTES.monitorTasks]: {
    sectionLabel: '监测',
    sectionTo: ROUTES.monitor,
    pageLabel: '品牌监测',
  },
  [ROUTES.monitorTaskNew]: {
    sectionLabel: '监测',
    sectionTo: ROUTES.monitor,
    pageLabel: '新建监测',
    description: '配置品牌、问题频率、通知策略。',
  },
  [ROUTES.monitorTask]: {
    sectionLabel: '监测',
    sectionTo: ROUTES.monitor,
    pageLabel: '监测详情',
  },
  // Settings + dev-tools + notifications
  [ROUTES.settingsGeneral]: {
    sectionLabel: '设置',
    pageLabel: '设置',
    description: '后端连通性、版本信息与各模块入口。变更类操作请前往对应模块页。',
  },
  [ROUTES.settingsNotifications]: {
    sectionLabel: '设置',
    pageLabel: '通知设置',
    description: '邮件渠道与监测阈值默认。',
  },
  [ROUTES.settingsDevTools]: {
    sectionLabel: '设置',
    pageLabel: '故障注入',
    description: 'dev 模式可见 — LLM 超时 / 工具错误 / 网络故障。',
  },
  // 智能助手
  [ROUTES.agent]: {
    sectionLabel: '智能助手',
    pageLabel: '会话列表',
  },
  [ROUTES.agentSession]: {
    sectionLabel: '智能助手',
    pageLabel: '会话',
  },
  // 月度成本
  [ROUTES.cost]: {
    sectionLabel: '监测',
    sectionTo: ROUTES.monitor,
    pageLabel: '月度成本',
    description: '按 provider / model 拆分的 LLM 调用成本。',
  },
};

function crumbsFor(pathname: string): Crumb[] {
  // 1) Exact match wins.
  const exact = CRUMB_META[pathname];
  if (exact) return crumbOf(exact);

  // 2) Prefix match for routes that carry a dynamic segment
  //    (`:taskId`, `:reportId`, …).  We strip leading segments until
  //    a key in the meta table matches.
  for (const key of Object.keys(CRUMB_META)) {
    if (!key.includes(':')) continue;
    if (pathMatchesKey(pathname, key)) return crumbOf(CRUMB_META[key]);
  }

  // 3) Hard safety net — never echo the raw path back to the UI.
  //    If we reach this branch we forgot to add a META row above;
  //    fall back to a neutral "本页" title so the header is always
  //    human-readable.
  return [{ label: '本页' }];
}

function crumbOf(
  meta: { sectionLabel: string; sectionTo?: string; pageLabel: string; description?: string },
): Crumb[] {
  const out: Crumb[] = [];
  if (meta.sectionTo) out.push({ label: meta.sectionLabel, to: meta.sectionTo });
  else if (meta.sectionLabel) out.push({ label: meta.sectionLabel });
  out.push({ label: meta.pageLabel, description: meta.description });
  return out;
}

function pathMatchesKey(pathname: string, key: string): boolean {
  const pSegs = pathname.split('/');
  const kSegs = key.split('/');
  if (pSegs.length !== kSegs.length) return false;
  for (let i = 0; i < pSegs.length; i++) {
    if (kSegs[i]!.startsWith(':')) continue;
    if (pSegs[i] !== kSegs[i]) return false;
  }
  return true;
}

function activeSectionFromPath(pathname: string): string {
  // Spec §5.1 — match /diagnose, /knowledge/bases, /generate/tasks, etc.
  if (pathname.startsWith('/diagnose')) return 'diagnose';
  if (pathname.startsWith('/knowledge')) return 'knowledge';
  if (pathname.startsWith('/generate')) return 'generate';
  if (pathname.startsWith('/publish')) return 'publish';
  if (pathname.startsWith('/monitor') || pathname.startsWith('/cost')) return 'monitor';
  if (pathname.startsWith('/settings')) return 'settings';
  if (pathname.startsWith('/agent')) return 'agent';
  return 'diagnose';
}

function LayoutShellRouter() {
  const location = useLocation();
  const { nodes } = usePipelineState();
  const crumbs = useMemo(() => crumbsFor(location.pathname), [location.pathname]);
  const [paletteOpen, setPaletteOpen] = useCommandPalette();
  const { theme, toggle: toggleTheme } = useDarkMode();
  const isAgentRoute = location.pathname === '/agent' || location.pathname.startsWith('/agent/');
  const activeSection = activeSectionFromPath(location.pathname);
  return (
    <>
      <LayoutShell
        sections={navSections}
        activeSection={activeSection}
        onSelectSection={() => {}}
        navItems={navItems}
        crumbs={crumbs}
        pipelineNodes={nodes}
        asideLeft={isAgentRoute ? <AgentSessionListPanel /> : undefined}
        onOpenCommandPalette={() => setPaletteOpen(true)}
        isDark={theme === 'dark'}
        onToggleDark={toggleTheme}
      >
      <Routes>
        {/* v0.7 IA — 6 drawer category roots mount the real pages. */}
        <Route path={ROUTES.diagnose} element={<Dashboard />} />
        <Route path={ROUTES.diagnoseNew} element={<NewDiagnosis />} />
        <Route path={ROUTES.diagnoseRun} element={<DiagnosisStatus />} />
        <Route path={ROUTES.diagnoseReports} element={<ReportList />} />
        <Route path={ROUTES.diagnoseReport} element={<ReportView />} />
        <Route path={ROUTES.knowledge} element={<KnowledgeList />} />
        <Route path={ROUTES.knowledgeDetail} element={<KnowledgeDetail />} />
        <Route path={ROUTES.knowledgeSearch} element={<KnowledgeSearch />} />
        <Route path={ROUTES.generateTasks} element={<TaskList />} />
        <Route path={ROUTES.generateTaskNew} element={<NewTask />} />
        <Route path={ROUTES.generateTask} element={<TaskDetail />} />
        <Route path={ROUTES.generateReviews} element={<ReviewQueue />} />
        <Route path={ROUTES.generateReview} element={<ReviewArticle />} />
        <Route path={ROUTES.publishConfigs} element={<PublisherConfigPage />} />
        <Route path={ROUTES.publishJobs} element={<PublishList />} />
        <Route path={ROUTES.monitorTasks} element={<MonitorList />} />
        <Route path={ROUTES.monitorTaskNew} element={<NewMonitor />} />
        <Route path={ROUTES.monitorTask} element={<MonitorDetail />} />
        <Route path={ROUTES.settingsNotifications} element={<NotificationSettings />} />
        <Route path={ROUTES.settingsGeneral} element={<Settings />} />
        <Route
          path={ROUTES.settingsDevTools}
          element={
            import.meta.env.DEV ? (
              <DevTools />
            ) : (
              // Production: route exists but the dev panel tree-shakes
              // out of the bundle (see vite.config.ts → manualChunks).
              // A neutral 404 tile keeps the literal name out of the
              // prod bundle's source map, satisfying the red-line grep.
              <div className="rounded-lg border border-dashed border-border bg-bg p-12 text-center">
                <h2 className="mb-2 text-lg font-semibold">不可用</h2>
                <p className="text-sm text-fg-muted">
                  本节仅在开发模式下启用,生产构建已禁用。
                </p>
              </div>
            )
          }
        />
        {/* agent + cost remain mounted at their canonical paths only — they
            don't have legacy redirects in spec §5.3, so no alias needed. */}
        <Route path={ROUTES.agent} element={<AgentWorkspace />} />
        <Route path={ROUTES.agentSession} element={<AgentWorkspace />} />
        <Route path={ROUTES.cost} element={<CostDashboard />} />

        {/* v0.6 legacy URL compatibility — 19 redirects to the v0.7 IA */}
        {Object.entries(ROUTE_REDIRECTS).map(([from, to]) => (
          <Route
            key={from}
            path={from}
            element={<RedirectWithParams to={to} />}
          />
        ))}

        {/* Catch-all */}
        <Route
          path="*"
          element={
            <div className="rounded-lg border border-dashed border-border bg-bg p-12 text-center">
              <h2 className="mb-2 text-lg font-semibold">页面不存在</h2>
              <Link to={ROUTES.diagnose} className="text-primary hover:underline">
                返回诊断首页
              </Link>
            </div>
          }
        />
      </Routes>
      </LayoutShell>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <LayoutShellRouter />
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
