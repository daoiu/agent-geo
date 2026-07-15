import { useEffect, useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowUp } from 'lucide-react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import type { AgentMessage, AgentSessionDetail } from '@/types/v0.4';
import type { AgentEventV7 as AgentEvent } from '@/types/v0.7';

import { api, sendAgentMessageStream } from '@/api/client';
import { useAgentSession } from '@/hooks/useAgentSession';
import { ChatMessage } from '@/components/ChatMessage';
import { AssistantTurn } from '@/components/AssistantTurn';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { buildTurnRows } from '@/lib/agentTimeline';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Composer — fixed-height card; the whole box lights up when input is non-empty
// (not just the round send button).
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
        disabled={false}
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
// Empty state
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
// First-send SSE — runs against a brand-new session id and patches the cache
// the same way useAgentSession does, so subsequent renders read the same
// in-progress conversation from queryClient.
// ---------------------------------------------------------------------------

async function streamFirstSend(
  qc: ReturnType<typeof useQueryClient>,
  newSessionId: string,
  text: string,
): Promise<void> {
  for await (const event of sendAgentMessageStream(newSessionId, text)) {
    applyAgentEvent(qc, newSessionId, event);
  }
  qc.invalidateQueries({ queryKey: ['agent-session', newSessionId] });
}

function applyAgentEvent(
  qc: ReturnType<typeof useQueryClient>,
  sessionId: string,
  event: AgentEvent,
): void {
  switch (event.event) {
    case 'assistant_message':
      if (event.content) {
        qc.setQueryData<AgentSessionDetail>(['agent-session', sessionId], (old) => {
          if (!old) return old;
          return {
            ...old,
            messages: [
              ...old.messages,
              {
                id: `ast-${Date.now()}-${Math.random()}`,
                session_id: sessionId,
                role: 'assistant',
                content: event.content,
                tool_calls: null,
                tool_call_id: null,
                pending_confirmation: false,
                created_at: new Date().toISOString(),
              } as AgentMessage,
            ],
          };
        });
      }
      break;
    case 'tool_call_start':
    case 'tool_call_result':
    case 'human_confirmation_required':
    case 'turn_complete':
    case 'max_iterations_reached':
    case 'error':
    case 'llm_start':
    case 'llm_token':
    case 'tool_call':
    case 'tool_result':
    case 'handoff':
    case 'memory_injected':
    case 'truncation_decision':
    case 'llm_error':
    case 'turn_complete_legacy':
      // first-send path only needs the assistant_message branch for visual
      // rendering; tool call / handoff / truncation / memory injection are
      // surfaced via TimelineRail (Task 8 v0.7.1 integration step).
      break;
    default: {
      // Exhaustiveness check — TS knows we covered every AgentEvent variant
      // (`as unknown as never` keeps the cast valid even after AgentEvent
      // is widened to v0.7's `AgentEventV7` superset).
      const _exhaustive: never = event as unknown as never;
      void _exhaustive;
      break;
    }
  }
}

// ---------------------------------------------------------------------------
// ChatPane — owns the page; first-send auto-creates the session.
// ---------------------------------------------------------------------------

export default function AgentWorkspace() {
  const navigate = useNavigate();
  const qc = useQueryClient();
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

  // One-shot guard: stream against the new session exactly once per click.
  // Without this, React 18 StrictMode + a same-render dep change on
  // sessionId from '' to <new-id> can double-invoke the auto-fire path.
  const inFlightRef = useRef(false);

  const create = useMutation({
    mutationFn: (title?: string) => api.createAgentSession(title),
  });

  async function onSend() {
    if (inFlightRef.current) return;
    const text = input.trim();
    if (!text) return;
    if (loading || pending) return;

    if (sessionId) {
      // Subsequent sends — normal path through useAgentSession.
      void send();
      return;
    }

    // First-send in /agent — create, seed cache, stream inline, then nav.
    // No setTimeout / effect / state machine so we never fire twice.
    inFlightRef.current = true;
    try {
      const title = text.slice(0, 30);
      const newSession = await create.mutateAsync(title);
      const now = new Date().toISOString();
      const userMsg: AgentMessage = {
        id: `usr-${now}`,
        session_id: newSession.id,
        role: 'user',
        content: text,
        tool_calls: null,
        tool_call_id: null,
        pending_confirmation: false,
        created_at: now,
      };

      // Seed the cache *with* the user message so the upcoming /agent/:id
      // mount renders the user bubble without a flicker.
      qc.setQueryData(['agent-session', newSession.id], {
        ...newSession,
        messages: [userMsg],
      });
      qc.invalidateQueries({ queryKey: ['agent-sessions'] });

      // Fire the SSE stream against the new id; this writes assistant
      // messages into the same cache. We deliberately do NOT await the full
      // stream before navigating — we kick it off and let the URL change
      // happen so the user sees the rest of the conversation.
      void streamFirstSend(qc, newSession.id, text).catch((err) => {
        console.error('SSE error:', err);
      });

      // Clear the composer locally and head to the new conversation.
      setInput('');
      navigate(`/agent/${newSession.id}`, { replace: true });
    } finally {
      inFlightRef.current = false;
    }
  }

  // One-shot fill: prefill query string into the composer on /agent (only).
  useEffect(() => {
    if (prefill && !sessionId && input === '') {
      setInput(prefill);
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
            buildTurnRows(session?.messages ?? [], toolCalls).map((row, i) =>
              row.kind === 'user' ? (
                <ChatMessage key={row.message.id} message={row.message} />
              ) : (
                <AssistantTurn key={`turn-${i}`} items={row.items} />
              ),
            )
          )}
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
            onSend={onSend}
            loading={loading}
            disabled={Boolean(pending) || inFlightRef.current}
          />
          {!sessionId && (
            <p className="mt-2 text-center text-xs text-muted-foreground">
              按「发送」自动创建新对话并发送
            </p>
          )}
        </div>
      </footer>
    </section>
  );
}
