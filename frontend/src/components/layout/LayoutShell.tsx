import { useState, type ReactNode } from 'react';
import { TopBar } from './TopBar';
import { SideNav, type NavItem } from './SideNav';
import { Breadcrumb, type Crumb } from './Breadcrumb';
import { PipelineRail, type PipelineNode } from './PipelineRail';
import { NavDrawer, type NavSection } from './NavDrawer';
import { cn } from '@/lib/utils';

export interface LayoutShellProps {
  /**
   * Legacy v0.6 sidebar config — flat list of items with optional children.
   * Still honored if `sections` is not provided, so existing route shells
   * keep rendering until they migrate to the v0.7 NavDrawer sections API.
   */
  navItems?: NavItem[];
  /**
   * v0.7 HarmonyOS IA — 6 drawer sections + optional 智能助手 entry.
   * Takes precedence over `navItems` when provided.
   */
  sections?: NavSection[];
  /**
   * Active section id (v0.7). When `sections` is used this drives the
   * left-rail active-state styling; falls back to "无" highlight in
   * navItems mode.
   */
  activeSection?: string;
  /** Required when `sections` is used — receives the clicked section id. */
  onSelectSection?: (id: string) => void;
  crumbs: Crumb[];
  pipelineNodes: PipelineNode[];
  contextPane?: ReactNode;
  /**
   * Optional left aside rendered inside `<main>` between the navigation
   * rail and children. Used by `/agent` to inject the session list column
   * (w-60). When present, the page takes the full main height and
   * children render as the right pane of a 2-col flex.
   */
  asideLeft?: ReactNode;
  /** Callback wired from TopBar's "搜索" button (⌘K / Ctrl K also opens it). */
  onOpenCommandPalette?: () => void;
  isDark?: boolean;
  onToggleDark?: () => void;
  children: ReactNode;
}

/**
 * LayoutShell — wraps every page with TopBar (top) + NavDrawer OR legacy
 * SideNav (left, responsive) + Breadcrumb + main content + optional
 * ContextPane (right) + PipelineRail (bottom).
 *
 * v0.7 default: NavDrawer with HarmonyOS glass surface, 6 sections, 60/240
 * collapse toggle. The legacy SideNav is still mounted when only
 * `navItems` is provided so the migration window doesn't break the older
 * pages.
 */
export function LayoutShell({
  navItems,
  sections,
  activeSection,
  onSelectSection,
  crumbs,
  pipelineNodes,
  contextPane,
  asideLeft,
  onOpenCommandPalette,
  isDark,
  onToggleDark,
  children,
}: LayoutShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const useDrawer = sections !== undefined;
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
          className={cn('hidden md:block', sidebarOpen && 'block')}
        >
          {useDrawer ? (
            <NavDrawer
              sections={sections!}
              activeSection={activeSection ?? sections![0]?.id ?? ''}
              onSelect={onSelectSection ?? (() => {})}
            />
          ) : (
            <SideNav items={navItems ?? []} />
          )}
        </aside>
        <main className="flex-1 overflow-y-auto">
          {asideLeft ? (
            <div className="flex h-full">
              <aside
                className="hidden w-60 shrink-0 border-r border-border bg-bg-stage md:block"
                aria-label="会话历史"
              >
                {asideLeft}
              </aside>
              <div className="min-w-0 flex-1 overflow-hidden">{children}</div>
            </div>
          ) : (
            <div className="mx-auto max-w-7xl px-6 py-6">
              <Breadcrumb items={crumbs} />
              <div className="mt-6 flex gap-6">
                <div className="min-w-0 flex-1">{children}</div>
                {contextPane && (
                  <aside className="hidden w-80 shrink-0 xl:block" aria-label="上下文面板">
                    {contextPane}
                  </aside>
                )}
              </div>
            </div>
          )}
        </main>
      </div>
      <PipelineRail
        nodes={pipelineNodes}
        collapsed={false}
        onToggle={() => {}}
      />
    </div>
  );
}
