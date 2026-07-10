import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

export interface TopBarProps {
  onToggleSidebar?: () => void;
  sidebarOpen?: boolean;
}

/**
 * TopBar — primary brand chrome. Logo + brand name + optional mobile hamburger.
 * Settings / notifications icons to the right.
 */
export function TopBar({ onToggleSidebar, sidebarOpen }: TopBarProps) {
  return (
    <header className="flex h-14 items-center gap-3 border-b border-border bg-bg px-4">
      {onToggleSidebar && (
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? '关闭侧边导航' : '打开侧边导航'}
          className="rounded-md p-2 text-fg-muted hover:bg-bg-subtle md:hidden"
        >
          ☰
        </button>
      )}
      <Link
        to="/"
        className="flex items-center gap-2 text-fg hover:text-primary"
        aria-label="返回 GEO 优化系统首页"
      >
        <Logo />
        <span className="text-base font-semibold">GEO 优化系统</span>
      </Link>
      <div className="flex-1" />
      <Link
        to="/notifications"
        aria-label="通知"
        className="rounded-md p-2 text-fg-muted hover:bg-bg-subtle hover:text-fg"
      >
        🔔
      </Link>
      <Link
        to="/settings"
        aria-label="设置"
        className="rounded-md p-2 text-fg-muted hover:bg-bg-subtle hover:text-fg"
      >
        ⚙
      </Link>
    </header>
  );
}

function Logo() {
  return (
    <svg
      viewBox="0 0 24 24"
      className={cn('h-6 w-6 text-primary')}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="3" fill="currentColor" />
      <circle cx="12" cy="3" r="1.5" fill="currentColor" />
      <circle cx="20" cy="7" r="1.5" fill="currentColor" />
      <circle cx="20" cy="17" r="1.5" fill="currentColor" />
      <circle cx="12" cy="21" r="1.5" fill="currentColor" />
      <circle cx="4" cy="17" r="1.5" fill="currentColor" />
      <circle cx="4" cy="7" r="1.5" fill="currentColor" />
    </svg>
  );
}
