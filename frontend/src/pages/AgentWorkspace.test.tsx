import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock the api so React Query never touches fetch.
vi.mock('@/api/client', () => ({
  api: {
    listAgentSessions: vi.fn(),
    getAgentSession: vi.fn(),
    createAgentSession: vi.fn(),
    deleteAgentSession: vi.fn(),
    confirmAgentAction: vi.fn(),
  },
  sendAgentMessageStream: vi.fn(),
  confirmAgentActionStream: vi.fn(),
}));

import { api } from '@/api/client';
import AgentWorkspace from './AgentWorkspace';
import type { AgentSession, AgentSessionDetail } from '@/types/v0.4';

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

function emptyDetail(): AgentSessionDetail {
  return {
    id: 'recent-7',
    title: 'Supervisor 含义解析',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    messages: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.listAgentSessions.mockResolvedValue(sessionListFixture());
  mockedApi.getAgentSession.mockResolvedValue(emptyDetail());
  mockedApi.createAgentSession.mockResolvedValue({
    id: 'new-1',
    title: '新对话',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  });
});

describe('AgentWorkspace', () => {
  it('renders 3 mode tabs in the segmented control', () => {
    renderWithRouter(<AgentWorkspace />);
    expect(screen.getByRole('tab', { name: /快速模式/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /专家模式/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /识图模式/ })).toBeInTheDocument();
  });

  it('groups sessions by 7 days / 30 days / YYYY-MM', async () => {
    renderWithRouter(<AgentWorkspace />);
    expect(await screen.findByText('7天内')).toBeInTheDocument();
    expect(await screen.findByText('30天内')).toBeInTheDocument();
    // 80-100 days ago → bucket '2026-XX' (group label)
    const months = await screen.findAllByText(/\d{4}-\d{2}内/);
    expect(months.length).toBeGreaterThanOrEqual(2);
  });

  it('clicking a session routes to /agent/:id', async () => {
    renderWithRouter(<AgentWorkspace />, { initialEntries: ['/agent'] });
    const link = await screen.findByRole('link', { name: 'Supervisor 含义解析' });
    expect(link).toHaveAttribute('href', '/agent/recent-7');
  });

  it('shows the empty-state call-to-action when no session is loaded', () => {
    renderWithRouter(<AgentWorkspace />, { initialEntries: ['/agent'] });
    expect(screen.getByText(/使用快速模式开始对话/)).toBeInTheDocument();
  });

  it('switches mode labels in the empty state', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AgentWorkspace />, { initialEntries: ['/agent'] });
    expect(screen.getByText(/使用快速模式开始对话/)).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: /专家模式/ }));
    expect(screen.getByText(/使用专家模式开始对话/)).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: /识图模式/ }));
    expect(screen.getByText(/使用识图模式开始对话/)).toBeInTheDocument();
  });

  it('send button is disabled while input is empty', () => {
    renderWithRouter(<AgentWorkspace />, { initialEntries: ['/agent/recent-7'] });
    const btn = screen.getByRole('button', { name: '发送' });
    expect(btn).toBeDisabled();
  });

  it('new-session button is rendered at the top of the sidebar', () => {
    renderWithRouter(<AgentWorkspace />, { initialEntries: ['/agent/recent-7'] });
    expect(screen.getByRole('button', { name: /开启新对话/ })).toBeInTheDocument();
  });
});
