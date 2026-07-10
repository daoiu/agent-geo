import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface EmptyStateProps {
  /** Headline shown above the description. */
  title: string;
  /** Secondary text explaining the empty state. */
  description?: string;
  /** Optional icon or illustration. */
  icon?: ReactNode;
  /** CTA button area. */
  action?: ReactNode;
  className?: string;
}

/**
 * EmptyState — used in lists, dashboards, and panels when there's no data yet.
 * Includes an optional icon, description, and action button to guide users.
 */
export function EmptyState({ title, description, icon, action, className }: EmptyStateProps) {
  return (
    <div
      role="status"
      className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-bg-subtle px-6 py-12 text-center',
        className
      )}
    >
      {icon && <div className="mb-4 text-fg-dim">{icon}</div>}
      <h3 className="text-base font-medium text-fg">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-fg-muted">{description}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

/**
 * Simple decorative SVG illustration used by EmptyState when no custom icon is provided.
 * Inlined to avoid extra HTTP round-trips and to support currentColor / dark-mode switches.
 */
export function DefaultEmptyIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 64 48"
      aria-hidden="true"
      className={cn('h-12 w-16 text-fg-dim', className)}
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
