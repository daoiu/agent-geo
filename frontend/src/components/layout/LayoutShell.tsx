import { useState, type ReactNode } from 'react';
import { TopBar } from './TopBar';
import { SideNav, type NavItem } from './SideNav';
import { Breadcrumb, type Crumb } from './Breadcrumb';
import { PipelineRail, type PipelineNode } from './PipelineRail';
import { cn } from '@/lib/utils';

export interface LayoutShellProps {
  navItems: NavItem[];
  crumbs: Crumb[];
  pipelineNodes: PipelineNode[];
  contextPane?: ReactNode;
  /** Callback wired from TopBar's "搜索" button (⌘K / Ctrl K also opens it). */
  onOpenCommandPalette?: () => void;
  isDark?: boolean;
  onToggleDark?: () => void;
  children: ReactNode;
}

/**
 * LayoutShell — wraps every page with TopBar (top) + SideNav (left, responsive)
 * + Breadcrumb + main content + optional ContextPane (right) + PipelineRail (bottom).
 */
export function LayoutShell({
  navItems,
  crumbs,
  pipelineNodes,
  contextPane,
  onOpenCommandPalette,
  isDark,
  onToggleDark,
  children,
}: LayoutShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div className="flex h-screen flex-col bg-muted">
      <TopBar
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
        sidebarOpen={sidebarOpen}
        onOpenCommandPalette={onOpenCommandPalette}
        isDark={isDark}
        onToggleDark={onToggleDark}
      />
      <div className="flex flex-1 overflow-hidden">
        <aside
          className={cn(
            'hidden md:block',
            sidebarOpen && 'block'
          )}
        >
          <SideNav items={navItems} />
        </aside>
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl px-6 py-5">
            <Breadcrumb items={crumbs} />
            <div className="mt-4 flex gap-6">
              <div className="min-w-0 flex-1">{children}</div>
              {contextPane && (
                <aside className="hidden w-80 shrink-0 xl:block" aria-label="上下文面板">
                  {contextPane}
                </aside>
              )}
            </div>
          </div>
        </main>
      </div>
      <PipelineRail
        nodes={pipelineNodes}
        collapsed={collapsed}
        onToggle={() => setCollapsed((v) => !v)}
      />
    </div>
  );
}
