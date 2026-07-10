import { cn } from '@/lib/utils';

export interface RankBadgeProps {
  /** 1-based rank. 1 = gold, 2 = silver, 3 = bronze, 4+ = neutral. */
  rank: number;
  /** Optional movement indicator relative to previous snapshot. */
  trend?: 'up' | 'down' | 'flat';
  className?: string;
}

function rankTone(rank: number): string {
  if (rank === 1) return 'bg-warning/15 text-warning border-warning/30';
  if (rank === 2) return 'bg-fg-dim/20 text-fg-muted border-border';
  if (rank === 3) return 'bg-accent/15 text-accent border-accent/30';
  return 'bg-bg-subtle text-fg-muted border-border';
}

export function RankBadge({ rank, trend, className }: RankBadgeProps) {
  return (
    <span
      aria-label={`第 ${rank} 位${trend ? ' 趋势' + trend : ''}`}
      className={cn(
        'inline-flex items-center gap-1 rounded-pill border px-2 py-0.5 text-xs font-medium',
        rankTone(rank),
        className
      )}
    >
      <span className="font-semibold tabular-nums">#{rank}</span>
      {trend === 'up' && <span aria-hidden="true">↑</span>}
      {trend === 'down' && <span aria-hidden="true">↓</span>}
      {trend === 'flat' && <span aria-hidden="true">→</span>}
    </span>
  );
}
