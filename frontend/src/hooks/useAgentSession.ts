import { useEffect, useRef, useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { api, confirmAgentActionStream, sendAgentMessageStream } from '@/api/client';
import type {
  AgentMessage,
  AgentSessionDetail,
  PendingConfirmation,
} from '@/types/v0.4';
import type { AgentEventV7 as AgentEvent } from '@/types/v0.7';
import type { ToolCallDisplay } from '@/components/ToolCallCard';

export interface UseAgentSessionResult {
  /** Live session detail — null while loading. */
  session: AgentSessionDetail | undefined;
  /** Composer state. */
  input: string;
  setInput: (v: string) => void;
  /** True while the SSE stream is open. */
  loading: boolean;
  /** Pending human-confirmation card, if any. */
  pending: PendingConfirmation | null;
  /** Live tool call tiles keyed by tool_call_id. */
  toolCalls: ToolCallDisplay[];
  /** Send the current input — appends user message, opens SSE stream. */
  send: () => Promise<void>;
  /** Approve a pending human confirmation; resumes SSE. */
  approve: () => Promise<void>;
  /** Cancel a pending human confirmation. */
  cancel: () => Promise<void>;
  /** True while an empty-state view should be shown (no messages yet). */
  isEmpty: boolean;
}

/**
 * useAgentSession — owns the SSE session lifecycle for a single agent chat:
 *
 *   - session detail via React Query
 *   - optimistic user-message insertion
 *   - SSE streaming, in-place assistant_message / tool_call_start / result patches
 *   - pending human-confirmation plumbing
 *   - approve / cancel resume via SSE
 *
 * The hook is view-agnostic; AgentWorkspace consumes the result and lays it
 * out as a 2-pane workspace.
 */
export function useAgentSession(sessionId: string | undefined): UseAgentSessionResult {
  const qc = useQueryClient();

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState<PendingConfirmation | null>(null);
  const [toolCalls, setToolCalls] = useState<Record<string, ToolCallDisplay>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const enabled = Boolean(sessionId);
  const { data: session } = useQuery({
    queryKey: ['agent-session', sessionId],
    queryFn: () => api.getAgentSession(sessionId as string),
    enabled,
  });

  // Reset transient state when the session id changes
  useEffect(() => {
    setInput('');
    setLoading(false);
    setPending(null);
    setToolCalls({});
  }, [sessionId]);

  // Auto-scroll handler (kept here so views can pass the ref themselves; the
  // hook only holds a slot).
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [session?.messages?.length, toolCalls]);

  const handleAgentEvent = useCallback((event: AgentEvent) => {
    switch (event.event) {
      case 'assistant_message':
        if (event.content) {
          qc.setQueryData(
            ['agent-session', sessionId],
            (old: AgentSessionDetail | undefined) => {
              if (!old) return old;
              return {
                ...old,
                messages: [
                  ...old.messages,
                  {
                    id: `ast-${Date.now()}-${Math.random()}`,
                    session_id: sessionId as string,
                    role: 'assistant',
                    content: event.content,
                    tool_calls: null,
                    tool_call_id: null,
                    pending_confirmation: false,
                    created_at: new Date().toISOString(),
                  } as AgentMessage,
                ],
              };
            },
          );
        }
        break;
      case 'tool_call_start':
        setToolCalls((prev) => ({
          ...prev,
          [event.tool_call_id]: {
            tool_call_id: event.tool_call_id,
            tool_name: event.tool_name,
            arguments: event.arguments,
            pending: true,
          },
        }));
        break;
      case 'tool_call_result':
        setToolCalls((prev) => ({
          ...prev,
          [event.tool_call_id]: {
            ...prev[event.tool_call_id],
            result: event.result,
            pending: false,
          },
        }));
        break;
      case 'human_confirmation_required':
        setPending({
          message_id: event.message_id,
          tool_name: event.tool_name,
          arguments: event.arguments,
        });
        break;
      case 'turn_complete':
      case 'max_iterations_reached':
      case 'error':
        break;
    }
  }, [qc, sessionId]);

  const send = useCallback(async () => {
    if (!sessionId) return;
    if (!input.trim() || loading || pending) return;
    const userContent = input.trim();
    setInput('');
    setLoading(true);
    setToolCalls({});

    // optimistic user-message insertion
    qc.setQueryData(
      ['agent-session', sessionId],
      (old: AgentSessionDetail | undefined) => {
        if (!old) return old;
        return {
          ...old,
          messages: [
            ...old.messages,
            {
              id: `usr-${Date.now()}`,
              session_id: sessionId,
              role: 'user',
              content: userContent,
              tool_calls: null,
              tool_call_id: null,
              pending_confirmation: false,
              created_at: new Date().toISOString(),
            } as AgentMessage,
          ],
        };
      },
    );

    try {
      for await (const event of sendAgentMessageStream(sessionId, userContent)) {
        handleAgentEvent(event);
      }
    } catch (err) {
      console.error('SSE error:', err);
    } finally {
      setLoading(false);
      qc.invalidateQueries({ queryKey: ['agent-session', sessionId] });
    }
  }, [handleAgentEvent, input, loading, pending, qc, sessionId]);

  const approve = useCallback(async () => {
    if (!sessionId || !pending) return;
    const approved = pending;
    setPending(null);
    setToolCalls({});
    try {
      for await (const event of confirmAgentActionStream(
        sessionId,
        approved.message_id,
        true,
      )) {
        handleAgentEvent(event);
      }
    } catch (err) {
      console.error('Resume SSE error:', err);
    } finally {
      qc.invalidateQueries({ queryKey: ['agent-session', sessionId] });
    }
  }, [handleAgentEvent, pending, qc, sessionId]);

  const cancel = useCallback(async () => {
    if (!sessionId || !pending) return;
    setPending(null);
    setToolCalls({});
    await api.confirmAgentAction(sessionId, pending.message_id, false);
    qc.invalidateQueries({ queryKey: ['agent-session', sessionId] });
  }, [pending, qc, sessionId]);

  return {
    session,
    input,
    setInput,
    loading,
    pending,
    toolCalls: Object.values(toolCalls),
    send,
    approve,
    cancel,
    isEmpty: !session || session.messages.length === 0,
  };
}
