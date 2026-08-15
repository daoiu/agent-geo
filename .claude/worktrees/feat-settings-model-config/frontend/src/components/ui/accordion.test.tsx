import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from './accordion';

describe('Accordion (shadcn)', () => {
  it('expands on click and reveals content', async () => {
    const user = userEvent.setup();
    renderWithRouter(
      <Accordion type="single" collapsible>
        <AccordionItem value="q1">
          <AccordionTrigger>第一问</AccordionTrigger>
          <AccordionContent>答一</AccordionContent>
        </AccordionItem>
        <AccordionItem value="q2">
          <AccordionTrigger>第二问</AccordionTrigger>
          <AccordionContent>答二</AccordionContent>
        </AccordionItem>
      </Accordion>
    );
    expect(screen.queryByText('答一')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '第一问' }));
    expect(screen.getByText('答一')).toBeInTheDocument();
  });
});
