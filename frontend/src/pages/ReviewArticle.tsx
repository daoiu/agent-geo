import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { api } from '@/api/client';
import { stripMarkdown } from '@/lib/markdown';
import { formatDate } from '@/lib/utils';
import { Button } from '@/components/ui/button';

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

  async function copyToClipboard(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`已复制：${label}`);
    } catch {
      toast.error('复制失败，请手动选中复制');
    }
  }

  function handleCopyMarkdown() {
    if (!article?.content) return;
    void copyToClipboard(article.content, 'Markdown 全文');
  }

  function handleCopyPlain() {
    if (!article?.content) return;
    void copyToClipboard(stripMarkdown(article.content), '纯文本');
  }

  function handleDownload() {
    if (!article?.content) return;
    // 用 Blob + a 元素触发下载（不依赖后端 /articles/{id}/download）
    const title = article.title || '未命名文章';
    const safe = title.replace(/[\\/:*?"<>|\r\n\t]/g, '_').slice(0, 60);
    const filename = `${articleId.slice(0, 8)}-${safe}.md`;
    const blob = new Blob([article.content], {
      type: 'text/markdown;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success(`已下载：${filename}`);
  }

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground">加载中...</div>;
  }
  if (!article) {
    return <div className="p-8 text-center text-red-500">文章不存在</div>;
  }

  // 把 content 里第一行 H1 抽出来当"显示标题"，body 里再剥掉
  const bodyWithoutTitle = stripFirstH1(article.content);

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-3xl mx-auto px-4">
        {/* 返回链：根据来源（task 详情 / 审核队列）智能判断 */}
        <Link
          to={`/tasks/${article.task_id}`}
          className="text-primary text-sm"
        >
          ← 返回任务详情
        </Link>

        {/* 状态 meta */}
        <div className="text-sm text-muted-foreground mt-1">
          状态：{article.review_status} · 由 {article.llm_provider || '未知'}{' '}
          生成 · 创建于 {formatDate(article.created_at)}
        </div>

        {article.error_message && (
          <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">
            ⚠ {article.error_message}
          </div>
        )}

        {/* 标题区（H1 独立显示，大字 + teal 强调线） */}
        <header className="mt-6 pb-4 border-b-2 border-primary">
          <h1 className="text-3xl font-bold text-foreground">
            {article.title || '（无标题）'}
          </h1>
        </header>

        {/* 操作按钮区 */}
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopyMarkdown}
            disabled={!article.content}
          >
            📋 复制全文（Markdown）
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopyPlain}
            disabled={!article.content}
          >
            📄 复制纯文本
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownload}
            disabled={!article.content}
          >
            ⬇ 下载 .md
          </Button>
        </div>

        {/* 正文区（剥掉首行 H1，剩下按 Markdown 渲染） */}
        <article className="bg-white rounded-lg shadow p-6 mt-6">
          {article.content ? (
            <div className="prose prose-slate max-w-none whitespace-pre-wrap">
              {bodyWithoutTitle}
            </div>
          ) : (
            <p className="text-muted-foreground">（无内容）</p>
          )}
        </article>

        {/* 引用提示 */}
        {article.cited_chunks.length > 0 && (
          <div className="bg-accent rounded-lg p-4 mt-4 text-sm text-blue-800">
            📎 引用了 {article.cited_chunks.length} 个知识库片段
          </div>
        )}

        {/* 审核操作 */}
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
          <div className="bg-muted rounded-lg p-4 mt-4 text-sm">
            <strong>审核意见：</strong>
            {article.review_note}
          </div>
        )}
      </div>
    </div>
  );
}

/** 剥离第一行 H1（如果有），返回剩余内容。 */
function stripFirstH1(content: string | null | undefined): string {
  if (!content) return '';
  const m = content.match(/^#\s+.+\n+/);
  if (!m) return content;
  return content.slice(m[0].length);
}