/**
 * v0.7 智能助手 (agent) endpoints — sessions, confirmations, the
 * message stream, and Replay. The SSE parser (`parseSSE`) lives here
 * because both `sendAgentMessageStream` and `confirmAgentActionStream`
 * need it; v0.7 also adds a `replayAgentMessage` stream (Task 10).
 *
 * Mounted routes (App.tsx): `/agent`, `/agent/:sessionId`.
 *
 * **LANGGRAPH_ENABLED flag (spec §6.2 / §8.7)** — at construction time
 * v0.7 reads `import.meta.env.VITE_LANGGRAPH_ENABLED` to decide whether
 * the response payloads should be parsed with the new LangGraph schema
 * or the legacy react_loop schema.  The default is `false` so existing
 * callers do not break.
 */
import type { AgentEvent, AgentSession, AgentSessionDetail } from '@/types/v0.4';
import { authHeaders, request } from './infra';

export const LANGGRAPH_ENABLED =
  (import.meta as unknown as { env: Record<string, string | undefined> }).env
    .VITE_LANGGRAPH_ENABLED === 'true';

export const agentApi = {
  listAgentSessions(): Promise<AgentSession[]> {
    return request('/agent/sessions');
  },

  createAgentSession(title?: string): Promise<AgentSession> {
    return request('/agent/sessions', {
      method: 'POST',
      body: JSON.stringify(title ? { title } : {}),
    });
  },

  getAgentSession(id: string): Promise<AgentSessionDetail> {
    return request(`/agent/sessions/${id}`);
  },

  deleteAgentSession(id: string): Promise<void> {
    return request(`/agent/sessions/${id}`, { method: 'DELETE' });
  },

  updateAgentSessionTitle(id: string, title: string): Promise<AgentSession> {
    return request(`/agent/sessions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    });
  },

  confirmAgentAction(
    sessionId: string,
    messageId: string,
    approved: boolean,
    options?: { reason?: string },
  ): Promise<{ status: string; message_id: string }> {
    // v0.7 — when rejecting, `reason` is mandatory and enters the LLM
    // context (P1 #26).  When approving, we omit it entirely so the
    // backend sees `None` rather than empty string.
    const body: { approved: boolean; reason?: string } = { approved };
    if (!approved && options?.reason) body.reason = options.reason;
    return request(`/agent/sessions/${sessionId}/messages/${messageId}/confirm`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  /**
   * Replay API (Task 10) — POST to `/sessions/{sid}/replay/{msg_id}`,
   * returns the same SSE schema as a fresh send message.
   * The body is empty; the response is the resumption stream itself.
   */
  replayAgentMessage(sessionId: string, messageId: string): Promise<Response> {
    return fetch(`/api/agent/sessions/${sessionId}/replay/${messageId}`, {
      method: 'POST',
      headers: authHeaders(),
    });
  },
};

// ---------------------------------------------------------------------------
// SSE streaming helpers + parser.  Kept in agent.ts because they are
// exclusively consumed by agent surfaces; v0.7 Task 7 will branch the
// parser based on `LANGGRAPH_ENABLED`.
// ---------------------------------------------------------------------------

interface ParsedSSE {
  events: AgentEvent[];
  remainder: string;
}

/**
 * Parse a chunk of SSE text into zero or more `AgentEvent`s.
 * Handles partial buffers — call repeatedly with the cumulative text and
 * carry the returned `remainder` into the next invocation.
 *
 * v0.7 supports the legacy react_loop schema (8 events) and the
 * LangGraph schema (10 events including handoff / memory_injected /
 * truncation_decision). Both share the `event: <name>` framing so the
 * line-level parser is identical; downstream consumers see the variant
 * by reading `event` field.  `useAgentStream` (Task 7) does the typing.
 */
export function parseSSE(buffer: string): ParsedSSE {
  const events: AgentEvent[] = [];
  const lines = buffer.split('\n');
  let remainder = '';
  let currentEvent: string | null = null;
  let currentData: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith('event: ')) {
      currentEvent = line.slice(7).trim();
    } else if (line.startsWith('data: ')) {
      currentData.push(line.slice(6).trim());
    } else if (line === '' && currentEvent && currentData.length > 0) {
      try {
        const data = JSON.parse(currentData.join('\n'));
        events.push({ event: currentEvent, ...data } as AgentEvent);
      } catch {
        // ignore malformed event frames — SSE is lossy by design
      }
      currentEvent = null;
      currentData = [];
    } else if (i === lines.length - 1 && line !== '') {
      // last line may be partial — defer to next chunk
      remainder = line;
    }
  }
  return { events, remainder };
}

async function* sseGenerator(
  url: string,
  init: RequestInit,
): AsyncGenerator<AgentEvent> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`SSE HTTP ${response.status}`);
  }
  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, remainder } = parseSSE(buffer);
    buffer = remainder;
    for (const evt of events) yield evt;
  }
}

export async function* sendAgentMessageStream(
  sessionId: string,
  content: string,
): AsyncGenerator<AgentEvent> {
  yield* sseGenerator(`/api/agent/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ content }),
  });
}

export async function* confirmAgentActionStream(
  sessionId: string,
  messageId: string,
  approved: boolean,
): AsyncGenerator<AgentEvent> {
  yield* sseGenerator(
    `/api/agent/sessions/${sessionId}/messages/${messageId}/confirm`,
    {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ approved }),
    },
  );
}

export async function* replayAgentMessageStream(
  sessionId: string,
  messageId: string,
): AsyncGenerator<AgentEvent> {
  yield* sseGenerator(
    `/api/agent/sessions/${sessionId}/replay/${messageId}`,
    {
      method: 'POST',
      headers: authHeaders(),
    },
  );
}

export type AgentApi = typeof agentApi;
