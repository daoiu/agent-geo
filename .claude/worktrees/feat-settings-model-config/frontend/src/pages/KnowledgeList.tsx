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
  const [query, setQuery] = useState('');

  const { data: kbs, isLoading } = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: () => api.listKnowledgeBases(),
  });

  // v0.6 P1.3 — global cross-KB search. No kb_id required.
  const {
    data: searchResult,
    isFetching: searching,
    refetch: runSearch,
  } = useQuery({
    queryKey: ['knowledge-global-search', query],
    queryFn: () => api.searchKnowledgeGlobal(query.trim(), 10),
    enabled: false, // require explicit trigger via Enter / button
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

  const trimmed = query.trim();
  const showResults = trimmed.length > 0 && !!searchResult;

  function submitSearch() {
    if (!trimmed) return;
    void runSearch();
  }

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-4xl mx-auto px-4">
        <h1 className="text-2xl font-semibold mb-4 text-foreground">知识库</h1>

        {/* ---- v0.6 P1.3: cross-KB global search ---- */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <label htmlFor="kb-global-search" className="sr-only">
            全局搜索知识库
          </label>
          <div className="flex gap-2">
            <input
              id="kb-global-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  submitSearch();
                }
              }}
              placeholder="跨知识库全文检索（无需选 KB，回车搜索）"
              className="flex-1 px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/40"
              aria-label="跨知识库搜索"
            />
            <button
              type="button"
              onClick={submitSearch}
              disabled={!trimmed || searching}
              className="px-4 py-2 bg-primary text-white rounded-md disabled:opacity-50"
            >
              {searching ? '搜索中…' : '搜索'}
            </button>
          </div>

          {showResults && (
            <div className="mt-4">
              {searchResult.hits.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  没有命中任何知识库片段。
                </p>
              ) : (
                <ul className="divide-y">
                  {searchResult.hits.map((h) => (
                    <li
                      key={h.chunk_id}
                      className="py-3 flex flex-col gap-1"
                      data-testid="global-search-hit"
                    >
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 text-xs rounded-full bg-primary/10 text-primary">
                          {h.kb_name || '未命名 KB'}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          来自 {h.doc_filename}
                        </span>
                        {h.sources.map((s) => (
                          <span
                            key={s}
                            className="px-1.5 py-0.5 text-[10px] rounded border border-border text-muted-foreground"
                          >
                            {s}
                          </span>
                        ))}
                        <span className="ml-auto text-xs text-muted-foreground">
                          score {h.score.toFixed(3)}
                        </span>
                      </div>
                      <p className="text-sm text-foreground whitespace-pre-wrap line-clamp-3">
                        {h.content}
                      </p>
                      <Link
                        to={`/knowledge/${h.kb_id}`}
                        className="self-start text-xs text-primary hover:underline"
                      >
                        打开知识库 →
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* ---- existing KB list + create ---- */}
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-lg font-semibold text-foreground">我的知识库</h2>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-primary text-white rounded-md"
          >
            + 新建知识库
          </button>
        </div>

        {showCreate && (
          <div className="bg-white rounded-lg shadow p-6 mb-4">
            <h3 className="text-lg font-semibold mb-3">新建知识库</h3>
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
