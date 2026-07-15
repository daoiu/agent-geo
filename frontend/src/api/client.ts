/**
 * v0.7 client.ts — thin compatibility shim.
 *
 * The bottom of the request stack now lives in `./infra.ts` (avoids the
 * circular import that would otherwise form between `./index.ts` and
 * this file).  This file re-exports the public surface unchanged so
 * call sites that still import from `@/api/client` keep working —
 * new code should prefer `@/api` (the barrel).
 */
export { request, ApiError, authHeaders, BASE } from './infra';
export type { RequestOptions } from './types';
export { api } from './index';
export {
  parseSSE,
  sendAgentMessageStream,
  confirmAgentActionStream,
  replayAgentMessageStream,
  LANGGRAPH_ENABLED,
} from './agent';
