import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { knowledgeApi } from '@/api/knowledge';
import { KnowledgeChunkGrid } from '@/components/knowledge/KnowledgeChunkGrid';

/**
 * v0.7 KnowledgeSearch — cross-KB hybrid recall (spec §5.1 + v0.6 P1.3).
 * Debounces user input by 200 ms before firing the query so we don't
 * thrash the backend while typing.
 */
const DEBOUNCE_MS = 200;

export default function KnowledgeSearch() {
  const [text, setText] = useState('');
  const [debounced, setDebounced] = useState('');
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(text), DEBOUNCE_MS);
    return () => window.clearTimeout(t);
  }, [text]);

  const searchQ = useQuery({
    queryKey: ['knowledge-search', debounced],
    queryFn: () => knowledgeApi.searchKnowledgeGlobal(debounced, 50),
    enabled: debounced.length >= 1,
  });

  return (
    <div className="flex flex-col gap-4 p-6">
      <header className="flex items-baseline gap-3">
        <Search className="h-5 w-5 text-primary" aria-hidden="true" />
        <h1 className="text-2xl font-semibold text-fg">跨库检索</h1>
        <span className="text-sm text-fg-muted">
          关键词在所有 KB 中执行 hybrid recall。
        </span>
      </header>

      <label className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 shadow-card focus-within:ring-2 focus-within:ring-ring">
        <Search className="h-4 w-4 text-fg-muted" aria-hidden="true" />
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="试试「小米 Mix Fold 4 评测」"
          className="min-w-0 flex-1 bg-transparent text-sm text-fg placeholder:text-fg-muted focus-visible:outline-none"
        />
      </label>

      {searchQ.isLoading && debounced && (
        <p className="text-sm text-fg-muted">搜索中…</p>
      )}
      {searchQ.isError && (
        <p className="text-sm text-danger">检索失败:{String(searchQ.error)}</p>
      )}
      {searchQ.data && (
        <KnowledgeChunkGrid result={searchQ.data} />
      )}
      {!debounced && (
        <p className="mt-12 text-center text-sm text-fg-muted">
          输入关键词开始搜索。
        </p>
      )}
    </div>
  );
}
