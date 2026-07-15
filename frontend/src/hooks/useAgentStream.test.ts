import { describe, it, expect } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useAgentStreamFor, type StreamFactories } from './useAgentStream';
import type { AgentEventV7 } from '@/types/v0.7';

/**
 * useAgentStream is consumed by AgentWorkspace (红线 1) and TimelineRail
 * (Task 8).  These tests exercise the reducer via `useAgentStreamFor`
 * with injected `StreamFactories` so a known event sequence can be
 * replayed without touching `fetch()`.
 */

async function* scripted(events: AgentEventV7[]): AsyncGenerator<AgentEventV7> {
  for (const e of events) yield e;
}

function makeFactories(events: AgentEventV7[]): StreamFactories {
  return {
    send: () => scripted(events),
    confirm: () => scripted(events),
    replay: () => scripted(events),
  };
}

describe('useAgentStreamFor (sessionId-bound)', () => {
  it('accumulates llm_token deltas into state.messages', async () => {
    const { result } = renderHook(() =>
      useAgentStreamFor(
        's1',
        makeFactories([
          { event: 'llm_token', delta: 'Hel' },
          { event: 'llm_token', delta: 'lo' },
        ]),
      ),
    );
    await act(async () => {
      await result.current.send('hi');
    });
    expect(result.current.state.messages).toBe('Hello');
    expect(result.current.state.status).toBe('idle');
  });

  it('records handoffs from LangGraph handoff events', async () => {
    const events: AgentEventV7[] = [
      {
        event: 'handoff',
        from_agent: 'main',
        to_agent: 'content_writer',
        task_summary: 'draft article',
        timestamp: 1,
      },
    ];
    const { result } = renderHook(() => useAgentStreamFor('s1', makeFactories(events)));
    await act(async () => {
      await result.current.send('help');
    });
    expect(result.current.state.handoffs).toHaveLength(1);
    expect(result.current.state.handoffs[0].fromAgent).toBe('main');
    expect(result.current.state.handoffs[0].toAgent).toBe('content_writer');
  });

  it('records truncation_decision into state.truncations', async () => {
    const events: AgentEventV7[] = [
      { event: 'truncation_decision', strategy: 'drop', saved_tokens: 400 },
    ];
    const { result } = renderHook(() => useAgentStreamFor('s1', makeFactories(events)));
    await act(async () => {
      await result.current.send('help');
    });
    expect(result.current.state.truncations).toHaveLength(1);
    expect(result.current.state.truncations[0].strategy).toBe('drop');
    expect(result.current.state.truncations[0].savedTokens).toBe(400);
  });

  it('marks status=error when the iterator throws', async () => {
    async function* failing(): AsyncGenerator<AgentEventV7> {
      yield { event: 'llm_token', delta: 'partial' };
      throw new Error('connection lost');
    }
    const { result } = renderHook(() =>
      useAgentStreamFor('s1', {
        send: () => failing(),
        confirm: () => failing(),
        replay: () => failing(),
      }),
    );
    await act(async () => {
      await result.current.send('hi');
    });
    expect(result.current.state.status).toBe('error');
    expect(result.current.state.error).toBe('connection lost');
    expect(result.current.state.messages).toBe('partial');
  });
});
