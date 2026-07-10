import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Breadcrumb } from './Breadcrumb';

describe('Breadcrumb (page header)', () => {
  it('renders only the LAST item as H1 with aria-current=page', () => {
    renderWithRouter(
      <Breadcrumb
        items={[
          { label: '诊断', to: '/new' },
          { label: '历史报告', to: '/history' },
          { label: '2026-07-10 小米' },
        ]}
      />
    );
    const heading = screen.getByRole('heading', { level: 1, name: '2026-07-10 小米' });
    expect(heading).toHaveAttribute('aria-current', 'page');
  });

  it('does NOT render trail items (parent labels are not visible)', () => {
    renderWithRouter(
      <Breadcrumb
        items={[
          { label: '诊断', to: '/new' },
          { label: '新建诊断' },
        ]}
      />
    );
    // '诊断' (parent) should not appear as a visible element
    expect(screen.queryByText('诊断')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('新建诊断');
  });

  it('shows description when provided', () => {
    renderWithRouter(
      <Breadcrumb items={[{ label: '设置', description: '后端连通性与版本信息。' }]} />
    );
    expect(screen.getByText('后端连通性与版本信息。')).toBeInTheDocument();
  });
});
