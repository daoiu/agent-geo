import { useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface AccordionItem {
  key: string;
  title: string;
  content: ReactNode;
  defaultOpen?: boolean;
}

export interface AccordionProps {
  items: AccordionItem[];
  /** If true, allow multiple items to be open simultaneously. */
  multi?: boolean;
  className?: string;
}

/**
 * Accordion — vertical stack of collapsible items.
 * Single-open by default; pass `multi` for independent toggling.
 */
export function Accordion({ items, multi = false, className }: AccordionProps) {
  const [openSet, setOpenSet] = useState<Set<string>>(
    () =>
      new Set(
        items.filter((i) => i.defaultOpen).map((i) => i.key)
      )
  );

  const toggle = (key: string) => {
    setOpenSet((prev) => {
      const next = new Set(multi ? prev : []);
      if (prev.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  return (
    <div className={cn('divide-y divide-border rounded-md border border-border bg-bg', className)}>
      {items.map((it) => {
        const open = openSet.has(it.key);
        const headingId = `acc-${it.key}-h`;
        const panelId = `acc-${it.key}-p`;
        return (
          <div key={it.key}>
            <h3>
              <button
                id={headingId}
                aria-expanded={open}
                aria-controls={panelId}
                type="button"
                onClick={() => toggle(it.key)}
                className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-fg hover:bg-bg-subtle"
              >
                {it.title}
                <span
                  aria-hidden="true"
                  className={cn(
                    'ml-2 text-fg-muted transition-transform',
                    open && 'rotate-180'
                  )}
                >
                  ▾
                </span>
              </button>
            </h3>
            {open && (
              <div id={panelId} role="region" aria-labelledby={headingId} className="px-4 pb-4 text-sm text-fg-muted">
                {it.content}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
