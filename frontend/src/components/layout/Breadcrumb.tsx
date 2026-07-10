import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface Crumb {
  label: string;
  to?: string;
  /** Optional subtitle shown under the page title in a muted style. */
  description?: string;
}

export interface BreadcrumbProps {
  items: Crumb[];
  className?: string;
}

/**
 * Breadcrumb — page-level navigation with the **last item styled as the page
 * H1**. This is the canonical page title and the primary visual anchor on
 * every page — every page route should rely on this rather than rendering
 * its own h1.
 *
 * Intermediate items are smaller and muted (the "trail"); the final item
 * is rendered with `aria-current="page"` and heavier weight.
 */
export function Breadcrumb({ items, className }: BreadcrumbProps) {
  const last = items[items.length - 1];
  const trail = items.slice(0, -1);

  return (
    <nav aria-label="面包屑" className={cn('flex flex-col gap-1', className)}>
      {trail.length > 0 && (
        <ol className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          {trail.map((c, i) => (
            <Fragment key={`${c.label}-${i}`}>
              {i > 0 && (
                <ChevronRight aria-hidden="true" className="h-3 w-3 text-fg-dim" />
              )}
              <li className="flex items-center">
                {c.to ? (
                  <Link
                    to={c.to}
                    className="rounded-sm transition-colors hover:text-foreground"
                  >
                    {c.label}
                  </Link>
                ) : (
                  <span className="text-foreground/70">{c.label}</span>
                )}
              </li>
            </Fragment>
          ))}
          <li aria-hidden="true" className="flex items-center">
            <ChevronRight className="h-3 w-3 text-fg-dim" />
          </li>
        </ol>
      )}
      <h1
        aria-current="page"
        className="text-2xl font-semibold tracking-tight text-foreground"
      >
        {last?.label ?? ' '}
      </h1>
      {last?.description && (
        <p className="text-sm text-muted-foreground">{last.description}</p>
      )}
    </nav>
  );
}
