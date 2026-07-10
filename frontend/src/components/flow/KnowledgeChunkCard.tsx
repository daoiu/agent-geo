import { cn } from '@/lib/utils';

export interface KnowledgeChunkCardProps {
  title: string;
  /** First ~80 chars of the chunk, used as preview. */
  preview: string;
  /** Source label, e.g. "白皮书 P.12" or "小米官网 /news". */
  source: string;
  /** Hybrid search score (0..1) — surfaced from v0.5 RRF. */
  hybridScore?: number;
  /** Number of articles that cite this chunk. */
  citedIn?: number;
  onClick?: () => void;
  className?: string;
}

/**
 * KnowledgeChunkCard — single retrieved chunk in the knowledge base.
 * Surfaces v0.5 hybrid search scoring and downstream citation count.
 */
export function KnowledgeChunkCard({
  title,
  preview,
  source,
  hybridScore,
  citedIn,
  onClick,
  className,
}: KnowledgeChunkCardProps) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      onClick={onClick}
      className={cn(
        'w-full rounded-lg border border-border bg-bg p-4 text-left shadow-card transition-colors',
        onClick && 'hover:border-primary focus:outline-none focus-visible:border-primary cursor-pointer',
        className
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-medium text-fg">{title}</h3>
          <p className="mt-1 line-clamp-2 text-xs text-fg-muted">{preview}</p>
        </div>
        {typeof hybridScore === 'number' && (
          <div className="flex shrink-0 flex-col items-end">
            <span className="text-[10px] uppercase tracking-wider text-fg-dim">
              检索分
            </span>
            <span
              aria-label={`检索分 ${hybridScore.toFixed(2)}`}
              className="text-sm font-semibold tabular-nums text-primary"
            >
              {hybridScore.toFixed(2)}
            </span>
          </div>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-fg-dim">
        <span className="truncate">{source}</span>
        {typeof citedIn === 'number' && (
          <span aria-label={`在 ${citedIn} 篇文章中被引用`}>
            引用 {citedIn} 篇
          </span>
        )}
      </div>
    </Tag>
  );
}
