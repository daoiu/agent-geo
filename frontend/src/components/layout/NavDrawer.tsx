import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

/**
 * v0.7 HarmonyOS NavDrawer — flat 6-category sidebar with collapse toggle,
 * active tint + 2px primary left bar, glass surface in light mode.
 *
 * Replaces v0.6 SideNav as the primary navigation. LayoutShell picks which
 * to mount based on environment; SideNav remains as a fallback / parallel
 * implementation until its tests are ported in a follow-up.
 */

export interface NavItem {
  to: string;
  label: string;
  icon?: ReactNode;
}

export interface NavSection {
  id: string;
  label: string;
  icon: ReactNode;
  to: string;
  items: NavItem[];
}

export interface NavDrawerProps {
  sections: NavSection[];
  activeSection: string;
  onSelect: (id: string) => void;
  className?: string;
}

export function NavDrawer({
  sections,
  activeSection,
  onSelect,
  className,
}: NavDrawerProps) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <nav
      aria-label="主导航"
      data-collapsed={collapsed ? 'true' : 'false'}
      className={cn(
        'h-full overflow-y-auto border-r border-glass-border bg-[var(--glass-bg)] backdrop-blur-[20px] p-4 transition-[width] duration-400 ease-spring-gentle',
        collapsed ? 'w-16' : 'w-60',
        className
      )}
    >
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="mb-4 rounded-md p-2 transition-colors hover:bg-primary-tint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={collapsed ? '展开导航' : '收起导航'}
      >
        <span aria-hidden="true">{collapsed ? '›' : '‹'}</span>
      </button>
      <ul className="space-y-2">
        {sections.map((s) => {
          const active = activeSection === s.id;
          return (
            <li key={s.id}>
              <Link
                to={s.to}
                onClick={() => onSelect(s.id)}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-[background-color,color] duration-400 ease-spring-gentle',
                  active
                    ? 'bg-primary-tint border-l-2 border-primary text-primary font-medium'
                    : 'text-fg-muted hover:bg-primary-tint/50 hover:text-fg'
                )}
                data-testid={`nav-section-${s.id}`}
              >
                <span className="flex h-5 w-5 items-center justify-center" aria-hidden="true">
                  {s.icon}
                </span>
                {!collapsed && <span>{s.label}</span>}
              </Link>
              {!collapsed && active && s.items.length > 0 && (
                <ul className="mt-1 ml-3 space-y-1 border-l border-border pl-2">
                  {s.items.map((item) => (
                    <li key={item.to}>
                      <Link
                        to={item.to}
                        className="block rounded-md px-2 py-1.5 text-sm text-fg-muted transition-colors hover:bg-primary-tint/40 hover:text-primary"
                      >
                        {item.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
