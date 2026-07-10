import { useMemo } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MessageSquarePlus, Trash2 } from 'lucide-react';

import { api } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { AgentSession } from '@/types/v0.4';

// ---------------------------------------------------------------------------
// Session grouping
// ---------------------------------------------------------------------------

type Bucket = '7天' | '30天' | string; // last is the YYYY-MM month label

function bucketFor(iso: string): Bucket {
  const d = new Date(iso).getTime();
  const ageDays = (Date.now() - d) / 86_400_000;
  if (ageDays <= 7) return '7天';
  if (ageDays <= 30) return '30天';
  const date = new Date(iso);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

interface SessionGroup {
  label: string;
  items: AgentSession[];
}

function groupSessions(sessions: AgentSession[]): SessionGroup[] {
  const order: string[] = [];
  const map = new Map<string, AgentSession[]>();
  for (const s of sessions) {
    const b = bucketFor(s.updated_at);
    if (!map.has(b)) {
      map.set(b, []);
      order.push(b);
    }
    map.get(b)!.push(s);
  }
  for (const arr of map.values()) {
    arr.sort((a, b) => (a.updated_at > b.updated_at ? -1 : 1));
  }
  return order.map((label) => ({ label, items: map.get(label) ?? [] }));
}

// ---------------------------------------------------------------------------
// AgentSessionListPanel — renders inside LayoutShell's asideLeft slot at /agent
// Same width (w-60) as the global SideNav, sits next to it on agent routes.
// ---------------------------------------------------------------------------

export function AgentSessionListPanel() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { sessionId } = useParams<{ sessionId: string }>();
  const currentId = sessionId;

  const { data: sessions, isLoading } = useQuery({
    queryKey: ['agent-sessions'],
    queryFn: () => api.listAgentSessions(),
  });
  const groups = useMemo(() => (sessions ? groupSessions(sessions) : []), [sessions]);

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteAgentSession(id),
    onSuccess: (_, deletedId) => {
      qc.invalidateQueries({ queryKey: ['agent-sessions'] });
      if (deletedId === currentId) navigate('/agent');
    },
  });

  return (
    <div className="flex h-full flex-col">
      <div className="px-3 pt-3">
        <Button
          type="button"
          variant="default"
          className="w-full justify-center"
          onClick={() => navigate('/agent')}
          size="sm"
        >
          <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
          开启新对话
        </Button>
      </div>
      <div className="mt-3 flex-1 overflow-y-auto px-2">
        {isLoading ? (
          <div className="space-y-2 px-2 py-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : groups.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            还没有对话。下方输入框开始第一条
          </p>
        ) : (
          groups.map((g) => (
            <div key={g.label} className="mb-3">
              <div className="px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                {g.label}内
              </div>
              <ul>
                {g.items.map((s) => {
                  const active = s.id === currentId;
                  return (
                    <li key={s.id} className="group relative">
                      <Link
                        to={`/agent/${s.id}`}
                        className={cn(
                          'flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
                          active
                            ? 'bg-primary/10 font-medium text-primary'
                            : 'text-foreground hover:bg-muted'
                        )}
                      >
                        <span className="truncate">{s.title}</span>
                      </Link>
                      <button
                        type="button"
                        aria-label={`删除对话 ${s.title}`}
                        onClick={async (e) => {
                          e.preventDefault();
                          if (!window.confirm(`删除对话「${s.title}」？`)) return;
                          remove.mutate(s.id);
                        }}
                        className="absolute right-2 top-1/2 hidden -translate-y-1/2 rounded p-1 text-muted-foreground hover:bg-muted hover:text-destructive group-hover:block"
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
