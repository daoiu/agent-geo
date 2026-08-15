import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { ReasoningTrace, type TraceEvent } from './ReasoningTrace';

const SAMPLE: TraceEvent[] = [
  { kind: 'thought', text: '我会先查一下', ts: 0 },
  { kind: 'tool_call', tool: 'search_knowledge', args: { q: '小米' }, status: 'done', ts: 1, result: { found: 5 } },
  { kind: 'llm_query', provider: 'DeepSeek', status: 'done', ts: 2, durationMs: 1234 },
  { kind: 'final', text: '完成', ts: 3 },
];

describe('ReasoningTrace', () => {
  it('renders events in order with role list', () => {
    renderWithRouter(<ReasoningTrace events={SAMPLE} />);
    expect(screen.getByRole('list', { name: 'Agent 推理时间线' })).toBeInTheDocument();
    expect(screen.getByText(/我会先查一下/)).toBeInTheDocument();
  });

  it('collapses when over threshold', () => {
    const many: TraceEvent[] = Array.from({ length: 60 }, (_, i) => ({
      kind: 'thought',
      text: `t${i}`,
      ts: i,
    }));
    renderWithRouter(<ReasoningTrace events={many} collapsibleThreshold={50} />);
    expect(screen.getByText(/展开 10 条历史推理/)).toBeInTheDocument();
  });
});
