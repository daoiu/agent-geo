import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-muted text-foreground',
  running: 'bg-accent text-blue-800',
  success: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-yellow-100 text-yellow-800',
};

const STATUS_LABELS: Record<string, string> = {
  pending: '等待中', running: '发布中', success: '已发布', failed: '失败', cancelled: '已取消',
};

export default function PublishList() {
  const { data: jobs, isLoading } = useQuery({
    queryKey: ['publish-jobs'],
    queryFn: () => api.listPublishJobs(),
  });

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-4xl mx-auto px-4">
        <h1 className="text-3xl font-bold text-foreground mb-6">发布任务</h1>
        {isLoading && <p className="text-muted-foreground">加载中...</p>}
        {jobs && jobs.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-muted-foreground">
            还没有发布任务。<br />
            <span className="text-sm">从 v0.2 审核通过的 Article 创建发布任务</span>
          </div>
        )}
        {jobs && jobs.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {jobs.map((j) => (
              <div key={j.id} className="p-4 flex justify-between items-center">
                <div>
                  <div className="text-sm text-muted-foreground">文章 ID: {j.article_id}</div>
                  <div className="text-xs text-muted-foreground">{formatDate(j.created_at)}</div>
                  {j.remote_url && <a href={j.remote_url} target="_blank" rel="noopener" className="text-xs text-primary">{j.remote_url}</a>}
                </div>
                <span className={`text-xs px-2 py-1 rounded ${STATUS_COLORS[j.status]}`}>
                  {STATUS_LABELS[j.status]}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
