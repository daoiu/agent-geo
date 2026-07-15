import { useMemo, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { GlobalKnowledgeSearchResult } from '@/types/v0.2';
import { cn } from '@/lib/utils';

/**
 * v0.7 KnowledgeChunkGrid — virtualised grid for cross-KB search
 * results.  Uses `@tanstack/react-virtual` (the only new dep added
 * during v0.7) so we can scroll through thousands of chunks without
 * DOM bloat.
 *
 * The component is intentionally minimal: it receives a fully-fetched
 * `GlobalKnowledgeSearchResult` and renders a 3-column responsive grid;
 * search debouncing lives in the page wrapper.
 */

export interface KnowledgeChunkGridProps {
  result: GlobalKnowledgeSearchResult;
  className?: string;
}

const COLUMN_CLASS = 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3';

export function KnowledgeChunkGrid({ result, className }: KnowledgeChunkGridProps) {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const ROW_HEIGHT = 200; // px — approximate chunk card height

  // Virtualization is row-based; on lg+ we want 3 columns ⇒ each row is 3 chunks.
  // The parentRef width + a column-aware rowHeight gives an over-estimate;
  // simpler approach is one row = one chunk stacked, which keeps height stable.
  const rowVirtualizer = useVirtualizer({
    count: result.hits.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 5,
  });

  const rows = useMemo(
    () => rowVirtualizer.getVirtualItems(),
    [rowVirtualizer],
  );

  return (
    <div
      ref={parentRef}
      data-testid="knowledge-chunk-grid"
      className={cn(
        'h-[640px] overflow-y-auto rounded-xl border border-glass-border bg-bg-subtle p-4',
        className,
      )}
    >
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {rows.map((virtualRow) => {
          const chunk = result.hits[virtualRow.index];
          if (!chunk) return null;
          return (
            <div
              key={`${chunk.kb_id}:${chunk.doc_id}:${chunk.chunk_id}`}
              className="absolute inset-x-0 px-1 pb-3"
              style={{
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <article className="rounded-lg bg-card p-4 shadow-card transition-shadow duration-400 ease-spring-gentle hover:shadow-popover">
                <h3 className="line-clamp-1 text-sm font-semibold text-fg">
                  {chunk.doc_filename} #{chunk.chunk_index}
                </h3>
                <p className="mt-1 line-clamp-3 text-xs text-fg-muted">
                  {chunk.content}
                </p>
                <div className="mt-2 flex items-center justify-between text-[11px] text-fg-muted">
                  <span>{chunk.kb_name}</span>
                  <span className="tabular-nums">
                    score {chunk.score.toFixed(2)}
                  </span>
                </div>
              </article>
            </div>
          );
        })}
      </div>
      {result.hits.length === 0 && (
        <p className="mt-12 text-center text-sm text-fg-muted">
          跨库检索没有命中,可以换一个更具体的问题试试。
        </p>
      )}
      {/* Hint: Column helper class is not actually used because we're
          virtualising rows of 1 chunk; the helper is exported for
          non-virtualised lists in the same module. */}
      <span className={cn('hidden', COLUMN_CLASS)} aria-hidden="true" />
    </div>
  );
}
