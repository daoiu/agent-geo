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
import { navItems } from '@/components/layout/navConfig.tsx';
import { ROUTES, ROUTE_REDIRECTS } from '@/routes';
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
 * crumbsFor — path → breadcrumb crumbs. Last item is the current page
 * (rendered as plain text per a11y).
 */
function crumbsFor(path: string): Crumb[] {
  if (path === '/')
    return [{ label: '仪表盘', description: '全局诊断入口与最近的优化活动。' }];
  if (path === '/new')
    return [
      { label: '诊断', to: '/new' },
      { label: '新建诊断', description: '输入品牌信息，60-90 秒获取诊断报告。' },
    ];
  if (path.startsWith('/diagnosis/'))
    return [
      { label: '诊断', to: '/new' },
      { label: '诊断进度', description: '正在抓取与多 LLM 询问；可在这里看到实时信号。' },
    ];
  if (path === '/reports')
    return [
      { label: '诊断', to: '/new' },
      { label: '历史报告', description: '所有诊断报告 · 按时间倒序。' },
    ];
  if (path.startsWith('/reports/'))
    return [
      { label: '诊断', to: '/new' },
      { label: '诊断报告', description: '五维评分、提及位置、情感分布。' },
    ];
  if (path === '/knowledge')
    return [{ label: '知识库', description: '上传 PDF / Word / MD 用于内容生成。' }];
  if (path.startsWith('/knowledge/'))
    return [
      { label: '知识库', to: '/knowledge' },
      { label: '文档详情', description: '本 KB 的 chunks 与 hybrid 引用情况。' },
    ];
  if (path === '/tasks')
    return [{ label: '生成', to: '/tasks' }, { label: '生成任务' }];
  if (path === '/tasks/new')
    return [
      { label: '生成', to: '/tasks' },
      { label: '创建任务', description: '选 KB → 配置主题与风格 → 启动批量生成。' },
    ];
  if (path.startsWith('/tasks/'))
    return [{ label: '生成', to: '/tasks' }, { label: '任务详情' }];
  if (path === '/reviews')
    return [{ label: '审核', to: '/reviews' }, { label: '审核队列' }];
  if (path.startsWith('/reviews/'))
    return [{ label: '审核', to: '/reviews' }, { label: '文章审核' }];
  if (path === '/publishers')
    return [{ label: '发布', to: '/publishes' }, { label: '平台配置' }];
  if (path === '/publishes')
    return [{ label: '发布' }, { label: '发布历史' }];
  if (path === '/monitors')
    return [{ label: '监测', to: '/monitors' }, { label: '品牌监测' }];
  if (path === '/monitors/new')
    return [
      { label: '监测', to: '/monitors' },
      { label: '新建监测', description: '配置品牌、问题频率、通知策略。' },
    ];
  if (path.startsWith('/monitors/'))
    return [{ label: '监测', to: '/monitors' }, { label: '监测详情' }];
  if (path === '/notifications')
    return [
      { label: '监测', to: '/monitors' },
      { label: '阈值通知', description: '邮件渠道与监测阈值默认。' },
    ];
  if (path === '/agent')
    return [{ label: '智能助手' }, { label: '会话列表' }];
  if (path.startsWith('/agent/'))
    return [{ label: '智能助手', to: '/agent' }, { label: '会话' }];
  if (path === '/settings')
    return [
      {
        label: '设置',
        description: '后端连通性、版本信息与各模块入口。变更类操作请前往对应模块页。',
      },
    ];
  return [{ label: path }];
}

function LayoutShellRouter() {
  const location = useLocation();
  const { nodes } = usePipelineState();
  const crumbs = useMemo(() => crumbsFor(location.pathname), [location.pathname]);
  const [paletteOpen, setPaletteOpen] = useCommandPalette();
  const { theme, toggle: toggleTheme } = useDarkMode();
  const isAgentRoute = location.pathname === '/agent' || location.pathname.startsWith('/agent/');
  return (
    <>
      <LayoutShell
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
        {/* agent + cost remain mounted at their canonical paths only — they
            don't have legacy redirects in spec §5.3, so no alias needed. */}
        <Route path={ROUTES.agent} element={<AgentWorkspace />} />
        <Route path={ROUTES.agentSession} element={<AgentWorkspace />} />
        <Route path={ROUTES.cost} element={
          // Cost page (Task 12) — until then surface a "coming in v0.7" tile.
          <div className="rounded-lg border border-dashed border-border bg-bg p-12 text-center">
            <h2 className="mb-2 text-lg font-semibold">月度成本</h2>
            <p className="text-sm text-fg-muted">
              Task 12 (recharts dashboard) will wire recharts data here.
            </p>
          </div>
        } />

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
