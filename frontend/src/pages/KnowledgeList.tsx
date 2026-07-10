import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

export default function KnowledgeList() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const { data: kbs, isLoading } = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: () => api.listKnowledgeBases(),
  });

  const create = useMutation({
    mutationFn: () =>
      api.createKnowledgeBase({
        name,
        description: description || undefined,
      }),
    onSuccess: (kb) => {
      qc.invalidateQueries({ queryKey: ['knowledge-bases'] });
      setShowCreate(false);
      setName('');
      setDescription('');
      navigate(`/knowledge/${kb.id}`);
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteKnowledgeBase(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge-bases'] }),
  });

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6"><button
            type="button"
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-primary text-white rounded-md"
          >
            + 新建知识库
          </button>
        </div>

        {showCreate && (
          <div className="bg-white rounded-lg shadow p-6 mb-4">
            <h2 className="text-lg font-semibold mb-3">新建知识库</h2>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="知识库名称"
              className="w-full px-3 py-2 border rounded-md mb-3"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述（可选）"
              className="w-full px-3 py-2 border rounded-md mb-3"
              rows={3}
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="px-3 py-1 text-muted-foreground"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => create.mutate()}
                disabled={!name.trim() || create.isPending}
                className="px-4 py-1 bg-primary text-white rounded-md disabled:opacity-50"
              >
                {create.isPending ? '创建中...' : '创建'}
              </button>
            </div>
          </div>
        )}

        {isLoading && <p className="text-muted-foreground">加载中...</p>}

        {kbs && kbs.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-muted-foreground">
            还没有知识库。
          </div>
        )}

        {kbs && kbs.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {kbs.map((kb) => (
              <div
                key={kb.id}
                className="p-4 flex justify-between items-center hover:bg-muted"
              >
                <Link to={`/knowledge/${kb.id}`} className="flex-1">
                  <div className="font-medium text-foreground">{kb.name}</div>
                  <div className="text-sm text-muted-foreground">
                    {kb.description || '（无描述）'} · {formatDate(kb.created_at)}
                  </div>
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    if (confirm(`删除知识库「${kb.name}」？`)) remove.mutate(kb.id);
                  }}
                  className="text-destructive text-sm px-2"
                >
                  删除
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
