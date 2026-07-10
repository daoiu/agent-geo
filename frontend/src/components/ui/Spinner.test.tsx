import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Spinner } from './Spinner';

describe('Spinner', () => {
  it('renders with status role and default label', () => {
    renderWithRouter(<Spinner />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', '加载中');
  });

  it('accepts a custom label', () => {
    renderWithRouter(<Spinner label="生成中" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', '生成中');
  });
});
