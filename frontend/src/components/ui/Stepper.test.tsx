import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Stepper } from './Stepper';

describe('Stepper', () => {
  it('marks states done / current / pending based on current index', () => {
    const steps = [
      { key: 'a', title: '品牌' },
      { key: 'b', title: '问题' },
      { key: 'c', title: '启动' },
    ];
    const { container } = renderWithRouter(<Stepper steps={steps} current={1} />);
    const states = Array.from(container.querySelectorAll('li[data-step-state]')).map(
      (li) => li.getAttribute('data-step-state')
    );
    expect(states).toEqual(['done', 'current', 'pending']);
  });

  it('renders titles as text', () => {
    renderWithRouter(
      <Stepper steps={[{ key: 'a', title: '品牌' }, { key: 'b', title: '问题' }]} current={0} />
    );
    expect(screen.getByText('品牌')).toBeInTheDocument();
    expect(screen.getByText('问题')).toBeInTheDocument();
  });
});
