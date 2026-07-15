/**
 * v0.7 cost endpoints — read-only access to the monthly LLM cost
 * breakdown (P2 #49).  Backed by `GET /api/reports/cost/by-month`.
 *
 * The shape is intentionally narrow — `CostByMonth` is defined in
 * `@/types/v0.7` and shared with the recharts dashboard.
 */
import type { CostByMonth } from '@/types/v0.7';
import { request } from './infra';

export const costApi = {
  byMonth(from: string, to: string): Promise<CostByMonth> {
    return request(`/reports/cost/by-month?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`);
  },
};

export type CostApi = typeof costApi;
