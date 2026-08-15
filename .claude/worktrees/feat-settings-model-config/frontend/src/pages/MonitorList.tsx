import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

const FREQ_LABELS: Record<string, string> = { hourly: '每小时', daily: '每天', weekly: '每周' };

export default function MonitorList() {
  const { data: monitors, isLoading } = useQuery({
    queryKey: ['monitors'],
    queryFn: () => api.listMonitors(),
  });

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6"><Link to="/monitors/new" className="px-4 py-2 bg-primary text-white rounded-md">
            + 新建监测
          </Link>
        </div>

        {isLoading && <p className="text-muted-foreground">加载中...</p>}

        {monitors && monitors.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-muted-foreground">
            还没有监测任务。
          </div>
        )}

        {monitors && monitors.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {monitors.map((m) => (
              <Link
                key={m.id}
                to={`/monitors/${m.id}`}
                className="block p-4 hover:bg-muted"
              >
                <div className="flex justify-between items-center">
                  <div>
                    <div className="font-medium text-foreground">{m.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {m.brand} · {FREQ_LABELS[m.frequency]}
                      {m.is_active ? '' : ' · 已暂停'}
                    </div>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {m.last_run_at ? `上次：${formatDate(m.last_run_at)}` : '未运行'}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
