/**
 * v0.7 shared API typings.
 *
 *   `RequestOptions`  — extends `RequestInit` with our app-level
 *                       extensions (currently `signal` for cancellation
 *                       and a passthrough-friendly `headers` typing).
 *
 * Used by every domain module (diagnosis/knowledge/generate/publish/
 * monitor/agent) and by the top-level `request<T>` helper in infra.ts.
 * Callers that need `RequestInit` itself should import directly from
 * the DOM lib (`lib.dom.d.ts`).
 */

export interface RequestOptions extends Omit<RequestInit, 'signal'> {
  /** AbortSignal for cancellation. Forwarded into `fetch()`. */
  signal?: AbortSignal;
}
