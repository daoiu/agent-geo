import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { EmptyState } from './EmptyState';
import { Button } from './Button';

describe('EmptyState', () => {
  it('shows title and description', () => {
    renderWithRouter(<EmptyState title="还没有数据" description="先建一个" />);
    expect(screen.getByText('还没有数据')).toBeInTheDocument();
    expect(screen.getByText('先建一个')).toBeInTheDocument();
  });

  it('renders action slot when provided', () => {
    renderWithRouter(
      <EmptyState title="空" action={<Button>新建</Button>} />
    );
    expect(screen.getByRole('button', { name: '新建' })).toBeInTheDocument();
  });

  it('uses status role for SR announcement', () => {
    renderWithRouter(<EmptyState title="空" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});
