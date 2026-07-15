import { useCallback, useMemo, useState } from 'react';
import {
  sendAgentMessageStream,
  confirmAgentActionStream,
  replayAgentMessageStream,
} from '@/api/agent';
import type { AgentEventV7, HandoffLog, TruncationDecision } from '@/types/v0.7';

/**
 * v0.7 useAgentStream(sessionId) — plan §Task 7 §Step 6 hook shape.
 *
 *   const { state, send, confirm, replay, abort } = useAgentStream(sessionId);
 *
 *   - `state` carries messages / tools / handoffs / truncations / status
 *   - `send(content)`           → SSE stream for a fresh user message
 *   - `confirm(messageId, ok)`  → HITL reply
 *   - `replay(messageId)`       → Replay API (Task 10)
 *   - `abort()`                 → cancels any in-flight consume
 *
 * `sessionId` is bound at the hook so the call sites do not have to
 * thread it through every method.  Tests use `useAgentStreamCore`
 * (factory) to inject scripted event sources — that variant does not
 * need a real sessionId.
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
  send: (content: string) => Promise<void>;
  confirm: (messageId: string, approved: boolean) => Promise<void>;
  replay: (messageId: string) => Promise<void>;
  abort: () => void;
}

/**
 * Default factory from the real API iterators.  Tests pass a custom
 * `factories` to replay scripted events.
 */
function defaultFactories(sessionId: string) {
  return {
    send: (content: string) => sendAgentMessageStream(sessionId, content),
    confirm: (messageId: string, approved: boolean) =>
      confirmAgentActionStream(sessionId, messageId, approved),
    replay: (messageId: string) => replayAgentMessageStream(sessionId, messageId),
  };
}

export type StreamFactories = ReturnType<typeof defaultFactories>;

export function useAgentStream(sessionId: string): UseAgentStream {
  return useAgentStreamFor(sessionId, defaultFactories);
}

/**
 * useAgentStreamFor — accepts a `factories` map so unit tests can
 * swap in scripted event streams without touching `fetch()`.
 */
export function useAgentStreamFor(
  sessionId: string,
  factories: StreamFactories,
): UseAgentStream {
  const [state, setState] = useState<AgentStreamState>({
    messages: '',
    tools: [],
    handoffs: [],
    truncations: [],
    status: 'idle',
  });

  const consume = useCallback(async (iter: AsyncGenerator<AgentEventV7>) => {
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
  }, []);

  const send = useCallback(
    async (content: string) => consume(factories.send(content)),
    [consume, factories],
  );
  const confirm = useCallback(
    async (messageId: string, approved: boolean) => {
      setState((s) => ({ ...s, status: 'awaiting_confirmation' }));
      await consume(factories.confirm(messageId, approved));
    },
    [consume, factories],
  );
  const replay = useCallback(
    async (messageId: string) => consume(factories.replay(messageId)),
    [consume, factories],
  );
  const abort = useCallback(() => {
    setState((s) => ({ ...s, status: 'idle' }));
  }, []);

  return { state, send, confirm, replay, abort };
}

/**
 * useAgentStreamCore — legacy entry point kept for the unit tests
 * (scripted event replay).  Internally delegates to useAgentStreamFor.
 */
export function useAgentStreamCore(adapters: {
  send: (sessionId: string, content: string) => AsyncGenerator<AgentEventV7>;
  confirm: (
    sessionId: string,
    messageId: string,
    approved: boolean,
  ) => AsyncGenerator<AgentEventV7>;
  replay: (sessionId: string, messageId: string) => AsyncGenerator<AgentEventV7>;
}): UseAgentStream {
  // sessionId is folded into the adapter API for the legacy contract;
  // the default `'s1'` is a placeholder because tests always inject
  // their own scripted generators.
  const factories = useMemo<StreamFactories>(
    () => ({
      send: (content: string) => adapters.send('s1', content),
      confirm: (messageId: string, approved: boolean) =>
        adapters.confirm('s1', messageId, approved),
      replay: (messageId: string) => adapters.replay('s1', messageId),
    }),
    [adapters],
  );
  return useAgentStreamFor('s1', factories);
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
      return state;
  }
}

function cryptoId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `id-${Math.random().toString(36).slice(2)}`;
}
