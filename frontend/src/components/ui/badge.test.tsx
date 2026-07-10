import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Badge } from './badge.tsx';

describe('Badge (shadcn)', () => {
  it('renders default variant', () => {
    renderWithRouter(<Badge>v0.6</Badge>);
    expect(screen.getByText('v0.6')).toBeInTheDocument();
  });

  it('renders success variant', () => {
    renderWithRouter(<Badge variant="success">已完成</Badge>);
    expect(screen.getByText('已完成')).toHaveClass('text-white');
  });

  it('renders destructive variant', () => {
    renderWithRouter(<Badge variant="destructive">已失败</Badge>);
    expect(screen.getByText('已失败')).toBeInTheDocument();
  });

  it('adds leading dot when dot=true', () => {
    const { container } = renderWithRouter(
      <Badge variant="success" dot>运行中</Badge>
    );
    expect(container.querySelector('span[aria-hidden="true"]')).toBeInTheDocument();
  });
});
