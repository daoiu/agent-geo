import { useCallback, useRef, useState } from 'react';
import {
  sendAgentMessageStream,
  confirmAgentActionStream,
  replayAgentMessageStream,
} from '@/api/agent';
import type { AgentEventV7, HandoffLog, TruncationDecision } from '@/types/v0.7';

/**
 * useAgentStream — subscribes to the agent SSE stream and surfaces five
 * cohesive slices for the UI to render:
 *
 *   - messages : assistant content tokens accumulated into a single string
 *   - tools    : in-flight tool call results (insert + patch)
 *   - handoffs : multi-agent handoff log (LangGraph-only)
 *   - truncations : LLM-context compression decisions
 *   - status   : 'idle' | 'streaming' | 'awaiting_confirmation' | 'error'
 *
 * The hook accepts an injected SSE iterator so tests can replay a
 * canned event stream without hitting `fetch()`.
 */

export interface AgentStreamToolEntry {
  tool_call_id: string;
  tool_name: string;
  result?: unknown;
}

export interface AgentStreamState {
  messages: string;
  tools: AgentStreamToolEntry[];
  handoffs: HandoffLog[];
  truncations: TruncationDecision[];
  status: 'idle' | 'streaming' | 'awaiting_confirmation' | 'error';
  error?: string;
}

export interface UseAgentStream {
  state: AgentStreamState;
  send: (sessionId: string, content: string) => Promise<void>;
  confirm: (
    sessionId: string,
    messageId: string,
    approved: boolean,
  ) => Promise<void>;
  replay: (sessionId: string, messageId: string) => Promise<void>;
  abort: () => void;
}

/**
 * Default hook used by the app — wraps the real API iterators.
 * `useAgentStreamForTesting` below takes an injected iterator factory
 * so unit tests can replay event streams without touching `fetch`.
 */
export function useAgentStream(): UseAgentStream {
  return useAgentStreamCore({
    send: (sid, content) =>
      sendAgentMessageStream(sid, content) as AsyncGenerator<AgentEventV7>,
    confirm: (sid, mid, approved) =>
      confirmAgentActionStream(sid, mid, approved) as AsyncGenerator<AgentEventV7>,
    replay: (sid, mid) =>
      replayAgentMessageStream(sid, mid) as AsyncGenerator<AgentEventV7>,
  });
}

export interface StreamAdapters {
  send: (
    sessionId: string,
    content: string,
  ) => AsyncGenerator<AgentEventV7>;
  confirm: (
    sessionId: string,
    messageId: string,
    approved: boolean,
  ) => AsyncGenerator<AgentEventV7>;
  replay: (
    sessionId: string,
    messageId: string,
  ) => AsyncGenerator<AgentEventV7>;
}

/**
 * useAgentStreamCore — accepts injected stream sources so unit tests can
 * drive the reducer with a known event script.
 */
export function useAgentStreamCore(adapters: StreamAdapters): UseAgentStream {
  const [state, setState] = useState<AgentStreamState>({
    messages: '',
    tools: [],
    handoffs: [],
    truncations: [],
    status: 'idle',
  });
  const ctrlRef = useRef<AbortController | null>(null);

  const consume = useCallback(
    async (iter: AsyncGenerator<AgentEventV7>) => {
      setState((s) => ({ ...s, status: 'streaming', error: undefined }));
      try {
        for await (const evt of iter) {
          setState((s) => reduce(s, evt));
        }
        setState((s) => ({ ...s, status: 'idle' }));
      } catch (err) {
        setState((s) => ({
          ...s,
          status: 'error',
          error: err instanceof Error ? err.message : String(err),
        }));
      }
    },
    [],
  );

  const send = useCallback(
    async (sessionId: string, content: string) => {
      const iter = adapters.send(sessionId, content);
      await consume(iter);
    },
    [adapters, consume],
  );

  const confirm = useCallback(
    async (sessionId: string, messageId: string, approved: boolean) => {
      setState((s) => ({ ...s, status: 'awaiting_confirmation' }));
      const iter = adapters.confirm(sessionId, messageId, approved);
      await consume(iter);
    },
    [adapters, consume],
  );

  const replay = useCallback(
    async (sessionId: string, messageId: string) => {
      const iter = adapters.replay(sessionId, messageId);
      await consume(iter);
    },
    [adapters, consume],
  );

  const abort = useCallback(() => {
    ctrlRef.current?.abort();
    ctrlRef.current = null;
    setState((s) => ({ ...s, status: 'idle' }));
  }, []);

  return { state, send, confirm, replay, abort };
}

function reduce(state: AgentStreamState, evt: AgentEventV7): AgentStreamState {
  switch (evt.event) {
    case 'llm_token':
      return { ...state, messages: state.messages + evt.delta };
    case 'tool_call':
      return {
        ...state,
        tools: [
          ...state.tools,
          { tool_call_id: cryptoId(), tool_name: evt.name },
        ],
      };
    case 'tool_result':
      return {
        ...state,
        tools: state.tools.map((t) =>
          t.tool_name === evt.name && t.result === undefined
            ? { ...t, result: evt.result }
            : t,
        ),
      };
    case 'handoff':
      return {
        ...state,
        handoffs: [
          ...state.handoffs,
          {
            id: cryptoId(),
            sessionId: '',
            fromAgent: evt.from_agent,
            toAgent: evt.to_agent,
            taskSummary: evt.task_summary,
            reason: evt.reason,
            timestamp: evt.timestamp,
          },
        ],
      };
    case 'truncation_decision':
      return {
        ...state,
        truncations: [
          ...state.truncations,
          {
            strategy: evt.strategy,
            originalTokens: 0,
            finalTokens: 0,
            savedTokens: evt.saved_tokens,
          },
        ],
      };
    default:
      // `llm_start` / `turn_complete` / errors / legacy variants — no
      // state change yet; the UI can hook these up in Task 8 (Timeline).
      return state;
  }
}

function cryptoId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `id-${Math.random().toString(36).slice(2)}`;
}
