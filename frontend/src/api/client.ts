/**
 * v0.7 client.ts — backward-compatibility re-export shim.
 *
 * The actual request / error / auth-headers logic lives in `./infra`.
 * The composed `api.*` namespace lives in `./index`.  This file only
 * re-exports the union of those surfaces so legacy imports such as
 *   `import { api, ApiError } from '@/api/client'`
 * keep compiling during the v0.6 → v0.7 migration window.
 *
 * New code should prefer `import from '@/api'` (the barrel).
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
