import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

/**
 * v0.7 HarmonyOS SectionCardGrid — 12-col responsive card grid for
 * section home pages (诊断首页 / 知识首页 / etc.). Each card carries an
 * optional icon, title, one-line description, and optional badge.
 *
 * Tiles lift on hover via shadow-card → shadow-popover with the
 * spring-gentle easing declared in tailwind.config.
 */

export interface SectionCard {
  to: string;
  title: string;
  description: string;
  icon?: ReactNode;
  badge?: string;
}

export interface SectionCardGridProps {
  cards: SectionCard[];
  className?: string;
}

export function SectionCardGrid({ cards, className }: SectionCardGridProps) {
  return (
    <div
      className={
        'grid grid-cols-1 gap-4 p-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 ' +
        (className ?? '')
      }
    >
      {cards.map((c) => (
        <Link
          key={c.to}
          to={c.to}
          className="group block rounded-xl bg-card p-6 shadow-card transition-[box-shadow,transform] duration-400 ease-spring-gentle hover:-translate-y-0.5 hover:shadow-popover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          aria-label={c.title}
          data-testid={`section-card-${c.title}`}
        >
          <div className="flex items-start gap-3">
            {c.icon && (
              <div className="text-primary transition-colors group-hover:text-primary">
                {c.icon}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-base font-semibold leading-tight text-fg">{c.title}</h3>
                {c.badge && (
                  <span className="rounded-pill bg-primary-tint px-2 py-0.5 text-xs text-primary">
                    {c.badge}
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-fg-muted">{c.description}</p>
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
