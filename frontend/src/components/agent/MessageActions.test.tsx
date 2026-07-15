import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MessageActions } from './MessageActions';

describe('MessageActions', () => {
  it('renders nothing when isCheckpoint is false (legacy messages)', () => {
    const { container } = render(
      <MessageActions
        sessionId="s1"
        messageId="m1"
        isCheckpoint={false}
        onReplay={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('shows a kebab trigger when isCheckpoint is true', () => {
    render(
      <MessageActions
        sessionId="s1"
        messageId="m-ckpt-42"
        isCheckpoint
        onReplay={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /消息操作/ })).toBeInTheDocument();
  });

  it('opens menu and triggers onReplay when the item is clicked', () => {
    const onReplay = vi.fn();
    render(
      <MessageActions
        sessionId="s1"
        messageId="m-ckpt-42"
        isCheckpoint
        onReplay={onReplay}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /消息操作/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: /重放消息/ }));
    expect(onReplay).toHaveBeenCalledWith('m-ckpt-42');
  });
});
