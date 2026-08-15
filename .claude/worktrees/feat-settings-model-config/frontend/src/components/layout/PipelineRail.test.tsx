import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { PipelineRail, type PipelineNode } from './PipelineRail';

const NODES: PipelineNode[] = [
  {
    key: 'diagnose',
    label: '诊断',
    to: '/',
    matchPrefixes: ['/', '/new', '/diagnosis', '/reports', '/agent/diagnose'],
    status: 'running',
  },
  { key: 'generate', label: '生成', to: '/tasks', matchPrefixes: ['/tasks'], status: 'done' },
  { key: 'review', label: '审核', to: '/reviews', matchPrefixes: ['/reviews'], status: 'pending' },
  {
    key: 'publish',
    label: '发布',
    to: '/publishes',
    matchPrefixes: ['/publishes', '/publishers'],
    status: 'error',
    count: 3,
  },
  {
    key: 'monitor',
    label: '监测',
    to: '/monitors',
    matchPrefixes: ['/monitors'],
    status: 'pending',
  },
  {
    key: 'track',
    label: '跟踪',
    to: '/monitors',
    matchPrefixes: ['/agent', '/notifications'],
    status: 'pending',
  },
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
    expect(screen.getByLabelText(/^诊断 进行中/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^发布 失败 失败 3 项/)).toBeInTheDocument();
  });

  it('marks nodes with error status using danger color', () => {
    renderWithRouter(<PipelineRail nodes={NODES} />);
    const errorLink = screen.getByRole('link', { name: /发布/ });
    expect(errorLink).toHaveClass('border-danger');
  });

  describe('active highlighting', () => {
    function getActiveLinks() {
      return screen.getAllByRole('link', { hidden: false }).filter((a) =>
        a.hasAttribute('aria-current')
      );
    }

    it('highlights diagnose at /', () => {
      renderWithRouter(<PipelineRail nodes={NODES} />, { initialEntries: ['/'] });
      const link = screen.getByRole('link', { name: /诊断/ });
      expect(link).toHaveAttribute('aria-current', 'page');
      expect(link.className).toMatch(/ring-primary/);
    });

    it('highlights generate at /tasks', () => {
      renderWithRouter(<PipelineRail nodes={NODES} />, { initialEntries: ['/tasks'] });
      expect(screen.getByRole('link', { name: /生成/ })).toHaveAttribute(
        'aria-current',
        'page'
      );
    });

    it('highlights generate at nested /tasks/new', () => {
      renderWithRouter(<PipelineRail nodes={NODES} />, { initialEntries: ['/tasks/new'] });
      expect(screen.getByRole('link', { name: /生成/ })).toHaveAttribute(
        'aria-current',
        'page'
      );
    });

    it('highlights publish at /publishers via matchPrefixes', () => {
      renderWithRouter(<PipelineRail nodes={NODES} />, { initialEntries: ['/publishers'] });
      expect(screen.getByRole('link', { name: /发布/ })).toHaveAttribute(
        'aria-current',
        'page'
      );
    });

    it('only one node highlighted at a time at /tasks', () => {
      renderWithRouter(<PipelineRail nodes={NODES} />, { initialEntries: ['/tasks'] });
      const actives = getActiveLinks();
      expect(actives).toHaveLength(1);
      expect(actives[0]).toHaveTextContent('生成');
    });

    it('no node highlighted at unrelated path', () => {
      renderWithRouter(<PipelineRail nodes={NODES} />, { initialEntries: ['/unknown/path'] });
      expect(getActiveLinks()).toHaveLength(0);
    });
  });
});
