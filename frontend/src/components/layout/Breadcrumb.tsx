import { cn } from '@/lib/utils';

export interface Crumb {
  label: string;
  to?: string;
  /** Optional subtitle shown under the page title. */
  description?: string;
}

export interface BreadcrumbProps {
  items: Crumb[];
  className?: string;
}

/**
 * PageHeader — replaces the old multi-level breadcrumb. Renders **only**
 * the current page as a single H1 (with optional subtitle). The full
 * hierarchy lives in the left SideNav, so there's no need to repeat
 * the trail here.
 *
 * Backed by the same `Crumb` type for API symmetry, but only the last
 * item is rendered. Pass an array with length ≥ 1.
 */
export function Breadcrumb({ items, className }: BreadcrumbProps) {
  const last = items[items.length - 1];

  return (
    <div className={cn('flex flex-col gap-1', className)} aria-label="页面标题">
      <h1
        aria-current="page"
        className="text-2xl font-semibold tracking-tight text-foreground"
      >
        {last?.label ?? ' '}
      </h1>
      {last?.description && (
        <p className="text-sm text-muted-foreground">{last.description}</p>
      )}
    </div>
  );
}
