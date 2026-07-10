import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { TrendPoint } from '@/types/v0.3';

export function TrendChart({ data }: { data: TrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="run_at" tickFormatter={(v) => new Date(v).toLocaleDateString()} />
        <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
        <Tooltip
          formatter={(v: number) => `${(v * 100).toFixed(1)}%`}
          labelFormatter={(v) => new Date(v).toLocaleString()}
        />
        <Line type="monotone" dataKey="mention_rate" stroke="#2563eb" strokeWidth={2} dot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
