import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen, within } from '@testing-library/react';
import { SideNav, type NavItem } from './SideNav';

const ITEMS: NavItem[] = [
  { key: 'home', label: '仪表盘', to: '/' },
  {
    key: 'diag',
    label: '诊断',
    to: '/new',
    children: [
      { key: 'diag-new', label: '新建诊断', to: '/new' },
      { key: 'diag-history', label: '历史报告', to: '/' },
    ],
  },
  { key: 'kb', label: '知识库', to: '/knowledge' },
];

describe('SideNav', () => {
  it('renders top-level items', () => {
    renderWithRouter(<SideNav items={ITEMS} />, { initialEntries: ['/'] });
    const nav = screen.getByRole('navigation', { name: '主导航' });
    expect(within(nav).getByText('仪表盘')).toBeInTheDocument();
    expect(within(nav).getByText('诊断')).toBeInTheDocument();
    expect(within(nav).getByText('知识库')).toBeInTheDocument();
  });

  it('renders child items indented', () => {
    renderWithRouter(<SideNav items={ITEMS} />);
    expect(screen.getByText('新建诊断')).toBeInTheDocument();
    expect(screen.getByText('历史报告')).toBeInTheDocument();
  });

  it('marks active item with primary color', () => {
    renderWithRouter(<SideNav items={ITEMS} />, { initialEntries: ['/knowledge'] });
    const link = screen.getByRole('link', { name: '知识库' });
    expect(link).toHaveClass('text-primary');
  });
});
