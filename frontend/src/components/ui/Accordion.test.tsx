import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Accordion } from './Accordion';

describe('Accordion', () => {
  it('opens default items and toggles on click', async () => {
    const user = userEvent.setup();
    renderWithRouter(
      <Accordion
        items={[
          { key: 'q1', title: '第一问', content: '答一', defaultOpen: true },
          { key: 'q2', title: '第二问', content: '答二' },
        ]}
      />
    );
    expect(screen.getByText('答一')).toBeInTheDocument();
    expect(screen.queryByText('答二')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '第二问' }));
    expect(screen.getByText('答二')).toBeInTheDocument();
  });
});
