/**
 * v0.7 api/infra — the bottom of the request stack.
 *
 *   - `BASE` constant
 *   - `authHeaders()` — injects X-Device-Id + JSON content-type
 *   - `request<T>(path, init)` — JSON fetch with AbortSignal + auth headers
 *   - `ApiError` — class with status / message / optional code
 *
 * Lives in its own module so domain modules (`./diagnosis`, `./knowledge`,
 * ...) and the SSE helpers can import from here without creating a
 * cycle through `./index.ts` (which composes them into the `api`
 * namespace).
 */
import { getDeviceId } from '@/lib/deviceId';
import type { RequestOptions } from './types';

export const BASE = '/api';

/**
 * ApiError — rejected from `request<T>` (and the SSE helpers) when the
 * server returns a non-OK response. v0.7 adds an optional `code` field
 * so the UI can show a stable diagnostic label (e.g. "not_found",
 * "session_busy") without parsing the message body.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function authHeaders(extra?: HeadersInit): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-Device-Id': getDeviceId(),
    ...(extra as Record<string, string> | undefined),
  };
}

export async function request<T>(
  path: string,
  init: RequestOptions = {},
): Promise<T> {
  const { signal, headers, ...rest } = init;
  const resp = await fetch(`${BASE}${path}`, {
    headers: authHeaders(headers),
    signal,
    ...rest,
  });
  if (!resp.ok) {
    const body = await resp.text();
    let code: string | undefined;
    try {
      const parsed = JSON.parse(body) as { error_code?: string };
      code = parsed.error_code;
    } catch {
      // body wasn't JSON — leave code undefined
    }
    throw new ApiError(resp.status, body || resp.statusText, code);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}
