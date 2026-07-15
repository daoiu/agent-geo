/**
 * v0.7 handoff endpoints — read-only access to the multi-agent
 * handoff history for a session.
 *
 * Mounted route (backend):
 *   GET /api/agent/sessions/{session_id}/handoffs
 *
 * Returns `{ handoffs: HandoffLog[] }`. The API contract matches the
 * `HandoffLog` shape in `types/v0.7.ts`.
 */
import type { HandoffLog } from '@/types/v0.7';
import { request } from './infra';

export const handoffApi = {
  listForSession(sessionId: string): Promise<HandoffLog[]> {
    return request<HandoffLog[]>(`/agent/sessions/${sessionId}/handoffs`);
  },
};

export type HandoffApi = typeof handoffApi;
