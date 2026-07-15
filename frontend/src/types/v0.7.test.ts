import { describe, it, expect } from 'vitest';
import {
  v0_7_RUNTIME_SENTINEL,
  type HandoffLog,
  type MemorySnapshot,
  type MemoryEntry,
  type TruncationDecision,
  type CostByMonth,
  type FaultConfig,
  type AgentEventV7,
} from './v0.7';

/**
 * Type-only sanity checks — these tests won't catch many runtime issues
 * but they pin the public surface of the v0.7 types so refactors that
 * lose a field are caught at compile time.
 */
describe('v0.7 types', () => {
  it('HandoffLog has required fields', () => {
    const h: HandoffLog = {
      id: 'h1',
      sessionId: 's1',
      fromAgent: 'main',
      toAgent: 'cw',
      taskSummary: 'gen',
      timestamp: 0,
    };
    expect(h.id).toBe('h1');
    expect(h.timestamp).toBe(0);
  });

  it('MemorySnapshot wraps an array of entries with optional preview', () => {
    const e: MemoryEntry = {
      id: 'm1',
      summary: '用户偏好 meta',
      source: 'L2',
      createdAt: 123,
    };
    const s: MemorySnapshot = {
      sessionId: 's1',
      memories: [e],
    };
    expect(s.memories[0]?.source).toBe('L2');
  });

  it('TruncationDecision has strategy + savedTokens', () => {
    const t: TruncationDecision = {
      strategy: 'drop',
      originalTokens: 100,
      finalTokens: 60,
      savedTokens: 40,
    };
    expect(t.strategy).toBe('drop');
    expect(t.savedTokens).toBe(40);
  });

  it('TruncationDecision supports droppedMessages list', () => {
    const t: TruncationDecision = {
      strategy: 'drop',
      originalTokens: 100,
      finalTokens: 60,
      savedTokens: 40,
      droppedMessages: [1, 2, 3],
    };
    expect(t.droppedMessages).toEqual([1, 2, 3]);
  });

  it('CostByMonth has byProvider and byModel arrays', () => {
    const c: CostByMonth = {
      months: [
        {
          month: '2026-06',
          totalCost: 12.34,
          byProvider: [{ provider: 'anthropic', cost: 9.99 }],
          byModel: [{ model: 'claude-opus-4-8', cost: 9.99 }],
        },
      ],
    };
    expect(c.months[0]?.byProvider[0]?.provider).toBe('anthropic');
  });

  it('FaultConfig covers the 5 dev-fault kinds', () => {
    const fc: FaultConfig = {
      kind: 'llm_timeout',
      target: 'next',
      params: { delayMs: 1500 },
    };
    expect(fc.kind).toBe('llm_timeout');
  });

  it('AgentEventV7 union accepts the 3 LangGraph-only events', () => {
    const handoff: AgentEventV7 = {
      event: 'handoff',
      from_agent: 'main',
      to_agent: 'content_writer',
      task_summary: '写文章',
      reason: 'specialist 切换',
      timestamp: 1,
    };
    expect(handoff.event).toBe('handoff');
    const mem: AgentEventV7 = {
      event: 'memory_injected',
      count: 2,
      source: 'L2',
      preview: ['mem1', 'mem2'],
    };
    expect(mem.event).toBe('memory_injected');
    const td: AgentEventV7 = {
      event: 'truncation_decision',
      strategy: 'summarize',
      saved_tokens: 100,
    };
    expect(td.event).toBe('truncation_decision');
  });

  it('v0_7_RUNTIME_SENTINEL proves the module is loadable at runtime', () => {
    // Closes the TDD red→green loop for the case where `./v0.7` is
    // accidentally deleted or stubbed-out: this assertion fails at
    // runtime, vitest reports a transform/import error rather than a
    // silent green run.
    expect(v0_7_RUNTIME_SENTINEL).toBe('geo2.v0.7');
  });
});
