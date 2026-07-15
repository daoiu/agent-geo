import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { TimelineRail } from './TimelineRail';
import type { HandoffLog } from '@/types/v0.7';

const HANDOFFS: HandoffLog[] = [
  {
    id: 'h1',
    sessionId: 's1',
    fromAgent: 'main',
    toAgent: 'content_writer',
    taskSummary: '写文章',
    timestamp: 1,
  },
  {
    id: 'h2',
    sessionId: 's1',
    fromAgent: 'content_writer',
    toAgent: 'monitor_specialist',
    taskSummary: '监测表现',
    reason: '需要数据反馈',
    timestamp: 2,
  },
];

describe('TimelineRail', () => {
  it('renders handoff list with agent labels in node order', () => {
    renderWithRouter(
      <TimelineRail
        sessionId="s1"
        handoffs={HANDOFFS}
        currentAgent="monitor_specialist"
      />,
    );
    // Each rendered node carries an accessible label including its agent name.
    const mainBtn = screen.getByRole('button', { name: /main/ });
    expect(mainBtn).toBeDisabled();
    const cwBtn = screen.getByRole('button', { name: /content_writer/ });
    expect(cwBtn).toBeEnabled();
    const msBtn = screen.getByRole('button', { name: /monitor_specialist/ });
    expect(msBtn).toHaveAttribute('aria-current', 'true');
  });

  it('surfaces the latest task summary text', () => {
    renderWithRouter(
      <TimelineRail
        sessionId="s1"
        handoffs={HANDOFFS}
        currentAgent="monitor_specialist"
      />,
    );
    expect(screen.getByText(/监测表现/)).toBeInTheDocument();
  });

  it('renders empty-state when no handoffs recorded', () => {
    renderWithRouter(
      <TimelineRail sessionId="s1" handoffs={[]} currentAgent="main" />,
    );
    expect(screen.getByText(/还没有 specialist 切换/)).toBeInTheDocument();
  });

  it('calls onSelectHandoff when an enabled node is clicked', () => {
    let clickedId: string | null = null;
    renderWithRouter(
      <TimelineRail
        sessionId="s1"
        handoffs={HANDOFFS}
        currentAgent="monitor_specialist"
        onSelectHandoff={(id) => {
          clickedId = id;
        }}
      />,
    );
    const cwBtn = screen.getByRole('button', { name: /content_writer/ });
    cwBtn.click();
    expect(clickedId).toBe('h1');
  });
});
