import { BrowserRouter, Route, Routes, Link, useLocation } from 'react-router-dom';
import { useMemo } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import NewDiagnosis from '@/pages/NewDiagnosis';
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
import AgentSessionList from '@/pages/AgentSessionList';
import AgentChat from '@/pages/AgentChat';

import { LayoutShell } from '@/components/layout/LayoutShell';
import { Toaster } from '@/components/ui/sonner';
import { navItems } from '@/components/layout/navConfig';
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
 * navItems — moved to `navConfig.ts` so CommandPalette can share it
 * without pulling in the router. Imported above.
 */

/**
 * crumbsFor — path → breadcrumb crumbs. Last item is the current page
 * (rendered as plain text per a11y).
 */
function crumbsFor(path: string): Crumb[] {
  if (path === '/') return [{ label: '仪表盘' }];
  if (path === '/new') return [{ label: '诊断', to: '/new' }, { label: '新建诊断' }];
  if (path.startsWith('/diagnosis/'))
    return [{ label: '诊断', to: '/new' }, { label: '诊断进度' }];
  if (path.startsWith('/reports/'))
    return [{ label: '诊断', to: '/new' }, { label: '诊断报告' }];
  if (path === '/knowledge')
    return [{ label: '知识库' }];
  if (path.startsWith('/knowledge/'))
    return [{ label: '知识库', to: '/knowledge' }, { label: '文档详情' }];
  if (path === '/tasks') return [{ label: '生成', to: '/tasks' }, { label: '生成任务' }];
  if (path === '/tasks/new') return [{ label: '生成', to: '/tasks' }, { label: '创建任务' }];
  if (path.startsWith('/tasks/'))
    return [{ label: '生成', to: '/tasks' }, { label: '任务详情' }];
  if (path === '/reviews') return [{ label: '审核', to: '/reviews' }, { label: '审核队列' }];
  if (path.startsWith('/reviews/'))
    return [{ label: '审核', to: '/reviews' }, { label: '文章审核' }];
  if (path === '/publishers') return [{ label: '发布', to: '/publishes' }, { label: '平台配置' }];
  if (path === '/publishes') return [{ label: '发布' }, { label: '发布历史' }];
  if (path === '/monitors') return [{ label: '监测', to: '/monitors' }, { label: '品牌监测' }];
  if (path === '/monitors/new') return [{ label: '监测', to: '/monitors' }, { label: '新建监测' }];
  if (path.startsWith('/monitors/'))
    return [{ label: '监测', to: '/monitors' }, { label: '监测详情' }];
  if (path === '/notifications') return [{ label: '监测', to: '/monitors' }, { label: '阈值通知' }];
  if (path === '/agent') return [{ label: '智能助手' }, { label: '会话列表' }];
  if (path.startsWith('/agent/'))
    return [{ label: '智能助手', to: '/agent' }, { label: '会话' }];
  if (path === '/settings') return [{ label: '设置' }];
  return [{ label: path }];
}

function LayoutShellRouter() {
  const location = useLocation();
  const { nodes } = usePipelineState();
  const crumbs = useMemo(() => crumbsFor(location.pathname), [location.pathname]);
  const [paletteOpen, setPaletteOpen] = useCommandPalette();
  const { theme, toggle: toggleTheme } = useDarkMode();
  return (
    <>
      <LayoutShell
        navItems={navItems}
        crumbs={crumbs}
        pipelineNodes={nodes}
        onOpenCommandPalette={() => setPaletteOpen(true)}
        isDark={theme === 'dark'}
        onToggleDark={toggleTheme}
      >
      <Routes>
        <Route path="/" element={<ReportList />} />
        <Route path="/new" element={<NewDiagnosis />} />
        <Route path="/diagnosis/:taskId/status" element={<DiagnosisStatus />} />
        <Route path="/reports/:reportId" element={<ReportView />} />
        <Route path="/knowledge" element={<KnowledgeList />} />
        <Route path="/knowledge/:kbId" element={<KnowledgeDetail />} />
        <Route path="/tasks" element={<TaskList />} />
        <Route path="/tasks/new" element={<NewTask />} />
        <Route path="/tasks/:taskId" element={<TaskDetail />} />
        <Route path="/reviews" element={<ReviewQueue />} />
        <Route path="/reviews/:articleId" element={<ReviewArticle />} />
        <Route path="/publishers" element={<PublisherConfigPage />} />
        <Route path="/publishes" element={<PublishList />} />
        <Route path="/monitors" element={<MonitorList />} />
        <Route path="/monitors/new" element={<NewMonitor />} />
        <Route path="/monitors/:monitorId" element={<MonitorDetail />} />
        <Route path="/notifications" element={<NotificationSettings />} />
        <Route path="/agent" element={<AgentSessionList />} />
        <Route path="/agent/:sessionId" element={<AgentChat />} />
        {/* Real settings page — see Settings.tsx */}
        <Route path="/settings" element={<Settings />} />
        {/* Catch-all */}
        <Route
          path="*"
          element={
            <div className="rounded-lg border border-dashed border-border bg-bg p-12 text-center">
              <h2 className="mb-2 text-lg font-semibold">页面不存在</h2>
              <Link to="/" className="text-primary hover:underline">
                返回首页
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
