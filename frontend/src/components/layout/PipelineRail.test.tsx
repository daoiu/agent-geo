import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { PipelineRail, type PipelineNode } from './PipelineRail';

const NODES: PipelineNode[] = [
  { key: 'diagnose', label: '诊断', to: '/', status: 'running' },
  { key: 'generate', label: '生成', to: '/tasks', status: 'done' },
  { key: 'review', label: '审核', to: '/reviews', status: 'pending' },
  { key: 'publish', label: '发布', to: '/publishes', status: 'error', count: 3 },
  { key: 'monitor', label: '监测', to: '/monitors', status: 'pending' },
  { key: 'track', label: '跟踪', to: '/monitors', status: 'pending' },
];

describe('PipelineRail', () => {
  it('renders all six nodes', () => {
    renderWithRouter(<PipelineRail nodes={NODES} />);
    expect(screen.getByText('诊断')).toBeInTheDocument();
    expect(screen.getByText('生成')).toBeInTheDocument();
    expect(screen.getByText('审核')).toBeInTheDocument();
    expect(screen.getByText('发布')).toBeInTheDocument();
    expect(screen.getByText('监测')).toBeInTheDocument();
    expect(screen.getByText('跟踪')).toBeInTheDocument();
  });

  it('exposes a11y label with status', () => {
    renderWithRouter(<PipelineRail nodes={NODES} />);
    expect(
      screen.getByLabelText('诊断 进行中')
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText('发布 失败 失败 3 项')
    ).toBeInTheDocument();
  });

  it('marks nodes with error status using danger color', () => {
    const { container } = renderWithRouter(<PipelineRail nodes={NODES} />);
    const errorLink = screen.getByRole('link', { name: /发布/ });
    expect(errorLink).toHaveClass('border-danger');
  });
});
