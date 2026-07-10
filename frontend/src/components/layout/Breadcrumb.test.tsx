import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Breadcrumb } from './Breadcrumb';

describe('Breadcrumb', () => {
  it('renders last item as H1 with aria-current=page', () => {
    renderWithRouter(
      <Breadcrumb
        items={[
          { label: '诊断', to: '/new' },
          { label: '历史报告', to: '/history' },
          { label: '2026-07-10 小米' },
        ]}
      />
    );
    const nav = screen.getByRole('navigation', { name: '面包屑' });
    expect(nav).toBeInTheDocument();
    const heading = screen.getByRole('heading', { level: 1, name: '2026-07-10 小米' });
    expect(heading).toHaveAttribute('aria-current', 'page');
  });

  it('renders earlier items as links', () => {
    renderWithRouter(
      <Breadcrumb items={[{ label: '家', to: '/' }, { label: '现在' }]} />
    );
    expect(screen.getByRole('link', { name: '家' })).toBeInTheDocument();
  });

  it('shows description when provided', () => {
    renderWithRouter(
      <Breadcrumb items={[{ label: '诊断', to: '/new' }, { label: '新建诊断', description: '输入品牌信息，60-90 秒获取诊断报告' }]} />
    );
    expect(screen.getByText('输入品牌信息，60-90 秒获取诊断报告')).toBeInTheDocument();
  });
});
