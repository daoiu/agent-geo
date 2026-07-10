import { useEffect, useRef, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children?: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  footer?: ReactNode;
}

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-2xl',
};

/**
 * Modal — uses the native HTML5 `<dialog>` element for focus trap + ESC handling.
 * Backdrop click closes the modal. Returns null when not open.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  size = 'md',
  className,
  children,
  footer,
}: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) {
      try {
        el.showModal();
      } catch {
        /* already open */
      }
    } else if (!open && el.open) {
      el.close();
    }
  }, [open]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const handleCancel = (e: Event) => {
      e.preventDefault();
      onClose();
    };
    el.addEventListener('cancel', handleCancel);
    return () => el.removeEventListener('cancel', handleCancel);
  }, [onClose]);

  if (!open) return null;

  return (
    <dialog
      ref={ref}
      aria-label={title || '对话框'}
      onClick={(e) => {
        // close on backdrop click
        if (e.target === ref.current) onClose();
      }}
      className={cn(
        'rounded-lg border border-border bg-bg p-0 shadow-popover',
        'backdrop:bg-fg/40',
        sizeClasses[size],
        'w-full m-auto',
        className
      )}
    >
      <div className="p-6">
        {title && <h2 className="text-lg font-semibold text-fg">{title}</h2>}
        {description && (
          <p className="mt-1 text-sm text-fg-muted">{description}</p>
        )}
        <div className="mt-4">{children}</div>
      </div>
      {footer && (
        <div className="flex items-center justify-end gap-2 border-t border-border bg-bg-subtle px-6 py-4 rounded-b-lg">
          {footer}
        </div>
      )}
    </dialog>
  );
}
