import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';
import { TrendChart } from '@/components/TrendChart';
import { formatDate } from '@/lib/utils';
import type { MonitorTask, TrendData } from '@/types/v0.3';

export default function MonitorDetail() {
  const { monitorId = '' } = useParams<{ monitorId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: monitor } = useQuery<MonitorTask>({
    queryKey: ['monitor', monitorId],
    queryFn: async () => {
      const resp = await fetch(`/api/monitors/${monitorId}`);
      if (!resp.ok) throw new Error('Failed to fetch monitor');
      return resp.json();
    },
  });

  const { data: trends } = useQuery<TrendData>({
    queryKey: ['monitor-trends', monitorId],
    queryFn: () => api.getMonitorTrends(monitorId, 30),
  });

  const runNow = useMutation({
    mutationFn: () => api.runMonitorNow(monitorId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['monitor-trends', monitorId] }),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteMonitor(monitorId),
    onSuccess: () => navigate('/monitors'),
  });

  if (!monitor) return <div className="p-8 text-center text-muted-foreground">加载中...</div>;

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-4xl mx-auto px-4">
        <Link to="/monitors" className="text-primary text-sm">← 返回监测列表</Link>
        <h1 className="text-3xl font-bold text-foreground mt-2">{monitor.name}</h1>
        <p className="text-muted-foreground mt-1">{monitor.brand} · {monitor.industry}</p>

        <div className="bg-white rounded-lg shadow p-4 mt-4 flex justify-between items-center">
          <div>
            <div>状态：{monitor.is_active ? '运行中' : '已暂停'}</div>
            <div className="text-sm text-muted-foreground">
              频率：{monitor.frequency} · 阈值：{(monitor.change_threshold * 100).toFixed(0)}%
              {monitor.last_run_at && ` · 上次：${formatDate(monitor.last_run_at)}`}
            </div>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => runNow.mutate()} disabled={runNow.isPending}
              className="px-3 py-1 text-sm bg-blue-500 text-white rounded disabled:opacity-50">
              立即跑
            </button>
            <button type="button" onClick={() => { if (confirm('删除此监测任务？')) remove.mutate(); }}
              className="px-3 py-1 text-sm bg-destructive text-white rounded">
              删除
            </button>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 mt-4">
          <h2 className="text-lg font-semibold mb-3">趋势 (近 30 天)</h2>
          {trends && trends.points.length > 0 ? (
            <TrendChart data={trends.points} />
          ) : (
            <p className="text-muted-foreground text-center py-8">还没有数据</p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-6 mt-4">
          <h2 className="text-lg font-semibold mb-3">问题</h2>
          <ul className="list-disc list-inside space-y-1 text-sm">
            {monitor.target_questions.map((q: string, i: number) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
