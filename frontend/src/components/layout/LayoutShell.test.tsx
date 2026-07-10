import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { LayoutShell } from './LayoutShell';
import type { NavItem } from './SideNav';
import type { Crumb } from './Breadcrumb';
import type { PipelineNode } from './PipelineRail';

const NAV: NavItem[] = [{ key: 'home', label: '仪表盘', to: '/' }];
const CRUMBS: Crumb[] = [{ label: '仪表盘' }];
const NODES: PipelineNode[] = [
  { key: 'diagnose', label: '诊断', to: '/', matchPrefixes: ['/'], status: 'done' },
];

describe('LayoutShell', () => {
  it('renders TopBar brand + SideNav items + PipelineRail nodes + main content', () => {
    renderWithRouter(
      <LayoutShell navItems={NAV} crumbs={CRUMBS} pipelineNodes={NODES}>
        <div>主内容</div>
      </LayoutShell>
    );
    expect(screen.getByText('GEO 优化系统')).toBeInTheDocument();
    expect(screen.getAllByText('仪表盘').length).toBeGreaterThan(0);
    expect(screen.getByText('主内容')).toBeInTheDocument();
    // PipelineRail '诊断' rendered
    expect(screen.getAllByText('诊断').length).toBeGreaterThan(0);
  });
});
