import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Badge } from './Badge';

describe('Badge', () => {
  it('renders with default neutral tone', () => {
    renderWithRouter(<Badge>中性</Badge>);
    expect(screen.getByText('中性')).toBeInTheDocument();
  });

  it('renders with success tone class', () => {
    renderWithRouter(<Badge tone="success">已完成</Badge>);
    expect(screen.getByText('已完成')).toHaveClass('text-success');
  });

  it('renders a leading dot when dot=true', () => {
    const { container } = renderWithRouter(<Badge tone="success" dot>运行中</Badge>);
    expect(container.querySelector('span > span')).toBeInTheDocument();
  });
});
