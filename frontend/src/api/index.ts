/**
 * v0.7 API barrel — the recommended entry point for callers.
 *
 *   - `request<T>(path, init?)` — JSON fetch with AbortSignal + X-Device-Id
 *   - `ApiError` — class with status / message / code
 *   - per-domain namespaces: `diagnosisApi`, `knowledgeApi`, `generateApi`,
 *     `publishApi`, `monitorApi`, `agentApi`
 *   - `api` — flat alias composing all six namespaces; preserved for
 *     legacy callers (`api.getTask(...)` etc.) until they migrate.
 *
 * The legacy `api` shape is also re-exported from `./client.ts` so
 * existing imports of `@/api/client` keep compiling.
 */
export { request, ApiError, authHeaders, BASE } from './client';
export type { RequestOptions } from './types';

import { diagnosisApi } from './diagnosis';
import { knowledgeApi } from './knowledge';
import { generateApi } from './generate';
import { publishApi } from './publish';
import { monitorApi } from './monitor';
import {
  agentApi,
  parseSSE,
  sendAgentMessageStream,
  confirmAgentActionStream,
  replayAgentMessageStream,
  LANGGRAPH_ENABLED,
} from './agent';
import { handoffApi } from './handoff';
import { costApi } from './cost';

export {
  parseSSE,
  sendAgentMessageStream,
  confirmAgentActionStream,
  replayAgentMessageStream,
  LANGGRAPH_ENABLED,
};

export {
  diagnosisApi,
  knowledgeApi,
  generateApi,
  publishApi,
  monitorApi,
  agentApi,
  handoffApi,
  costApi,
};

/**
 * Legacy `api` namespace — composes every per-domain API into a single
 * object so older call sites (`api.getTask(...)`, `api.listReports()`,
 * `api.uploadDocument(...)`, etc.) keep working. New code should
 * import the per-domain namespace it actually needs.
 */
export const api = {
  ...diagnosisApi,
  ...knowledgeApi,
  ...generateApi,
  ...publishApi,
  ...monitorApi,
  ...agentApi,
  ...handoffApi,
  ...costApi,
};
