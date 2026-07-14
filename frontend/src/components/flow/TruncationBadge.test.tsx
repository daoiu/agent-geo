import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { TruncationBadge } from './TruncationBadge';

describe('TruncationBadge (v0.7)', () => {
  it('renders noop gray with no tokens saved line', () => {
    renderWithRouter(<TruncationBadge strategy="noop" savedTokens={0} />);
    const node = screen.getByText(/压缩无需/);
    expect(node).toHaveClass('bg-gray-100');
  });

  it('renders truncate primary tint with formatted kilotokens', () => {
    renderWithRouter(<TruncationBadge strategy="truncate" savedTokens={1200} />);
    const node = screen.getByText(/截断 · 节省 1\.2k tokens/);
    expect(node).toHaveClass('bg-primary-tint');
  });

  it('renders drop warning with formatted kilotokens', () => {
    renderWithRouter(<TruncationBadge strategy="drop" savedTokens={3400} />);
    const node = screen.getByText(/丢弃 · 节省 3\.4k tokens/);
    expect(node).toHaveClass('bg-warning/20');
  });

  it('renders summarize accent tint with formatted kilotokens', () => {
    renderWithRouter(<TruncationBadge strategy="summarize" savedTokens={5100} />);
    const node = screen.getByText(/摘要 · 节省 5\.1k tokens/);
    expect(node).toHaveClass('bg-accent/30');
  });
});
