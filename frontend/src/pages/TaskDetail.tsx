import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

const REVIEW_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  revise_requested: 'bg-orange-100 text-orange-800',
};

const REVIEW_STATUS_LABELS: Record<string, string> = {
  pending: '待审核',
  approved: '已批准',
  rejected: '已拒绝',
  revise_requested: '需修订',
};

export default function TaskDetail() {
  const { taskId = '' } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: task, isLoading } = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => api.getTask(taskId),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (
        status === 'completed' ||
        status === 'failed' ||
        status === 'cancelled'
      ) {
        return false;
      }
      return 3000;
    },
  });

  const cancel = useMutation({
    mutationFn: () => api.cancelTask(taskId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['task', taskId] }),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteTask(taskId),
    onSuccess: () => navigate('/tasks'),
  });

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground">加载中...</div>;
  }
  if (!task) {
    return <div className="p-8 text-center text-red-500">任务不存在</div>;
  }

  const articles = task.articles ?? [];

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-4xl mx-auto px-4">
        <Link to="/tasks" className="text-primary text-sm">
          ← 返回任务列表
        </Link>
        <h1 className="text-3xl font-bold text-foreground mt-2">{task.name}</h1>
        <p className="text-muted-foreground mt-1">主题：{task.topic}</p>
        <p className="text-sm text-muted-foreground">创建于 {formatDate(task.created_at)}</p>

        {/* Status + progress */}
        <div className="bg-white rounded-lg shadow p-4 mt-4">
          <div className="flex justify-between items-center mb-2">
            <div>
              <span className="font-medium">状态：</span>
              <span className="ml-2">{task.status}</span>
            </div>
            <div className="flex gap-2">
              {task.status === 'pending' || task.status === 'running' ? (
                <button
                  type="button"
                  onClick={() => cancel.mutate()}
                  className="px-3 py-1 text-sm bg-yellow-500 text-white rounded"
                >
                  取消任务
                </button>
              ) : null}
              {task.status !== 'running' && (
                <button
                  type="button"
                  onClick={() => {
                    if (confirm('删除此任务？文章也会被删除。')) remove.mutate();
                  }}
                  className="px-3 py-1 text-sm bg-destructive text-white rounded"
                >
                  删除
                </button>
              )}
            </div>
          </div>
          {task.status === 'running' && (
            <div className="w-full bg-accent rounded-full h-2">
              <div
                className="bg-primary h-2 rounded-full transition-all"
                style={{ width: `${task.progress}%` }}
              />
            </div>
          )}
          {task.error_message && (
            <p className="mt-2 text-sm text-destructive">⚠ {task.error_message}</p>
          )}
        </div>

        {/* Articles */}
        <div className="bg-white rounded-lg shadow mt-6">
          <h2 className="text-lg font-semibold p-4 border-b">
            文章 ({articles.length})
          </h2>
          {articles.length === 0 && (
            <p className="p-4 text-muted-foreground text-center">
              还没有文章（任务运行后会生成）
            </p>
          )}
          {articles.map((a) => (
            <Link
              key={a.id}
              to={`/reviews/${a.id}`}
              className="block p-4 border-b last:border-0 hover:bg-muted"
            >
              <div className="flex justify-between items-center">
                <div className="flex-1">
                  <div className="font-medium text-foreground">
                    {a.title || '（无标题）'}
                  </div>
                  {a.error_message ? (
                    <div className="text-sm text-destructive mt-1">
                      ⚠ {a.error_message}
                    </div>
                  ) : a.content ? (
                    <div className="text-sm text-muted-foreground mt-1">
                      {a.content.slice(0, 100)}...
                    </div>
                  ) : null}
                </div>
                <span
                  className={`text-xs px-2 py-1 rounded ${
                    REVIEW_STATUS_COLORS[a.review_status] ?? 'bg-muted'
                  }`}
                >
                  {REVIEW_STATUS_LABELS[a.review_status] ?? a.review_status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
