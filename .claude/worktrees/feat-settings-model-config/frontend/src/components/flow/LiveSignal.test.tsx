import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { LiveSignal } from './LiveSignal';

describe('LiveSignal', () => {
  it('renders provider name and accessible status label', () => {
    renderWithRouter(<LiveSignal provider="DeepSeek" status="running" progress={42} />);
    const node = screen.getByRole('status');
    expect(node).toHaveAccessibleName(/DeepSeek 运行中 42%/);
  });

  it('renders duration on done', () => {
    renderWithRouter(<LiveSignal provider="Kimi" status="done" durationMs={1234} />);
    expect(screen.getByRole('status')).toHaveAccessibleName(/Kimi 完成 用时 1234ms/);
  });
});
