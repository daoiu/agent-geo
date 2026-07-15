import { useState, lazy, Suspense } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * v0.7 DevTools page (spec §13 + Global Constraint red-line 5).
 *
 * Renders the DevToolsPanel only under `import.meta.env.DEV` — the
 * production bundle completely tree-shakes this branch. A non-DEV
 * build replaces the panel with a 404 tile so the route exists but
 * the body is empty.
 *
 * The panel itself is loaded via `lazy()` so the e2e / unit-test
 * paths don't pull `recharts` and friends just to mount the panel.
 */

const DevToolsPanel = lazy(() =>
  import('@/components/dev/DevToolsPanel').then((m) => ({ default: m.DevToolsPanel })),
);

export default function DevTools() {
  const isDev = import.meta.env.DEV;
  // useLocation keeps this page wired to React Router's data layer
  // without us subscribing to the pathname; future v0.7.1 can plumb
  // fault-config toggles into the URL if needed.
  useLocation();
  const [ready] = useState(true);

  if (!isDev) {
    return (
      <section className="rounded-lg border border-dashed border-border bg-bg p-12 text-center">
        <h1 className="mb-2 text-lg font-semibold">DevTools</h1>
        <p className="text-sm text-fg-muted">
          故障注入面板仅在 <code>npm run dev</code> 模式下可见。
        </p>
      </section>
    );
  }

  return (
    <div className="p-6">
      <h1 className="mb-4 text-2xl font-semibold text-fg">故障注入</h1>
      {ready && (
        <Suspense fallback={<p className="text-sm text-fg-muted">加载中…</p>}>
          <DevToolsPanel />
        </Suspense>
      )}
    </div>
  );
}
