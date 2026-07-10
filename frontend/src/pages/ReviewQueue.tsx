import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

const STATUS_LABELS: Record<string, string> = {
  pending: '待审核',
  approved: '已批准',
  rejected: '已拒绝',
  revise_requested: '需修订',
};

export default function ReviewQueue() {
  const [filter, setFilter] = useState<'pending' | 'approved' | 'rejected'>(
    'pending',
  );
  const { data: articles, isLoading } = useQuery({
    queryKey: ['review-queue', filter],
    queryFn: () => api.listReviewQueue(filter),
  });

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-4xl mx-auto px-4"><div className="flex gap-2 mb-4">
          {(['pending', 'approved', 'rejected'] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setFilter(s)}
              className={`px-4 py-2 rounded-md ${
                filter === s ? 'bg-primary text-white' : 'bg-white border'
              }`}
            >
              {STATUS_LABELS[s]}
            </button>
          ))}
        </div>

        {isLoading && <p className="text-muted-foreground">加载中...</p>}

        {articles && articles.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-muted-foreground">
            {filter === 'pending' ? '没有待审核的文章' : '没有记录'}
          </div>
        )}

        {articles && articles.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {articles.map((a) => (
              <Link
                key={a.id}
                to={`/reviews/${a.id}`}
                className="block p-4 hover:bg-muted"
              >
                <div className="font-medium text-foreground">
                  {a.title || '（无标题）'}
                </div>
                <div className="text-sm text-muted-foreground mt-1">
                  {a.content ? a.content.slice(0, 120) + '...' : '（无内容）'}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {formatDate(a.created_at)}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
