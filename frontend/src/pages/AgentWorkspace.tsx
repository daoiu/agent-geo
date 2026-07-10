import { useEffect, useRef } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowUp } from 'lucide-react';

import { api } from '@/api/client';
import { useAgentSession } from '@/hooks/useAgentSession';
import { ChatMessage } from '@/components/ChatMessage';
import { ToolCallCard } from '@/components/ToolCallCard';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Composer (textarea fills the box; send button is an absolute pill in the
// bottom-right corner — when the input has content the *whole* composer
// lights up in primary, not just a half-height strip).
// ---------------------------------------------------------------------------

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
  const taRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, [input]);

  function submit() {
    if (!active) return;
    onSend();
  }

  const hasText = input.trim().length > 0;
  const active = hasText && !loading && !disabled;
  const dimmed = (loading || disabled) && !hasText;

  return (
    <div
      className={cn(
        'relative rounded-xl border bg-card shadow-sm transition-colors',
        active
          ? 'border-primary bg-primary/5'
          : 'border-border bg-card',
        dimmed && 'opacity-60',
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
        disabled={Boolean(disabled) && false /* always typeable; send has its own guard */}
        className="block w-full resize-none rounded-xl bg-transparent px-4 pb-12 pt-3 text-sm leading-6 placeholder:text-muted-foreground focus:outline-none"
      />
      <button
        type="button"
        onClick={submit}
        disabled={!active}
        aria-label="发送"
        className={cn(
          'absolute bottom-2 right-2 inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors',
          active
            ? 'bg-primary text-primary-foreground hover:bg-primary/90'
            : 'bg-muted text-muted-foreground cursor-not-allowed',
        )}
      >
        <ArrowUp className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty state (used by /agent without a session id)
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <h2 className="text-2xl font-semibold tracking-tight text-foreground">
        开始对话
      </h2>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        GEO 助手可以诊断品牌、查询知识库、生成内容。先说「帮我诊断小米」试试？
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ChatPane — the right pane of LayoutShell's asideLeft slot
// ---------------------------------------------------------------------------

function ChatPane() {
  const { sessionId = '' } = useParams<{ sessionId: string }>();
  const [searchParams] = useSearchParams();
  const prefill = searchParams.get('prefill') ?? '';

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
      <div className="flex-1 overflow-y-auto px-6 py-8">
        <div className="mx-auto flex max-w-3xl flex-col gap-6">
          {isEmpty ? (
            <EmptyState />
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

      <footer className="bg-bg-stage px-4 py-3">
        <div className="mx-auto max-w-3xl">
          <Composer
            input={input}
            setInput={setInput}
            onSend={send}
            loading={loading}
            disabled={Boolean(pending)}
          />
          {!sessionId && (
            <p className="mt-2 text-center text-xs text-muted-foreground">
              按「开启新对话」开始第一条消息
            </p>
          )}
        </div>
      </footer>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Default export — wraps the chat pane with the prefill auto-create flow.
// When the Dashboard's "立即对话 →" button includes ?prefill=…, this page
// creates a brand-new session the moment it mounts on /agent without a
// sessionId, then navigates to /agent/:newId.
// ---------------------------------------------------------------------------

export default function AgentWorkspace() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { sessionId } = useParams<{ sessionId: string }>();

  const create = useMutation({
    mutationFn: (title?: string) => api.createAgentSession(title),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ['agent-sessions'] });
      navigate(`/agent/${s.id}`, { replace: true });
    },
  });

  const [searchParams] = useSearchParams();
  const prefill = searchParams.get('prefill') ?? '';
  useEffect(() => {
    if (!sessionId && prefill && !create.isPending && !create.data) {
      create.mutate(prefill);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill, sessionId]);

  return <ChatPane />;
}
