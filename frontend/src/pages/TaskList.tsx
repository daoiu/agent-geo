import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-yellow-100 text-yellow-800',
};

const STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

export default function TaskList() {
  const { data: tasks, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.listTasks(),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">生成任务</h1>
          <Link
            to="/tasks/new"
            className="px-4 py-2 bg-blue-600 text-white rounded-md"
          >
            + 新建任务
          </Link>
        </div>

        {isLoading && <p className="text-gray-500">加载中...</p>}

        {tasks && tasks.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            还没有任务。
          </div>
        )}

        {tasks && tasks.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {tasks.map((t) => (
              <Link
                key={t.id}
                to={`/tasks/${t.id}`}
                className="block p-4 hover:bg-gray-50"
              >
                <div className="flex justify-between items-start mb-1">
                  <div className="font-medium text-gray-900">{t.name}</div>
                  <span
                    className={`text-xs px-2 py-1 rounded ${STATUS_COLORS[t.status]}`}
                  >
                    {STATUS_LABELS[t.status]}
                  </span>
                </div>
                <div className="text-sm text-gray-500">
                  主题：{t.topic.slice(0, 50)} · 文章数 {t.article_count} ·{' '}
                  {formatDate(t.created_at)}
                </div>
                {t.status === 'running' && (
                  <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full"
                      style={{ width: `${t.progress}%` }}
                    />
                  </div>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
