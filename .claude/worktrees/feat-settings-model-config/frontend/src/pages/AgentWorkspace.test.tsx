import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';

vi.mock('@/api/client', () => ({
  api: {
    getAgentSession: vi.fn(),
    createAgentSession: vi.fn(),
    confirmAgentAction: vi.fn(),
  },
  sendAgentMessageStream: vi.fn(),
  confirmAgentActionStream: vi.fn(),
}));

import { api } from '@/api/client';
import AgentWorkspace from './AgentWorkspace';
import type { AgentSessionDetail } from '@/types/v0.4';

const mockedApi = vi.mocked(api);

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
  mockedApi.getAgentSession.mockResolvedValue(emptyDetail());
  mockedApi.createAgentSession.mockResolvedValue({
    id: 'new-1',
    title: '新对话',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  });
});

describe('AgentWorkspace (chat pane only)', () => {
  it('shows the empty-state call-to-action when no session is loaded', () => {
    renderWithRouter(<AgentWorkspace />, { initialEntries: ['/agent'] });
    expect(screen.getByRole('heading', { name: /开始对话/ })).toBeInTheDocument();
  });

  it('send button is disabled while input is empty', () => {
    renderWithRouter(<AgentWorkspace />, { initialEntries: ['/agent/recent-7'] });
    const btn = screen.getByRole('button', { name: '发送' });
    expect(btn).toBeDisabled();
  });

  it('typing into the textarea activates the composer (primary border on the whole box)', async () => {
    const user = (await import('@testing-library/user-event')).default;
    renderWithRouter(<AgentWorkspace />, { initialEntries: ['/agent/recent-7'] });
    const ta = screen.getByPlaceholderText(/给 GEO 助手/) as HTMLTextAreaElement;
    await user.click(ta);
    await user.keyboard('帮我看看');
    expect(ta.value).toBe('帮我看看');

    // the send button is no longer disabled
    const btn = screen.getByRole('button', { name: '发送' });
    expect(btn).not.toBeDisabled();

    // the composer wrapper adopts the active border-primary class
    // (we locate it by the textarea's parent <div>)
    const wrapper = ta.parentElement as HTMLElement;
    expect(wrapper.className).toContain('border-primary');
  });

  it('does NOT render the global SideNav (now owned by LayoutShell)', () => {
    renderWithRouter(<AgentWorkspace />, { initialEntries: ['/agent/recent-7'] });
    expect(screen.queryByRole('navigation', { name: /主导航/ })).toBeNull();
    expect(screen.queryByRole('complementary', { name: /会话历史/ })).toBeNull();
  });

  it('first send in /agent creates a new session with the typed text as title', async () => {
    const user = (await import('@testing-library/user-event')).default;
    renderWithRouter(<AgentWorkspace />, { initialEntries: ['/agent'] });

    const ta = screen.getByPlaceholderText(/给 GEO 助手/) as HTMLTextAreaElement;
    await user.click(ta);
    await user.keyboard('帮我诊断小米');

    const btn = screen.getByRole('button', { name: '发送' });
    expect(btn).not.toBeDisabled();
    await user.click(btn);

    // Bug fix assertion: pressing Send in /agent must no longer be a no-op.
    // Previously useAgentSession.send() early-returned on !sessionId and the
    // user message was silently lost. The flow now calls createAgentSession
    // first and seeds the cache with the user message before navigating.
    expect(mockedApi.createAgentSession).toHaveBeenCalledTimes(1);
    expect(mockedApi.createAgentSession).toHaveBeenCalledWith('帮我诊断小米');
  });
});
