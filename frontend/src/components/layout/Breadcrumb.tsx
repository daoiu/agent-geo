import { Fragment } from 'react';
import { Link } from 'react-router-dom';

export interface Crumb {
  label: string;
  to?: string;
}

export interface BreadcrumbProps {
  items: Crumb[];
  className?: string;
}

/**
 * Breadcrumb — shows the current page hierarchy. Last item is the current page
 * (rendered as plain text, not a link) per ARIA recommendations.
 */
export function Breadcrumb({ items, className }: BreadcrumbProps) {
  return (
    <nav aria-label="面包屑" className={className}>
      <ol className="flex flex-wrap items-center gap-1.5 text-sm text-fg-muted">
        {items.map((c, i) => {
          const isLast = i === items.length - 1;
          return (
            <Fragment key={`${c.label}-${i}`}>
              {i > 0 && (
                <span aria-hidden="true" className="text-fg-dim">
                  /
                </span>
              )}
              <li className="flex items-center">
                {c.to && !isLast ? (
                  <Link to={c.to} className="hover:text-fg">
                    {c.label}
                  </Link>
                ) : (
                  <span aria-current={isLast ? 'page' : undefined} className="text-fg">
                    {c.label}
                  </span>
                )}
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
