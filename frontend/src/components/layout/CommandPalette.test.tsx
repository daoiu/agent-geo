import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

// useNavigate is consumed by CommandPalette
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = (await importOriginal()) as object;
  return { ...actual, useNavigate: () => mockNavigate };
});

import { CommandPalette } from './CommandPalette';

describe('CommandPalette ⌘K', () => {
  it('includes "历史报告" now that navConfig points it to /reports', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/']}>
        <CommandPalette open={true} onOpenChange={() => {}} />
      </MemoryRouter>,
    );
    const input = screen.getByPlaceholderText(/搜索页面/);
    await user.type(input, '历史报告');
    // Item from the flattened navconfig should be selectable; the entry shows
    // up as a button with "历史报告" + "/reports" shortcut
    const item = await screen.findByText('历史报告');
    expect(item).toBeInTheDocument();
    // Shortcut shows the target URL
    expect(screen.getByText('/reports')).toBeInTheDocument();
  });

  it('invokes navigate when an item is picked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <MemoryRouter initialEntries={['/']}>
        <CommandPalette open={true} onOpenChange={onClose} />
      </MemoryRouter>,
    );
    await user.type(screen.getByPlaceholderText(/搜索页面/), '仪表盘');
    await user.keyboard('{Enter}');
    expect(mockNavigate).toHaveBeenCalledWith('/');
    expect(onClose).toHaveBeenCalledWith(false);
  });
});
