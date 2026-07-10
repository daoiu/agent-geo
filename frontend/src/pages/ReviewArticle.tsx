import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';

export default function ReviewArticle() {
  const { articleId = '' } = useParams<{ articleId: string }>();
  const qc = useQueryClient();
  const [rejectNote, setRejectNote] = useState('');

  const { data: article, isLoading } = useQuery({
    queryKey: ['article', articleId],
    queryFn: () => api.getArticle(articleId),
  });

  const approve = useMutation({
    mutationFn: () => api.approveArticle(articleId, rejectNote || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['article', articleId] });
      qc.invalidateQueries({ queryKey: ['review-queue'] });
    },
  });

  const reject = useMutation({
    mutationFn: () => api.rejectArticle(articleId, rejectNote),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['article', articleId] });
      qc.invalidateQueries({ queryKey: ['review-queue'] });
    },
  });

  if (isLoading) {
    return <div className="p-8 text-center text-gray-500">加载中...</div>;
  }
  if (!article) {
    return <div className="p-8 text-center text-red-500">文章不存在</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        <Link to="/reviews" className="text-blue-600 text-sm">
          ← 返回审核队列
        </Link>
        <h1 className="text-3xl font-bold text-gray-900 mt-2">
          {article.title || '（无标题）'}
        </h1>
        <div className="text-sm text-gray-500 mt-1">
          状态：{article.review_status} · 由 {article.llm_provider || '未知'}{' '}
          生成
        </div>

        {article.error_message && (
          <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">
            ⚠ {article.error_message}
          </div>
        )}

        {/* Content */}
        <div className="bg-white rounded-lg shadow p-6 mt-4">
          <div className="prose max-w-none whitespace-pre-wrap">
            {article.content || '（无内容）'}
          </div>
        </div>

        {/* Cited chunks */}
        {article.cited_chunks.length > 0 && (
          <div className="bg-blue-50 rounded-lg p-4 mt-4 text-sm text-blue-800">
            📎 引用了 {article.cited_chunks.length} 个知识库片段
          </div>
        )}

        {/* Review actions */}
        {article.review_status === 'pending' && (
          <div className="bg-white rounded-lg shadow p-6 mt-4">
            <h2 className="text-lg font-semibold mb-3">审核操作</h2>
            <textarea
              value={rejectNote}
              onChange={(e) => setRejectNote(e.target.value)}
              placeholder="审核意见（拒绝时必填）"
              className="w-full px-3 py-2 border rounded-md mb-3"
              rows={3}
            />
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => reject.mutate()}
                disabled={!rejectNote.trim() || reject.isPending}
                className="px-4 py-2 bg-red-600 text-white rounded-md disabled:opacity-50"
              >
                拒绝
              </button>
              <button
                type="button"
                onClick={() => approve.mutate()}
                disabled={approve.isPending}
                className="px-4 py-2 bg-green-600 text-white rounded-md disabled:opacity-50"
              >
                批准
              </button>
            </div>
          </div>
        )}

        {article.review_status !== 'pending' && article.review_note && (
          <div className="bg-gray-50 rounded-lg p-4 mt-4 text-sm">
            <strong>审核意见：</strong>
            {article.review_note}
          </div>
        )}
      </div>
    </div>
  );
}
