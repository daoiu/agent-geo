import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Breadcrumb } from './Breadcrumb';

describe('Breadcrumb', () => {
  it('renders last item as current page (not a link)', () => {
    renderWithRouter(
      <Breadcrumb
        items={[
          { label: '诊断', to: '/new' },
          { label: '历史报告', to: '/history' },
          { label: '2026-07-10 小米' },
        ]}
      />
    );
    expect(screen.getByRole('navigation', { name: '面包屑' })).toBeInTheDocument();
    expect(screen.getByText('2026-07-10 小米')).toHaveAttribute('aria-current', 'page');
  });

  it('renders earlier items as links', () => {
    renderWithRouter(
      <Breadcrumb items={[{ label: '家', to: '/' }, { label: '现在' }]} />
    );
    expect(screen.getByRole('link', { name: '家' })).toBeInTheDocument();
  });
});
