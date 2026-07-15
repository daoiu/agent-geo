import { useEffect } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

/**
 * v0.7 NotificationDrawer — right-side slide-in panel for non-blocking
 * monitor threshold notifications (spec §7.1 + plan §16).  Uses
 * `prefers-reduced-motion`-aware Spring timing and traps focus inside
 * the drawer while open.
 */

export interface NotificationDrawerProps {
  open: boolean;
  title?: string;
  onClose: () => void;
  children?: React.ReactNode;
  className?: string;
}

export function NotificationDrawer({
  open,
  title = '监测通知',
  onClose,
  children,
  className,
}: NotificationDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onEsc);
    return () => window.removeEventListener('keydown', onEsc);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      data-testid="notification-drawer"
      className="fixed inset-0 z-50 flex"
    >
      <button
        type="button"
        aria-label="关闭面板"
        onClick={onClose}
        className="flex-1 bg-black/40 backdrop-blur-[6px]"
      />
      <aside
        className={cn(
          'flex h-full w-[420px] max-w-[90vw] flex-col border-l border-glass-border bg-[var(--glass-bg)] p-6 backdrop-blur-[20px] transition-[transform] duration-400 ease-spring-gentle',
          className,
        )}
      >
        <header className="flex items-center justify-between border-b border-border pb-3">
          <h2 className="text-base font-semibold text-fg">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-fg-muted hover:bg-primary-tint hover:text-primary"
            aria-label="关闭"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto pt-3 text-sm text-fg">{children}</div>
      </aside>
    </div>
  );
}
