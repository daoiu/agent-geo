import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';

vi.mock('@/api/client', () => ({
  api: {
    listAgentSessions: vi.fn(),
    deleteAgentSession: vi.fn(),
    createAgentSession: vi.fn(),
  },
}));

import { api } from '@/api/client';
import { AgentSessionListPanel } from './AgentSessionListPanel';
import type { AgentSession } from '@/types/v0.4';

const mockedApi = vi.mocked(api);

function sessionListFixture(): AgentSession[] {
  const now = Date.now();
  return [
    { id: 'old-month-a', title: 'LangChain 议题', created_at: new Date(now - 200 * 86_400_000).toISOString(), updated_at: new Date(now - 200 * 86_400_000).toISOString() },
    { id: 'recent-7', title: 'Supervisor 含义解析', created_at: new Date(now - 2 * 86_400_000).toISOString(), updated_at: new Date(now - 2 * 86_400_000).toISOString() },
    { id: 'recent-30', title: 'API 模型名称错误修正', created_at: new Date(now - 20 * 86_400_000).toISOString(), updated_at: new Date(now - 20 * 86_400_000).toISOString() },
    { id: 'old-month-b', title: 'Script Install Redirect', created_at: new Date(now - 350 * 86_400_000).toISOString(), updated_at: new Date(now - 350 * 86_400_000).toISOString() },
  ];
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.listAgentSessions.mockResolvedValue(sessionListFixture());
  mockedApi.deleteAgentSession.mockResolvedValue(undefined);
});

describe('AgentSessionListPanel', () => {
  it('groups sessions by 7 days / 30 days / YYYY-MM', async () => {
    renderWithRouter(<AgentSessionListPanel />);
    expect(await screen.findByText('7天内')).toBeInTheDocument();
    expect(await screen.findByText('30天内')).toBeInTheDocument();
    const months = await screen.findAllByText(/\d{4}-\d{2}内/);
    expect(months.length).toBeGreaterThanOrEqual(2);
  });

  it('clicking a session routes to /agent/:id', async () => {
    renderWithRouter(<AgentSessionListPanel />, { initialEntries: ['/agent'] });
    const link = await screen.findByRole('link', { name: 'Supervisor 含义解析' });
    expect(link).toHaveAttribute('href', '/agent/recent-7');
  });

  it('new-session button is rendered at the top of the column', () => {
    renderWithRouter(<AgentSessionListPanel />, { initialEntries: ['/agent/recent-7'] });
    expect(screen.getByRole('button', { name: /开启新对话/ })).toBeInTheDocument();
  });
});
