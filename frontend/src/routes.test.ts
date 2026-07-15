import { describe, it, expect } from 'vitest';
import { ROUTES, ROUTE_REDIRECTS, breadcrumbFor } from './routes';

/**
 * v0.7 routes — single source of truth. Two contracts guarded here:
 *
 *   1. `ROUTES` — the canonical new v0.7 URL table.  Routes are addressed
 *      everywhere in the app by these string constants so a rename can
 *      happen in one place.
 *   2. `ROUTE_REDIRECTS` — the 19 legacy URL → new URL mapping table
 *      (spec §5.3).  Each `<Route path={from} element={<Navigate replace />} />`
 *      in App.tsx references one row from this map so legacy URLs land on
 *      the new IA without 404.
 */

describe('ROUTES (v0.7 IA)', () => {
  it('exposes the 6 drawer categories + agent + key sub-routes', () => {
    expect(ROUTES.diagnose).toBe('/diagnose');
    expect(ROUTES.knowledge).toBe('/knowledge/bases');
    expect(ROUTES.generate).toBe('/generate/tasks');
    expect(ROUTES.publish).toBe('/publish/jobs');
    expect(ROUTES.monitor).toBe('/monitor/tasks');
    expect(ROUTES.settings).toBe('/settings/general');
    expect(ROUTES.agent).toBe('/agent');
    expect(ROUTES.cost).toBe('/cost');
  });

  it('exposes the new diagnose run / report sub-routes', () => {
    expect(ROUTES.diagnoseNew).toBe('/diagnose/new');
    expect(ROUTES.diagnoseRun).toBe('/diagnose/runs/:taskId');
    expect(ROUTES.diagnoseReports).toBe('/diagnose/reports');
    expect(ROUTES.diagnoseReport).toBe('/diagnose/reports/:reportId');
  });
});

describe('ROUTE_REDIRECTS (legacy → v0.7)', () => {
  it('exports exactly 19 redirects', () => {
    expect(Object.keys(ROUTE_REDIRECTS)).toHaveLength(19);
  });

  it.each([
    ['/', '/diagnose'],
    ['/new', '/diagnose/new'],
    ['/diagnosis/:taskId/status', '/diagnose/runs/:taskId'],
    ['/reports', '/diagnose/reports'],
    ['/reports/:reportId', '/diagnose/reports/:reportId'],
    ['/knowledge', '/knowledge/bases'],
    ['/knowledge/:kbId', '/knowledge/bases/:kbId'],
    ['/tasks', '/generate/tasks'],
    ['/tasks/new', '/generate/tasks/new'],
    ['/tasks/:taskId', '/generate/tasks/:taskId'],
    ['/reviews', '/generate/reviews'],
    ['/reviews/:articleId', '/generate/reviews/:articleId'],
    ['/publishers', '/publish/configs'],
    ['/publishes', '/publish/jobs'],
    ['/monitors', '/monitor/tasks'],
    ['/monitors/new', '/monitor/tasks/new'],
    ['/monitors/:monitorId', '/monitor/tasks/:monitorId'],
    ['/notifications', '/settings/notifications'],
    ['/settings', '/settings/general'],
  ])('maps %s → %s', (from, to) => {
    expect(ROUTE_REDIRECTS[from]).toBe(to);
  });
});

describe('breadcrumbFor (route-driven page title)', () => {
  it('returns a Chinese label for a v0.7 category route', () => {
    const trail = breadcrumbFor('/diagnose/new');
    // /diagnose/new resolves to diagnoseNew → parent diagnose.
    expect(trail.map((c) => c.label)).toEqual(['诊断', '新建诊断']);
    expect(trail[trail.length - 1]?.description).toMatch(/60-90 秒/);
  });

  it('resolves a sub-page with :param placeholder to its canonical route', () => {
    const trail = breadcrumbFor('/diagnose/reports/abc123');
    expect(trail.map((c) => c.label)).toEqual(['诊断', '历史报告', '诊断报告']);
  });

  it('walks parents up to a category root without including extras', () => {
    const trail = breadcrumbFor('/agent/sess-42');
    expect(trail.map((c) => c.label)).toEqual(['智能助手', '会话']);
  });

  it('walks a settings sub-route up to /settings', () => {
    const trail = breadcrumbFor('/settings/dev-tools');
    expect(trail.map((c) => c.label)).toEqual(['设置', '通用设置', 'DevTools(dev)']);
  });

  it('returns a Chinese top-level crumb for /cost', () => {
    const trail = breadcrumbFor('/cost');
    expect(trail.map((c) => c.label)).toEqual(['月度成本']);
  });

  it('falls back gracefully when no route matches', () => {
    const trail = breadcrumbFor('/some/wild/path');
    expect(trail).toEqual([{ label: '/some/wild/path' }]);
  });
});
