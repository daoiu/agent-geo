import { useEffect, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children?: ReactNode;
  widthClassName?: string; // e.g. 'w-80'
}

/**
 * Drawer — right-side slide-in panel for context / detail panes.
 * Backdrop click closes; ESC closes via document listener.
 */
export function Drawer({ open, onClose, title, children, widthClassName = 'w-96' }: DrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true">
      <button
        aria-label="关闭抽屉"
        onClick={onClose}
        className="absolute inset-0 bg-fg/40"
      />
      <aside
        className={cn(
          'relative z-50 h-full bg-bg shadow-popover overflow-y-auto',
          'animate-[slideInRight_200ms_ease-out]',
          widthClassName
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-base font-semibold text-fg">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="text-fg-muted hover:text-fg"
          >
            ✕
          </button>
        </div>
        <div className="px-6 py-4">{children}</div>
      </aside>
    </div>
  );
}
