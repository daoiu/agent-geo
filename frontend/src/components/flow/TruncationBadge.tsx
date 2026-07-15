/**
 * v0.7 TruncationBadge — surfaces an LLM-context compression decision to the
 * user. Four strategies (spec §7.5) each get a distinct HarmonyOS color:
 *
 *   noop       → gray       (no action taken)
 *   truncate   → primary    (cut the message tail)
 *   drop       → warning    (drop oldest messages)
 *   summarize  → accent     (replace block with summary)
 *
 * The `savedTokens` count is shown as "节省 N.Nk tokens" with one decimal of
 * precision, except `noop` which shows "压缩无需" alone.
 *
 * `TruncationStrategy` lives in `@/types/v0.7`; re-exported here so the
 * existing surface API (`./TruncationBadge` + its tests) stays stable.
 */

import type { TruncationStrategy as TruncationStrategyType } from '@/types/v0.7';

export type TruncationStrategy = TruncationStrategyType;

const LABELS: Record<TruncationStrategy, string> = {
  noop: '压缩无需',
  truncate: '截断',
  drop: '丢弃',
  summarize: '摘要',
};

const CLASSES: Record<TruncationStrategy, string> = {
  noop: 'bg-gray-100 text-gray-600',
  truncate: 'bg-primary-tint text-primary',
  drop: 'bg-warning/20 text-warning',
  summarize: 'bg-accent/30 text-accent',
};

export function TruncationBadge({
  strategy,
  savedTokens,
}: {
  strategy: TruncationStrategy;
  savedTokens: number;
}) {
  if (strategy === 'noop') {
    return (
      <span
        className={`rounded-md px-2 py-1 text-xs ${CLASSES.noop}`}
        data-testid="truncation-badge"
      >
        {LABELS.noop}
      </span>
    );
  }
  return (
    <span
      className={`rounded-md px-2 py-1 text-xs ${CLASSES[strategy]}`}
      data-testid="truncation-badge"
    >
      {LABELS[strategy]} · 节省 {(savedTokens / 1000).toFixed(1)}k tokens
    </span>
  );
}
