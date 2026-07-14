import { describe, it, expect, vi } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen, fireEvent } from '@testing-library/react';
import { NavDrawer, type NavSection } from './NavDrawer';

const SECTIONS: NavSection[] = [
  {
    id: 'diagnose',
    label: '诊断',
    icon: <svg data-testid="icon-d" />,
    to: '/diagnose',
    items: [],
  },
  {
    id: 'knowledge',
    label: '知识',
    icon: <svg data-testid="icon-k" />,
    to: '/knowledge/bases',
    items: [],
  },
  {
    id: 'generate',
    label: '生成',
    icon: <svg data-testid="icon-g" />,
    to: '/generate/tasks',
    items: [
      { to: '/generate/tasks/new', label: '新建任务' },
    ],
  },
];

describe('NavDrawer (v0.7 HarmonyOS)', () => {
  it('renders top-level sections by label', () => {
    renderWithRouter(
      <NavDrawer sections={SECTIONS} activeSection="diagnose" onSelect={() => {}} />,
      { initialEntries: ['/diagnose'] }
    );
    const nav = screen.getByRole('navigation', { name: '主导航' });
    expect(nav).toBeInTheDocument();
    expect(nav.textContent).toContain('诊断');
    expect(nav.textContent).toContain('知识');
    expect(nav.textContent).toContain('生成');
  });

  it('marks active section with primary tint + 2px left bar', () => {
    renderWithRouter(
      <NavDrawer sections={SECTIONS} activeSection="diagnose" onSelect={() => {}} />,
      { initialEntries: ['/diagnose'] }
    );
    const link = screen.getByRole('link', { name: '诊断' });
    expect(link).toHaveClass('bg-primary-tint');
  });

  it('calls onSelect when a non-active section is clicked', () => {
    const onSelect = vi.fn();
    renderWithRouter(
      <NavDrawer sections={SECTIONS} activeSection="diagnose" onSelect={onSelect} />,
      { initialEntries: ['/diagnose'] }
    );
    fireEvent.click(screen.getByRole('link', { name: '知识' }));
    expect(onSelect).toHaveBeenCalledWith('knowledge');
  });
});
