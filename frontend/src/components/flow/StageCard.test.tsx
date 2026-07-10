import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { StageCard } from './StageCard';

describe('StageCard', () => {
  it('shows progressbar with current value when progress < 100', () => {
    renderWithRouter(<StageCard title="爬虫" status="running" progress={42} />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '42');
  });

  it('hides progressbar when status=done', () => {
    renderWithRouter(<StageCard title="爬虫" status="done" progress={100} />);
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('uses success badge when done', () => {
    const { container } = renderWithRouter(
      <StageCard title="爬虫" status="done" progress={100} />
    );
    expect(container.querySelector('[data-stage-status="done"]')).toBeInTheDocument();
  });
});
