import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { costApi } from '@/api/cost';
import type { CostByMonth } from '@/types/v0.7';
import { cn } from '@/lib/utils';

/**
 * v0.7 CostDashboard — monthly LLM cost breakdown (spec §7.1).
 *
 * Three visualizations sharing one CostByMonth payload:
 *   1. AreaChart — month-by-month totalCost trend (large)
 *   2. PieChart — by provider split (Anthropic / OpenAI / ...)
 *   3. PieChart — by model split (claude-opus-4-8 / ...)
 *
 * + Detailed sortable table with CSV export.
 */

const RANGE_OPTIONS = [
  { value: '6', label: '最近 6 月' },
  { value: '12', label: '最近 12 月' },
  { value: '24', label: '最近 24 月' },
] as const;

const PIE_COLORS = ['#0A59F7', '#34D77F', '#FF7A45', '#A8B0FF', '#E54552', '#2675F8', '#E8F0FE'];

function monthsBack(n: number): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  from.setMonth(from.getMonth() - n);
  const fmt = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  return { from: fmt(from), to: fmt(to) };
}

/**
 * CSV shape — one row per (month × item), with an explicit `type`
 * column so downstream scripts don't have to rely on which side
 * (provider vs model) is empty.
 */
type CsvItemType = 'provider' | 'model';
const CSV_HEADERS = ['month', 'type', 'name', 'cost'] as const;

function csvCell(value: string | number): string {
  const s = String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function csvOf(data: CostByMonth): string {
  const rows: string[] = [CSV_HEADERS.join(',')];
  for (const m of data.months) {
    for (const p of m.byProvider) {
      rows.push(
        [m.month, 'provider' as CsvItemType, p.provider, p.cost.toFixed(4)]
          .map(csvCell)
          .join(','),
      );
    }
    for (const mm of m.byModel) {
      rows.push(
        [m.month, 'model' as CsvItemType, mm.model, mm.cost.toFixed(4)]
          .map(csvCell)
          .join(','),
      );
    }
  }
  return rows.join('\n');
}

export interface CostDashboardProps {
  className?: string;
}

export function CostDashboard({ className }: CostDashboardProps) {
  const [range, setRange] = useState<string>('6');
  const rangeMonths = Number.parseInt(range, 10);
  const { from, to } = useMemo(() => monthsBack(rangeMonths), [rangeMonths]);

  const costQ = useQuery({
    queryKey: ['cost-by-month', from, to],
    queryFn: () => costApi.byMonth(from, to),
  });

  // Latest month for breakdown pies
  const latest = costQ.data?.months.at(-1);

  return (
    <section
      aria-label="月度成本"
      className={cn('flex flex-col gap-6 p-6', className)}
    >
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold text-fg">月度成本</h1>
        <div role="tablist" aria-label="时间范围" className="flex gap-2">
          {RANGE_OPTIONS.map((o) => (
            <button
              key={o.value}
              role="tab"
              aria-selected={range === o.value}
              onClick={() => setRange(o.value)}
              className={cn(
                'rounded-md px-3 py-1 text-sm transition-colors duration-400 ease-spring-gentle',
                range === o.value
                  ? 'bg-primary-tint text-primary'
                  : 'text-fg-muted hover:bg-primary-tint/50',
              )}
            >
              {o.label}
            </button>
          ))}
        </div>
      </header>

      {costQ.isLoading && (
        <p className="text-sm text-fg-muted">加载中…</p>
      )}
      {costQ.isError && (
        <p className="text-sm text-danger">加载失败,{String(costQ.error)}</p>
      )}

      {costQ.data && (
        <>
          <article
            aria-label="趋势"
            className="rounded-xl bg-card p-6 shadow-card"
          >
            <h2 className="mb-4 text-base font-semibold text-fg">月度总成本</h2>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={costQ.data.months}>
                <defs>
                  <linearGradient id="costFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#0A59F7" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#0A59F7" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(0,0,0,0.06)" vertical={false} />
                <XAxis dataKey="month" stroke="#6B7280" />
                <YAxis stroke="#6B7280" />
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: '1px solid rgba(255,255,255,0.18)' }}
                  formatter={(v: number) => `$${v.toFixed(2)}`}
                />
                <Area
                  type="monotone"
                  dataKey="totalCost"
                  stroke="#0A59F7"
                  strokeWidth={2}
                  fill="url(#costFill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </article>

          {latest && (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <article className="rounded-xl bg-card p-6 shadow-card">
                <h2 className="mb-4 text-base font-semibold text-fg">
                  {latest.month} · 按 Provider 拆分
                </h2>
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie
                      data={latest.byProvider}
                      dataKey="cost"
                      nameKey="provider"
                      innerRadius={50}
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {latest.byProvider.map((_, i) => (
                        <Cell
                          key={i}
                          fill={PIE_COLORS[i % PIE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Legend />
                    <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
                  </PieChart>
                </ResponsiveContainer>
              </article>

              <article className="rounded-xl bg-card p-6 shadow-card">
                <h2 className="mb-4 text-base font-semibold text-fg">
                  {latest.month} · 按 Model 拆分
                </h2>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={latest.byModel}>
                    <CartesianGrid stroke="rgba(0,0,0,0.06)" vertical={false} />
                    <XAxis dataKey="model" stroke="#6B7280" />
                    <YAxis stroke="#6B7280" />
                    <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
                    <Bar dataKey="cost" fill="#0A59F7" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </article>
            </div>
          )}

          <article className="rounded-xl bg-card p-6 shadow-card">
            <header className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold text-fg">明细</h2>
              <button
                type="button"
                onClick={() => {
                  const blob = new Blob([csvOf(costQ.data)], {
                    type: 'text/csv;charset=utf-8',
                  });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `cost-${from}-to-${to}.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="rounded-md bg-primary-tint px-3 py-1.5 text-sm text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
              >
                导出 CSV
              </button>
            </header>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-fg-muted">
                    <th className="px-2 py-1">月份</th>
                    <th className="px-2 py-1">Provider</th>
                    <th className="px-2 py-1">Model</th>
                    <th className="px-2 py-1 text-right">成本 (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {costQ.data.months.flatMap((m) => [
                    ...m.byProvider.map((p) => (
                      <tr key={`${m.month}-p-${p.provider}`} className="border-b">
                        <td className="px-2 py-1">{m.month}</td>
                        <td className="px-2 py-1">{p.provider}</td>
                        <td className="px-2 py-1 text-fg-muted">—</td>
                        <td className="px-2 py-1 text-right tabular-nums">
                          ${p.cost.toFixed(4)}
                        </td>
                      </tr>
                    )),
                    ...m.byModel.map((mm) => (
                      <tr key={`${m.month}-m-${mm.model}`} className="border-b">
                        <td className="px-2 py-1">{m.month}</td>
                        <td className="px-2 py-1 text-fg-muted">—</td>
                        <td className="px-2 py-1">{mm.model}</td>
                        <td className="px-2 py-1 text-right tabular-nums">
                          ${mm.cost.toFixed(4)}
                        </td>
                      </tr>
                    )),
                  ])}
                </tbody>
              </table>
            </div>
          </article>
        </>
      )}
    </section>
  );
}
