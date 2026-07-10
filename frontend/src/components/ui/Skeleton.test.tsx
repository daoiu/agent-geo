import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Skeleton, SkeletonList } from './Skeleton';

describe('Skeleton', () => {
  it('renders with status role', () => {
    renderWithRouter(<Skeleton />);
    expect(screen.getByRole('status', { name: '加载中' })).toBeInTheDocument();
  });

  it('renders N inner skeleton rows plus the list container', () => {
    const { container } = renderWithRouter(<SkeletonList count={5} />);
    // 5 inner <Skeleton /> rows + 1 outer list container (each with role="status")
    expect(container.querySelectorAll('[role="status"]')).toHaveLength(6);
    expect(container.querySelectorAll('[aria-label="加载列表"]')).toHaveLength(1);
  });
});
