import { describe, it, expect, vi } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen, fireEvent } from '@testing-library/react';
import { NotificationDrawer } from './NotificationDrawer';

describe('NotificationDrawer (v0.7)', () => {
  it('renders nothing when closed', () => {
    const { container } = renderWithRouter(
      <NotificationDrawer open={false} onClose={vi.fn()}>
        hidden
      </NotificationDrawer>,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders a dialog when open with the given title', () => {
    renderWithRouter(
      <NotificationDrawer open onClose={vi.fn()} title="阈值通知">
        阈值已低于 75%
      </NotificationDrawer>,
    );
    expect(screen.getByRole('dialog', { name: '阈值通知' })).toBeInTheDocument();
  });

  it('calls onClose when the X button is clicked', () => {
    const onClose = vi.fn();
    renderWithRouter(
      <NotificationDrawer open onClose={onClose}>
        body
      </NotificationDrawer>,
    );
    fireEvent.click(screen.getByRole('button', { name: '关闭' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when the backdrop is clicked', () => {
    const onClose = vi.fn();
    renderWithRouter(
      <NotificationDrawer open onClose={onClose}>
        body
      </NotificationDrawer>,
    );
    fireEvent.click(screen.getByRole('button', { name: '关闭面板' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('close on Escape key', () => {
    const onClose = vi.fn();
    renderWithRouter(
      <NotificationDrawer open onClose={onClose}>
        body
      </NotificationDrawer>,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
