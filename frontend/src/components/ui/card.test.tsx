import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from './card.tsx';

describe('Card (shadcn)', () => {
  it('renders slot composition', () => {
    renderWithRouter(
      <Card>
        <CardHeader>
          <CardTitle>标题</CardTitle>
          <CardDescription>副标题</CardDescription>
        </CardHeader>
        <CardContent>正文</CardContent>
        <CardFooter>页脚</CardFooter>
      </Card>
    );
    expect(screen.getByText('标题')).toBeInTheDocument();
    expect(screen.getByText('副标题')).toBeInTheDocument();
    expect(screen.getByText('正文')).toBeInTheDocument();
    expect(screen.getByText('页脚')).toBeInTheDocument();
  });

  it('Card has card background class', () => {
    const { container } = renderWithRouter(<Card>x</Card>);
    expect(container.firstChild).toHaveClass('bg-card');
  });
});
