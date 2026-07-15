/**
 * v0.7 type extensions on top of v0.4.
 *
 * These types back the 10 backend SSE event variants introduced by the
 * LangGraph swap (spec §6.2). The legacy 7 react_loop event variants
 * remain exported from `./v0.4.ts`; `AgentEventV7` is the discriminated
 * union consumed by `useAgentStream` (Task 7) — it widens `AgentEvent`
 * by adding the 3 LangGraph-only events plus a few compat variants.
 */

import type { AgentSessionDetail } from './v0.4';

// ---------------------------------------------------------------------------
// Truncation (P2 #36/#37)
// ---------------------------------------------------------------------------

export type TruncationStrategy = 'noop' | 'truncate' | 'drop' | 'summarize';

export interface TruncationDecision {
  strategy: TruncationStrategy;
  originalTokens: number;
  finalTokens: number;
  savedTokens: number;
  /** Indices of the dropped messages, when strategy === 'drop'. */
  droppedMessages?: number[];
}

// ---------------------------------------------------------------------------
// Multi-Agent handoff (LangGraph-only event)
// ---------------------------------------------------------------------------

export interface HandoffLog {
  id: string;
  sessionId: string;
  fromAgent: string;
  toAgent: string;
  taskSummary: string;
  reason?: string;
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Memory injection (LangGraph-only event)
// ---------------------------------------------------------------------------

export interface MemoryEntry {
  id: string;
  summary: string;
  source: 'L1' | 'L2';
  createdAt: number;
}

export interface MemorySnapshot {
  sessionId: string;
  memories: MemoryEntry[];
}

// ---------------------------------------------------------------------------
// Monthly cost dashboard (P2 #49)
// ---------------------------------------------------------------------------

export interface CostByMonth {
  months: Array<{
    month: string; // YYYY-MM
    totalCost: number;
    byProvider: Array<{ provider: string; cost: number }>;
    byModel: Array<{ model: string; cost: number }>;
  }>;
}

// ---------------------------------------------------------------------------
// Dev fault injector (P2 #31) — gated by `import.meta.env.DEV`
// ---------------------------------------------------------------------------

export type FaultConfig = {
  kind: 'llm_timeout' | 'tool_error' | 'network_503' | 'rate_limit' | 'partial_stream';
  target: 'next' | { durationSec: number };
  params?: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// AgentEventV7 — wider union than v0.4's AgentEvent.  Subsumes the legacy
// 7-event react_loop schema plus 3 LangGraph-only events. The parser in
// api/agent.ts dispatches based on the LANGGRAPH_ENABLED flag; runtime
// consumers (`useAgentStream`) see one union.
// ---------------------------------------------------------------------------

export type AgentEventV7 =
  | { event: 'llm_start'; node: string }
  | { event: 'llm_token'; delta: string }
  | { event: 'tool_call'; name: string; args: unknown }
  | { event: 'tool_result'; name: string; result: unknown; latency_ms: number }
  | {
      event: 'handoff';
      from_agent: string;
      to_agent: string;
      task_summary: string;
      reason?: string;
      timestamp: number;
    }
  | {
      event: 'memory_injected';
      count: number;
      source: 'L1' | 'L2';
      preview?: string[];
    }
  | {
      event: 'truncation_decision';
      strategy: TruncationStrategy;
      saved_tokens: number;
    }
  | { event: 'max_iterations_reached'; iterations: number }
  | { event: 'turn_complete'; final_message: string }
  | { event: 'llm_error'; kind: string; message: string }
  // legacy react_loop shapes kept for backward compat
  | { event: 'assistant_message'; content: string }
  | {
      event: 'tool_call_start';
      tool_call_id: string;
      tool_name: string;
      arguments: Record<string, unknown>;
    }
  | {
      event: 'tool_call_result';
      tool_call_id: string;
      result: Record<string, unknown>;
    }
  | {
      event: 'human_confirmation_required';
      message_id: string;
      tool_name: string;
      arguments: Record<string, unknown>;
    }
  | { event: 'turn_complete_legacy' }
  | { event: 'error'; message: string };

// ---------------------------------------------------------------------------
// Session detail additions (last_checkpoint_message_id for Replay API)
// ---------------------------------------------------------------------------

export interface AgentSessionDetailV7 extends AgentSessionDetail {
  last_checkpoint_message_id?: string;
  handoff_logs?: HandoffLog[];
  memory_snapshot?: MemorySnapshot;
}
