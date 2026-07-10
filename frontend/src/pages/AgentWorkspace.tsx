import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowUp,
  Compass,
  Image as ImageIcon,
  MessageSquarePlus,
  Search,
  Sparkles,
  Trash2,
} from 'lucide-react';

import { api } from '@/api/client';
import { useAgentSession } from '@/hooks/useAgentSession';
import { useDarkMode } from '@/hooks/useDarkMode';
import { ChatMessage } from '@/components/ChatMessage';
import { ToolCallCard } from '@/components/ToolCallCard';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { AgentSession } from '@/types/v0.4';

// ---------------------------------------------------------------------------
// Mode switcher (lightweight segmented control — avoids Radix Tabs overhead)
// ---------------------------------------------------------------------------

type Mode = 'fast' | 'expert' | 'vision';

interface ModeMeta {
  id: Mode;
  label: string;
  icon: typeof Sparkles;
  hint: string;
}

const MODES: ModeMeta[] = [
  { id: 'fast', label: '快速模式', icon: Sparkles, hint: 'ReAct + 3 工具 (默认)' },
  { id: 'expert', label: '专家模式', icon: Compass, hint: '深度推理 · 多步' },
  { id: 'vision', label: '识图模式', icon: ImageIcon, hint: '截图/页面解析' },
];

function ModeSwitch({
  value,
  onChange,
  size = 'md',
}: {
  value: Mode;
  onChange: (m: Mode) => void;
  size?: 'sm' | 'md';
}) {
  return (
    <div
      role="tablist"
      aria-label="对话模式"
      className={cn(
        'inline-flex items-center justify-center rounded-full border border-border bg-card p-1 text-sm',
        size === 'sm' && 'text-xs'
      )}
    >
      {MODES.map((m) => {
        const Icon = m.icon;
        const active = m.id === value;
        return (
          <button
            key={m.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(m.id)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 font-medium transition-all',
              size === 'sm' && 'px-2.5 py-1',
              active
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
          >
            <Icon className={size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'} aria-hidden="true" />
            {m.label}
          </button>
        );
      })}
    </div>
  );
}

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
  // newest first within each group
  for (const arr of map.values()) {
    arr.sort((a, b) => (a.updated_at > b.updated_at ? -1 : 1));
  }
  return order.map((label) => ({ label, items: map.get(label) ?? [] }));
}

// ---------------------------------------------------------------------------
// Left sidebar: session list (280px)
// ---------------------------------------------------------------------------

function SessionSidebar({
  onNewChat,
  onDeleteChat,
  currentId,
}: {
  onNewChat: () => void;
  onDeleteChat: (id: string) => void;
  currentId: string | undefined;
}) {
  const navigate = useNavigate();
  const { data: sessions, isLoading } = useQuery({
    queryKey: ['agent-sessions'],
    queryFn: () => api.listAgentSessions(),
  });
  const groups = useMemo(() => (sessions ? groupSessions(sessions) : []), [sessions]);

  return (
    <aside
      aria-label="会话历史"
      className="hidden h-full w-72 shrink-0 flex-col border-r border-border bg-bg-stage md:flex"
    >
      <div className="flex items-center justify-between px-4 py-3">
        <Link to="/" className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground font-bold">
            G
          </span>
          <span className="text-sm font-semibold text-foreground">GEO 助手</span>
        </Link>
      </div>
      <div className="px-3">
        <Button
          type="button"
          variant="default"
          className="w-full justify-center"
          onClick={onNewChat}
        >
          <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
          开启新对话
        </Button>
      </div>
      <div className="mt-4 flex-1 overflow-y-auto px-2">
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
                          await onDeleteChat(s.id);
                          if (active) navigate('/agent');
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
      <div className="border-t px-3 py-3 text-xs text-muted-foreground">
        <span aria-hidden="true">268****05@qq.com</span>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Right pane: chat workspace
// ---------------------------------------------------------------------------

interface ChipProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

function Chip({ active, onClick, children }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs transition-colors',
        active
          ? 'border-primary bg-primary/10 text-primary'
          : 'border-border bg-card text-muted-foreground hover:text-foreground'
      )}
    >
      {children}
    </button>
  );
}

function Composer({
  input,
  setInput,
  onSend,
  loading,
  disabled,
}: {
  input: string;
  setInput: (v: string) => void;
  onSend: () => void;
  loading: boolean;
  disabled?: boolean;
}) {
  const [deep, setDeep] = useState(false);
  const [search, setSearch] = useState(false);
  const taRef = useRef<HTMLTextAreaElement>(null);
  // auto-grow
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [input]);

  function submit() {
    if (!input.trim() || loading || disabled) return;
    onSend();
  }

  return (
    <div
      className={cn(
        'rounded-2xl border border-border bg-card shadow-sm',
        (loading || disabled) && 'opacity-70'
      )}
    >
      <textarea
        ref={taRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder="给 GEO 助手发送消息（Enter 发送，Shift+Enter 换行）"
        aria-label="消息输入"
        disabled={Boolean(loading || disabled)}
        className="block w-full resize-none rounded-t-2xl bg-transparent px-4 py-3 text-sm leading-6 placeholder:text-muted-foreground focus:outline-none disabled:opacity-50"
      />
      <div className="flex items-center justify-between gap-2 border-t px-3 py-2">
        <div className="flex items-center gap-2">
          <Chip active={deep} onClick={() => setDeep((v) => !v)}>
            <Sparkles className="h-3 w-3" aria-hidden="true" />
            深度思考
          </Chip>
          <Chip active={search} onClick={() => setSearch((v) => !v)}>
            <Search className="h-3 w-3" aria-hidden="true" />
            智能搜索
          </Chip>
        </div>
        <button
          type="button"
          onClick={submit}
          disabled={!input.trim() || loading || Boolean(disabled)}
          aria-label="发送"
          className={cn(
            'inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors',
            input.trim() && !loading && !disabled
              ? 'bg-primary text-primary-foreground hover:bg-primary/90'
              : 'bg-muted text-muted-foreground'
          )}
        >
          <ArrowUp className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

function EmptyState({ modeLabel }: { modeLabel: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <h2 className="text-2xl font-semibold tracking-tight text-foreground">
        使用{modeLabel}开始对话
      </h2>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        GEO 助手可以诊断品牌、查询知识库、生成内容。先说「帮我诊断小米」试试？
      </p>
    </div>
  );
}

function ChatPane() {
  const { sessionId = '' } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const prefill = searchParams.get('prefill') ?? '';

  const [mode, setMode] = useState<Mode>('fast');
  const modeMeta = MODES.find((m) => m.id === mode) ?? MODES[0];
  const { theme } = useDarkMode();

  const {
    session,
    input,
    setInput,
    loading,
    pending,
    toolCalls,
    send,
    approve,
    cancel,
    isEmpty,
  } = useAgentSession(sessionId || undefined);

  // Prefill from query string once (only if composer is empty)
  const prefillRef = useRef(false);
  useEffect(() => {
    if (prefill && !prefillRef.current && input === '') {
      setInput(prefill);
      prefillRef.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.messages?.length, toolCalls.length]);

  return (
    <section className="flex h-full min-w-0 flex-1 flex-col">
      {/* Top: mode switch (only when no session or empty session) */}
      <header className="flex flex-col items-center gap-3 border-b px-6 py-4">
        <ModeSwitch value={mode} onChange={setMode} />
        {session && !isEmpty && (
          <div className="text-xs text-muted-foreground">
            {modeMeta.hint} · {session.messages.length} 条消息
          </div>
        )}
      </header>

      {/* Chat scroll */}
      <div className="flex-1 overflow-y-auto px-6 py-8">
        <div className="mx-auto flex max-w-3xl flex-col gap-6">
          {isEmpty ? (
            <EmptyState modeLabel={modeMeta.label} />
          ) : (
            session?.messages.map((m) => <ChatMessage key={m.id} message={m} />)
          )}
          {toolCalls.map((tc) => (
            <ToolCallCard key={tc.tool_call_id} display={tc} />
          ))}
          {loading && (
            <div className="text-sm italic text-muted-foreground">agent 思考中...</div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {pending && (
        <ConfirmDialog
          toolName={pending.tool_name}
          arguments={pending.arguments}
          onApprove={approve}
          onCancel={cancel}
          pending={loading}
        />
      )}

      {/* Composer */}
      <footer className="border-t bg-bg-stage px-4 py-3">
        <div className="mx-auto max-w-3xl">
          <Composer
            input={input}
            setInput={setInput}
            onSend={send}
            loading={loading}
            disabled={Boolean(pending) || !sessionId}
          />
          {!sessionId && (
            <p className="mt-2 text-center text-xs text-muted-foreground">
              按「开启新对话」开始第一条消息
            </p>
          )}
          <div className="mt-1 text-center text-[10px] text-muted-foreground tabular-nums">
            当前模式：{modeMeta.label} · 主题：{theme === 'dark' ? '暗' : '亮'}
          </div>
        </div>
      </footer>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Workspace root
// ---------------------------------------------------------------------------

/**
 * AgentWorkspace — deepseek-style 2-pane chat workspace.
 *
 * Sidebar: list of past sessions, grouped by recency (7 days / 30 days / month).
 * Main pane: mode switcher + scrollable transcript + composer.
 *
 * Routes:
 *   - /agent             → empty workspace; composer disabled
 *   - /agent/:sessionId  → loads that session; composer enabled
 *
 * The page intentionally bypasses `LayoutShell` (no TopBar / SideNav /
 * PipelineRail) because the workspace is a focused full-screen chat surface
 * — users come here to talk to the agent.
 */
export default function AgentWorkspace() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { sessionId } = useParams<{ sessionId: string }>();

  const create = useMutation({
    mutationFn: (title?: string) => api.createAgentSession(title),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ['agent-sessions'] });
      navigate(`/agent/${s.id}`);
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteAgentSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-sessions'] }),
  });

  // Wire the Dashboard "立即对话 →" prefill: when sessionId is missing
  // and a ?prefill query param is present, create a new session immediately.
  const [searchParams] = useSearchParams();
  const prefill = searchParams.get('prefill') ?? '';
  useEffect(() => {
    if (!sessionId && prefill && !create.isPending && !create.data) {
      create.mutate(prefill);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill, sessionId]);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-bg">
      <SessionSidebar
        currentId={sessionId}
        onNewChat={() => navigate('/agent')}
        onDeleteChat={(id) => remove.mutate(id)}
      />
      <ChatPane />
    </div>
  );
}
