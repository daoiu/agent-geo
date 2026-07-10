import type { PipelineNode, PipelineNodeKey, PipelineNodeStatus } from '@/components/layout/PipelineRail';

/**
 * usePipelineState — aggregates the most recent activity across the 6 pipeline
 * stages.
 *
 * P0 implementation: returns a fixed all-pending view so the new LayoutShell +
 * PipelineRail render correctly with the 6 nodes. The shape (key/label/to/
 * status/count) is the contract that P1 will fill in.
 *
 * Wiring plan for P1:
 *   - 'diagnose' from GET /api/reports (latest report)
 *   - 'generate' from GET /api/tasks     (latest task)
 *   - 'review'   from GET /api/reviews   (article queue)
 *   - 'publish'  from GET /api/publishes (publish jobs)
 *   - 'monitor'  from GET /api/monitors  (monitor list)
 *   - 'track'    from GET /api/monitors/:id/trends
 *
 * Each query will run with its own error boundary; failure → 'pending'.
 */
export function usePipelineState(): { nodes: PipelineNode[]; isLoading: boolean } {
  // P0: everything pending. P1 will replace this with derived status per stage.
  const views: Record<PipelineNodeKey, { status: PipelineNodeStatus; count?: number }> = {
    diagnose: { status: 'pending' },
    generate: { status: 'pending' },
    review: { status: 'pending' },
    publish: { status: 'pending' },
    monitor: { status: 'pending' },
    track: { status: 'pending' },
  };

  const nodes: PipelineNode[] = (
    [
      ['diagnose', '诊断', '/'],
      ['generate', '生成', '/tasks'],
      ['review', '审核', '/reviews'],
      ['publish', '发布', '/publishes'],
      ['monitor', '监测', '/monitors'],
      ['track', '跟踪', '/monitors'],
    ] as [PipelineNodeKey, string, string][]
  ).map(([key, label, to]) => ({
    key,
    label,
    to,
    status: views[key].status,
    count: views[key].count,
  }));

  return { nodes, isLoading: false };
}
