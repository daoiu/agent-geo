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
import { ROUTES, ROUTE_REDIRECTS, breadcrumbFor } from '@/routes';
import { CostDashboard } from '@/components/cost/CostDashboard';
import KnowledgeSearch from '@/pages/KnowledgeSearch';
import DevTools from '@/pages/DevTools';
import { AgentSessionListPanel } from '@/components/layout/AgentSessionListPanel';
import { CommandPalette, useCommandPalette } from '@/components/layout/CommandPalette';
import { useDarkMode } from '@/hooks/useDarkMode';
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
  const crumbs = useMemo(() => breadcrumbFor(location.pathname), [location.pathname]);
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
