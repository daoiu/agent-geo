import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './Tabs';

describe('Tabs', () => {
  it('shows default tab content and switches on click', async () => {
    const user = userEvent.setup();
    renderWithRouter(
      <Tabs defaultValue="a">
        <TabsList>
          <TabsTrigger value="a">标签A</TabsTrigger>
          <TabsTrigger value="b">标签B</TabsTrigger>
        </TabsList>
        <TabsContent value="a">内容A</TabsContent>
        <TabsContent value="b">内容B</TabsContent>
      </Tabs>
    );
    expect(screen.getByText('内容A')).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: '标签B' }));
    expect(screen.getByText('内容B')).toBeInTheDocument();
    expect(screen.queryByText('内容A')).not.toBeInTheDocument();
  });
});
