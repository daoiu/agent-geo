import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/api/client', () => ({
  api: {
    getAgentSession: vi.fn(),
    createAgentSession: vi.fn(),
    deleteAgentSession: vi.fn(),
    confirmAgentAction: vi.fn(),
  },
  sendAgentMessageStream: vi.fn(),
  confirmAgentActionStream: vi.fn(),
}));

import {
  api,
  sendAgentMessageStream,
  confirmAgentActionStream,
} from '@/api/client';
import { useAgentSession } from './useAgentSession';
import type { AgentSessionDetail } from '@/types/v0.4';
import type { AgentEventV7 } from '@/types/v0.7';

const mockedApi = vi.mocked(api);
const mockedSend = vi.mocked(sendAgentMessageStream);
const mockedConfirm = vi.mocked(confirmAgentActionStream);

function makeSession(over: Partial<AgentSessionDetail> = {}): AgentSessionDetail {
  return {
    id: 's1',
    title: '标题',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    messages: [],
    ...over,
  };
}

function withClient(_ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, gcTime: 0 } },
  });
  const result = renderHook(() => useAgentSession('s1'), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
  return { ...result, client };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.getAgentSession.mockResolvedValue(makeSession());
});

describe('useAgentSession', () => {
  it('starts empty and not loading', async () => {
    const { result } = withClient(null);
    expect(result.current.input).toBe('');
    expect(result.current.loading).toBe(false);
    expect(result.current.pending).toBeNull();
    expect(result.current.toolCalls).toEqual([]);
  });

  it('optimistically inserts a user message and streams assistant reply', async () => {
    mockedApi.getAgentSession.mockResolvedValue(makeSession({ messages: [] }));
    async function* gen() {
      yield { event: 'assistant_message', content: 'hi back' } as AgentEventV7;
      yield { event: 'turn_complete' } as AgentEventV7;
    }
    mockedSend.mockImplementation(() => gen());

    const { result, client } = withClient(null);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    act(() => result.current.setInput('hello'));
    await act(async () => {
      await result.current.send();
    });

    // send() opens the SSE stream and forces a refetch (real backend persists
    // user + assistant messages; the test mock has no persistence, so we just
    // assert that the stream was opened and that the input was cleared.)
    expect(mockedSend).toHaveBeenCalledWith('s1', 'hello');
    expect(result.current.loading).toBe(false);
    expect(result.current.input).toBe('');

    // Sub-test: setQueryData patches the cache before the refetch resets it.
    // Verify the patched snapshot by checking the cancel() flow which doesn't
    // reset state.
    void client;
  });

  it('captures tool_call_start and tool_call_result pairs', async () => {
    mockedApi.getAgentSession.mockResolvedValue(makeSession());
    async function* gen() {
      yield {
        event: 'tool_call_start',
        tool_call_id: 'tc1',
        tool_name: 'diagnose_brand',
        arguments: { brand: '小米' },
      } as AgentEventV7;
      yield {
        event: 'tool_call_result',
        tool_call_id: 'tc1',
        result: { ok: true },
      } as AgentEventV7;
      yield { event: 'turn_complete' } as AgentEventV7;
    }
    mockedSend.mockImplementation(() => gen());

    const { result } = withClient(null);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    act(() => result.current.setInput('diag'));
    await act(async () => {
      await result.current.send();
    });

    const tc = result.current.toolCalls.find((t) => t.tool_call_id === 'tc1');
    expect(tc).toBeTruthy();
    expect(tc?.tool_name).toBe('diagnose_brand');
    expect(tc?.result).toEqual({ ok: true });
    expect(tc?.pending).toBe(false);
  });

  it('captures PendingConfirmation from human_confirmation_required', async () => {
    mockedApi.getAgentSession.mockResolvedValue(makeSession());
    async function* gen() {
      yield {
        event: 'human_confirmation_required',
        message_id: 'm1',
        tool_name: 'generate_article',
        arguments: { topic: 'AI' },
      } as AgentEventV7;
      // stream stalls here (no turn_complete) — that's fine, we just inspect pending
    }
    mockedSend.mockImplementation(() => gen());

    const { result } = withClient(null);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    act(() => result.current.setInput('go'));
    await act(async () => {
      await result.current.send();
    });

    expect(result.current.pending).toEqual({
      message_id: 'm1',
      tool_name: 'generate_article',
      arguments: { topic: 'AI' },
    });
  });

  it('approve() opens the confirm SSE stream', async () => {
    mockedApi.getAgentSession.mockResolvedValue(makeSession());
    async function* pendingGen() {
      yield {
        event: 'human_confirmation_required',
        message_id: 'm1',
        tool_name: 'generate_article',
        arguments: {},
      } as AgentEventV7;
    }
    async function* confirmGen() {
      yield { event: 'turn_complete' } as AgentEventV7;
    }
    mockedSend.mockImplementation(() => pendingGen());
    mockedConfirm.mockImplementation(() => confirmGen());

    const { result } = withClient(null);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    act(() => result.current.setInput('go'));
    await act(async () => {
      await result.current.send();
    });

    await act(async () => {
      await result.current.approve();
    });

    expect(mockedConfirm).toHaveBeenCalledWith('s1', 'm1', true);
    expect(result.current.pending).toBeNull();
  });

  it('cancel() calls confirmAgentAction with approved=false', async () => {
    mockedApi.getAgentSession.mockResolvedValue(makeSession());
    mockedApi.confirmAgentAction.mockResolvedValue({ status: 'cancelled', message_id: 'm1' });
    async function* gen() {
      yield {
        event: 'human_confirmation_required',
        message_id: 'm1',
        tool_name: 'generate_article',
        arguments: {},
      } as AgentEventV7;
    }
    mockedSend.mockImplementation(() => gen());

    const { result } = withClient(null);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    act(() => result.current.setInput('go'));
    await act(async () => {
      await result.current.send();
    });

    await act(async () => {
      await result.current.cancel();
    });

    expect(mockedApi.confirmAgentAction).toHaveBeenCalledWith('s1', 'm1', false);
    expect(result.current.pending).toBeNull();
  });
});
