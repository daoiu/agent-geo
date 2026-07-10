import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { RankBadge } from './RankBadge';

describe('RankBadge', () => {
  it('renders rank number and a11y label', () => {
    renderWithRouter(<RankBadge rank={1} />);
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByLabelText(/第 1 位/)).toBeInTheDocument();
  });

  it('shows up/down trend indicator', () => {
    renderWithRouter(<RankBadge rank={2} trend="up" />);
    expect(screen.getByLabelText(/第 2 位.*up/)).toBeInTheDocument();
  });
});
