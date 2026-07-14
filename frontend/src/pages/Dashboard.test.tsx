import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import Dashboard from './Dashboard';

/**
 * v0.7 Dashboard is now the 诊断 home page — a static 7-card
 * SectionCardGrid + SmartQuickChat. The previous hero CTAs / pipeline
 * overview / KPI strip were removed in favor of a single screen of
 * shortcut tiles; their behaviour now lives on the destination routes.
 */
describe('Dashboard (v0.7 diagnostic home)', () => {
  it('renders the 诊断 header', () => {
    renderWithRouter(<Dashboard />);
    expect(screen.getByRole('heading', { name: '诊断' })).toBeInTheDocument();
  });

  it('renders the 新建诊断 service card', () => {
    renderWithRouter(<Dashboard />);
    const link = screen.getByRole('link', { name: '新建诊断' });
    expect(link).toHaveAttribute('href', '/diagnose/new');
  });

  it('renders the 本月成本 card', () => {
    renderWithRouter(<Dashboard />);
    expect(screen.getByRole('link', { name: '本月成本' })).toHaveAttribute('href', '/cost');
  });

  it('renders SmartQuickChat (textarea + 立即对话 button)', () => {
    renderWithRouter(<Dashboard />);
    expect(screen.getByPlaceholderText(/说一句话/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /立即对话/ })).toBeInTheDocument();
  });
});
