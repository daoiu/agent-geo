import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Tooltip } from '@/components/ui/Tooltip';

export interface MentionCell {
  brand: string;
  question: string;
  provider: string;
  mentioned: boolean;
  /** 1-based position; lower = stronger mention. */
  position?: number;
  sentiment?: 'positive' | 'neutral' | 'negative' | 'none';
}

export interface MentionMatrixProps {
  cells: MentionCell[];
  brands: string[];
  questions: string[];
  providers: string[];
  className?: string;
}

function cellAriaLabel(c: MentionCell): string {
  if (!c.mentioned) return `${c.brand}·${c.question}·${c.provider} 未提及`;
  const pos = c.position ? ` 提及且位置第 ${c.position}` : ' 有提及';
  const sent = c.sentiment && c.sentiment !== 'none' ? ` 情感 ${c.sentiment}` : '';
  return `${c.brand}·${c.question}·${c.provider}${pos}${sent}`;
}

/**
 * MentionMatrix — heatmap-style visualization of brand × question × provider
 * mention results. Position-aware intensity (1st mention = highest opacity).
 * A11y: every cell has an aria-label describing the state.
 */
export function MentionMatrix({
  cells,
  brands,
  questions,
  providers,
  className,
}: MentionMatrixProps) {
  const cellMap = useMemo(() => {
    const m = new Map<string, MentionCell>();
    for (const c of cells) {
      m.set(`${c.brand}|${c.question}|${c.provider}`, c);
    }
    return m;
  }, [cells]);

  return (
    <div className={cn('overflow-x-auto', className)}>
      <table
        role="table"
        aria-label="品牌提及矩阵（按 provider 分列）"
        className="w-full border-collapse text-xs"
      >
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-bg-subtle px-2 py-1.5 text-left text-fg-muted">
              品牌
            </th>
            {questions.map((q) => (
              <th
                key={q}
                className="bg-bg-subtle px-2 py-1.5 text-center text-fg-muted"
              >
                {q}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {brands.flatMap((brand) =>
            providers.map((provider) => (
              <tr key={`${brand}-${provider}`}>
                <th
                  scope="row"
                  className="sticky left-0 z-10 bg-bg-subtle px-2 py-1 text-left font-medium text-fg"
                >
                  <div className="flex flex-col">
                    <span className="text-fg">{brand}</span>
                    <span className="text-[10px] text-fg-dim">{provider}</span>
                  </div>
                </th>
                {questions.map((q) => {
                  const cell = cellMap.get(`${brand}|${q}|${provider}`);
                  if (!cell) {
                    return (
                      <td
                        key={q}
                        className="border border-border-subtle px-1 py-1.5 text-center text-fg-dim"
                      >
                        ·
                      </td>
                    );
                  }
                  const intensity = cell.mentioned
                    ? Math.max(0.15, 1 - ((cell.position ?? 5) - 1) * 0.18)
                    : 0;
                  return (
                    <td key={q} className="border border-border-subtle p-0.5">
                      <Tooltip content={cellAriaLabel(cell)}>
                        <div
                          role="cell"
                          aria-label={cellAriaLabel(cell)}
                          className={cn(
                            'flex h-7 w-full items-center justify-center rounded-sm text-[10px] font-medium',
                            !cell.mentioned && 'bg-bg text-fg-dim',
                            cell.mentioned && cell.sentiment === 'negative' && 'bg-danger text-white',
                            cell.mentioned && (cell.sentiment === 'positive' || !cell.sentiment) && 'bg-primary text-primary-fg'
                          )}
                          style={{
                            backgroundColor: cell.mentioned
                              ? `rgba(13, 148, 136, ${intensity})`
                              : undefined,
                            color: cell.mentioned && intensity > 0.55 ? '#FFFFFF' : undefined,
                          }}
                        >
                          {cell.mentioned ? (cell.position ?? '✓') : '—'}
                        </div>
                      </Tooltip>
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
