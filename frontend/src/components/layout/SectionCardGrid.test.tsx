import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { SectionCardGrid } from './SectionCardGrid';

const CARDS = [
  {
    to: '/diagnose/new',
    title: '新建诊断',
    description: '跑一遍 6 阶段流水线,5 分钟出报告',
    icon: <span aria-hidden="true">🆕</span>,
    badge: '主入口',
  },
  {
    to: '/agent',
    title: '智能助手',
    description: '自然语言 + ReAct 5 工具',
    icon: <span aria-hidden="true">🤖</span>,
  },
];

describe('SectionCardGrid (v0.7)', () => {
  it('renders one card per entry with link href matching `to`', () => {
    renderWithRouter(<SectionCardGrid cards={CARDS} />);
    expect(screen.getByRole('link', { name: '新建诊断' })).toHaveAttribute('href', '/diagnose/new');
    expect(screen.getByRole('link', { name: '智能助手' })).toHaveAttribute('href', '/agent');
  });

  it('renders badge when provided', () => {
    renderWithRouter(<SectionCardGrid cards={CARDS} />);
    expect(screen.getByText('主入口')).toBeInTheDocument();
  });

  it('renders description text', () => {
    renderWithRouter(<SectionCardGrid cards={CARDS} />);
    expect(screen.getByText(/跑一遍 6 阶段流水线/)).toBeInTheDocument();
  });
});
