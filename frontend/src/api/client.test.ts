import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { api, request, ApiError, sendAgentMessageStream, confirmAgentActionStream } from './client';
import { _resetDeviceIdForTest } from '@/lib/deviceId';

describe('X-Device-Id header injection', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  let capturedInit: RequestInit | undefined;

  beforeEach(() => {
    _resetDeviceIdForTest();
    // 给 fetch 一个固定的 ok 响应,避免测试卡在 json 解析
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
      capturedInit = init;
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
  });

  afterEach(() => {
    fetchSpy.mockRestore();
    capturedInit = undefined;
  });

  it('sends X-Device-Id on every api.* call (request<T> wrapper)', async () => {
    await api.getTask('task-x');
    const headers = (capturedInit?.headers ?? {}) as Record<string, string>;
    expect(headers['X-Device-Id']).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
  });

  it('sends X-Device-Id on sendAgentMessageStream (SSE)', async () => {
    // SSE 用 fetch 不消费 body —— 给一个空 ReadableStream 即可
    const empty = new ReadableStream({
      start(controller) {
        controller.close();
      },
    });
    fetchSpy.mockImplementationOnce(async (_input: RequestInfo | URL, init?: RequestInit) => {
      capturedInit = init;
      return new Response(empty, { status: 200 });
    });
    // drain the generator
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    for await (const _evt of sendAgentMessageStream('sess-1', 'hi')) {
      // intentionally empty
    }
    const headers = (capturedInit?.headers ?? {}) as Record<string, string>;
    expect(headers['X-Device-Id']).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
  });

  it('sends X-Device-Id on confirmAgentActionStream (SSE confirm)', async () => {
    const empty = new ReadableStream({
      start(controller) {
        controller.close();
      },
    });
    fetchSpy.mockImplementationOnce(async (_input: RequestInfo | URL, init?: RequestInit) => {
      capturedInit = init;
      return new Response(empty, { status: 200 });
    });
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    for await (const _evt of confirmAgentActionStream('sess-1', 'msg-1', true)) {
      // intentionally empty
    }
    const headers = (capturedInit?.headers ?? {}) as Record<string, string>;
    expect(headers['X-Device-Id']).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
  });
});

describe('request<T> AbortSignal (v0.7)', () => {
  it('rejects with AbortError when signal is already aborted', async () => {
    const ctrl = new AbortController();
    ctrl.abort();
    await expect(
      request('/anything', { signal: ctrl.signal }),
    ).rejects.toThrow();
  });

  it('forwards signal into the underlying fetch()', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response('{}', { status: 200 }));
    const ctrl = new AbortController();
    await request('/x', { signal: ctrl.signal }).catch(() => undefined);
    const init = (fetchSpy.mock.calls[0]?.[1] ?? {}) as RequestInit;
    expect(init.signal).toBe(ctrl.signal);
    fetchSpy.mockRestore();
  });
});

describe('ApiError (v0.7)', () => {
  it('carries status, message, and code', () => {
    const e = new ApiError(404, 'not found', 'not_found');
    expect(e.status).toBe(404);
    expect(e.message).toBe('not found');
    expect(e.code).toBe('not_found');
  });

  it('code is optional — older call sites can omit it', () => {
    const e = new ApiError(500, 'boom');
    expect(e.status).toBe(500);
    expect(e.code).toBeUndefined();
  });
});
