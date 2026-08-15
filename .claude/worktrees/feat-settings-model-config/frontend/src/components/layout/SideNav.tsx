import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';

export interface NavItem {
  key: string;
  label: string;
  icon?: ReactNode;
  to: string;
  children?: NavItem[];
}

export interface SideNavProps {
  items: NavItem[];
  className?: string;
}

function NavRow({ item }: { item: NavItem }) {
  return (
    <NavLink
      to={item.to}
      end={!item.children || item.children.length === 0}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
          isActive
            ? 'bg-primary/10 font-medium text-primary'
            : 'text-fg-muted hover:bg-bg-subtle hover:text-fg'
        )
      }
    >
      {item.icon && <span aria-hidden="true">{item.icon}</span>}
      <span>{item.label}</span>
    </NavLink>
  );
}

/**
 * SideNav — primary nav for the app. Grouped top-level items + child items.
 * Active state is route-aware via NavLink.
 */
export function SideNav({ items, className }: SideNavProps) {
  return (
    <nav
      aria-label="主导航"
      className={cn('h-full w-60 overflow-y-auto border-r border-border bg-bg p-3', className)}
    >
      <ul role="tree" className="space-y-1">
        {items.map((item) => (
          <li key={item.key} role="treeitem">
            <NavRow item={item} />
            {item.children && item.children.length > 0 && (
              <ul className="mt-1 ml-4 space-y-1 border-l border-border pl-2">
                {item.children.map((c) => (
                  <li key={c.key}>
                    <NavRow item={c} />
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}
