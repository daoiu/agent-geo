import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, icon, action, className }: EmptyStateProps) {
  return (
    <div
      role="status"
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-dashed bg-muted/30 px-6 py-12 text-center',
        className,
      )}
    >
      {icon && <div className="mb-4 text-muted-foreground">{icon}</div>}
      <h3 className="text-base font-medium text-foreground">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function DefaultEmptyIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 48"
      aria-hidden="true"
      className={cn('h-12 w-16 text-muted-foreground', className)}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <rect x="6" y="10" width="44" height="32" rx="4" />
      <path d="M6 22h44" />
      <circle cx="14" cy="16" r="1" fill="currentColor" />
      <circle cx="20" cy="16" r="1" fill="currentColor" />
      <path d="M52 6l8-4v8l-8-4z" />
    </svg>
  );
}
