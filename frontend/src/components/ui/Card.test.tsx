import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Card, CardHeader, CardTitle, CardDescription, CardBody, CardFooter } from './Card';

describe('Card', () => {
  it('renders children inside a rounded container', () => {
    renderWithRouter(<Card>hello</Card>);
    expect(screen.getByText('hello')).toBeInTheDocument();
  });

  it('renders Header/Title/Description/Body/Footer slots', () => {
    renderWithRouter(
      <Card>
        <CardHeader>
          <CardTitle>标题</CardTitle>
          <CardDescription>副标题</CardDescription>
        </CardHeader>
        <CardBody>正文</CardBody>
        <CardFooter>页脚</CardFooter>
      </Card>
    );
    expect(screen.getByText('标题')).toBeInTheDocument();
    expect(screen.getByText('副标题')).toBeInTheDocument();
    expect(screen.getByText('正文')).toBeInTheDocument();
    expect(screen.getByText('页脚')).toBeInTheDocument();
  });
});
