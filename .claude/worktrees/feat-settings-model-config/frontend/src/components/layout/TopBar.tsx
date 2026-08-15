import { Link } from 'react-router-dom';
import { Menu, Bell, Settings as SettingsIcon, Search, Sun, Moon } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface TopBarProps {
  onToggleSidebar?: () => void;
  sidebarOpen?: boolean;
  onOpenCommandPalette?: () => void;
  isDark?: boolean;
  onToggleDark?: () => void;
}

/**
 * TopBar — primary brand chrome. Logo + brand name + optional mobile hamburger.
 * Settings / notifications icons to the right.
 */
export function TopBar({
  onToggleSidebar,
  sidebarOpen,
  onOpenCommandPalette,
  isDark,
  onToggleDark,
}: TopBarProps) {
  return (
    <header className="flex h-14 items-center gap-3 border-b border-border bg-background px-4">
      {onToggleSidebar && (
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? '关闭侧边导航' : '打开侧边导航'}
          className="rounded-md p-2 text-muted-foreground hover:bg-muted md:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
      )}
      <Link
        to="/"
        className="flex items-center gap-2 text-foreground hover:text-primary"
        aria-label="返回 GEO 优化系统首页"
      >
        <Logo />
        <span className="text-base font-semibold">GEO 优化系统</span>
      </Link>
      <div className="flex-1" />
      {onOpenCommandPalette && (
        <button
          type="button"
          onClick={onOpenCommandPalette}
          aria-label="打开命令面板 (⌘K / Ctrl K)"
          className="flex items-center gap-2 rounded-md border border-border bg-muted px-3 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        >
          <Search className="h-4 w-4" />
          <span className="hidden md:inline">搜索</span>
          <kbd className="hidden md:inline rounded border border-border bg-background px-1.5 text-[10px] font-mono">
            ⌘K
          </kbd>
        </button>
      )}
      <Link
        to="/notifications"
        aria-label="通知"
        className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <Bell className="h-5 w-5" />
      </Link>
      {onToggleDark && (
        <button
          type="button"
          onClick={onToggleDark}
          aria-label={isDark ? '切换到浅色模式' : '切换到深色模式'}
          title={isDark ? '切换到浅色模式' : '切换到深色模式'}
          className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>
      )}
      <Link
        to="/settings"
        aria-label="设置"
        className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <SettingsIcon className="h-5 w-5" />
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
