import { useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

const PARSE_STATUS_LABELS: Record<string, string> = {
  pending: '解析中',
  success: '已就绪',
  failed: '失败',
};

const PARSE_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  success: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
};

export default function KnowledgeDetail() {
  const { kbId = '' } = useParams<{ kbId: string }>();
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: kb, isLoading } = useQuery({
    queryKey: ['knowledge-base', kbId],
    queryFn: () => api.getKnowledgeBase(kbId),
  });

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadDocument(kbId, file),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['knowledge-base', kbId] }),
  });

  const remove = useMutation({
    mutationFn: (docId: string) => api.deleteDocument(kbId, docId),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['knowledge-base', kbId] }),
  });

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground">加载中...</div>;
  }
  if (!kb) {
    return <div className="p-8 text-center text-red-500">知识库不存在</div>;
  }

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-4xl mx-auto px-4">
        <Link to="/knowledge" className="text-primary text-sm">
          ← 返回知识库列表
        </Link>
        <h1 className="text-3xl font-bold text-foreground mt-2 mb-2">{kb.name}</h1>
        {kb.description && (
          <p className="text-muted-foreground mb-6">{kb.description}</p>
        )}

        {/* Upload area */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-3">上传文档</h2>
          <p className="text-sm text-muted-foreground mb-3">
            支持 PDF / Word (.docx) / Markdown / TXT，单文件最大 50MB
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.md,.txt"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload.mutate(file);
              e.target.value = '';
            }}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={upload.isPending}
            className="px-4 py-2 bg-primary text-white rounded-md disabled:opacity-50"
          >
            {upload.isPending ? '上传中...' : '选择文件'}
          </button>
          {upload.isError && (
            <p className="mt-2 text-sm text-destructive">
              上传失败：{String(upload.error)}
            </p>
          )}
        </div>

        {/* Documents list */}
        <div className="bg-white rounded-lg shadow">
          <h2 className="text-lg font-semibold p-4 border-b">
            文档 ({kb.documents.length})
          </h2>
          {kb.documents.length === 0 && (
            <p className="p-4 text-muted-foreground text-center">还没有上传文档</p>
          )}
          {kb.documents.map((doc) => (
            <div
              key={doc.id}
              className="p-4 border-b last:border-0 flex justify-between items-center"
            >
              <div className="flex-1">
                <div className="font-medium text-foreground">{doc.filename}</div>
                <div className="text-sm text-muted-foreground">
                  {doc.file_type.toUpperCase()}
                  {doc.file_size != null && ` · ${(doc.file_size / 1024).toFixed(1)} KB`}
                  {' · '}
                  {formatDate(doc.created_at)}
                </div>
                {doc.parse_error && (
                  <div className="text-sm text-destructive mt-1">
                    ⚠ {doc.parse_error}
                  </div>
                )}
              </div>
              <span
                className={`px-2 py-1 text-xs rounded ${
                  PARSE_STATUS_COLORS[doc.parse_status] ?? 'bg-muted'
                }`}
              >
                {PARSE_STATUS_LABELS[doc.parse_status] ?? doc.parse_status}
                {doc.parse_status === 'success' && ` (${doc.chunk_count} 片)`}
              </span>
              <button
                type="button"
                onClick={() => {
                  if (confirm(`删除「${doc.filename}」？`)) remove.mutate(doc.id);
                }}
                className="ml-3 text-destructive text-sm"
              >
                删除
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
