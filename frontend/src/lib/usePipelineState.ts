import { useQueries } from '@tanstack/react-query';
import { api } from '@/api/client';
import type {
  PipelineNode,
  PipelineNodeKey,
  PipelineNodeStatus,
} from '@/components/layout/PipelineRail';

type DiagnosisStatus =
  | 'pending'
  | 'crawling'
  | 'querying_llm'
  | 'scoring'
  | 'rendering'
  | 'completed'
  | 'failed';

type ContentTaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
type PublishJobStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';

interface DiagnosisStatusView {
  status: PipelineNodeStatus;
  count?: number;
}

const PENDING: DiagnosisStatusView = { status: 'pending' };

function diagnosisStatus(s: DiagnosisStatus | undefined): PipelineNodeStatus {
  if (!s) return 'pending';
  if (s === 'completed') return 'done';
  if (s === 'failed') return 'error';
  return 'running';
}

function contentStatus(s: ContentTaskStatus | undefined): PipelineNodeStatus {
  if (!s) return 'pending';
  if (s === 'running' || s === 'pending') return 'running';
  if (s === 'completed') return 'done';
  if (s === 'failed') return 'error';
  return 'pending'; // cancelled
}

function publishStatusInline(jobs: { status: PublishJobStatus }[]): DiagnosisStatusView {
  const running = jobs.filter((j) => j.status === 'running' || j.status === 'pending').length;
  const failed = jobs.filter((j) => j.status === 'failed').length;
  if (failed > 0) return { status: 'error', count: failed };
  if (running > 0) return { status: 'running', count: running };
  return { status: 'done' };
}

/**
 * usePipelineState — aggregates the most recent activity across the 6 pipeline
 * stages into PipelineRail nodes. Uses 5 independent queries so a failing
 * stage falls back to 'pending' without taking down the bar.
 *
 * Mapping:
 *   - 'diagnose'  → latest entry in listReports()
 *   - 'generate'  → latest entry in listTasks()
 *   - 'review'    → listReviewQueue() pending count; empty list → done (queue clear)
 *   - 'publish'   → listPublishJobs(): running/failed counts
 *   - 'monitor'   → listMonitors(): active monitor count
 *   - 'track'     → getMonitorTrends(activeId): if last point shows drop → error; else running/done
 */
export function usePipelineState(): { nodes: PipelineNode[]; isLoading: boolean } {
  const results = useQueries({
    queries: [
      { queryKey: ['pipeline', 'reports'], queryFn: () => api.listReports(), staleTime: 30_000 },
      { queryKey: ['pipeline', 'tasks'], queryFn: () => api.listTasks(), staleTime: 30_000 },
      { queryKey: ['pipeline', 'reviews'], queryFn: () => api.listReviewQueue(), staleTime: 30_000 },
      { queryKey: ['pipeline', 'publishes'], queryFn: () => api.listPublishJobs(), staleTime: 30_000 },
      { queryKey: ['pipeline', 'monitors'], queryFn: () => api.listMonitors(), staleTime: 30_000 },
    ],
  });
  const [reportsQ, tasksQ, reviewsQ, publishesQ, monitorsQ] = results;

  // Stage views — each independent (failure isolation)
  const diagnoseView: DiagnosisStatusView = reportsQ.error
    ? PENDING
    : !reportsQ.data
    ? PENDING
    : reportsQ.data.length === 0
    ? { status: 'pending' }
    : { status: diagnosisStatus(reportsQ.data[0].status) };

  const generateView: DiagnosisStatusView = tasksQ.error
    ? PENDING
    : !tasksQ.data
    ? PENDING
    : tasksQ.data.length === 0
    ? { status: 'pending' }
    : { status: contentStatus(tasksQ.data[0].status) };

  const reviewView: DiagnosisStatusView = reviewsQ.error
    ? PENDING
    : !reviewsQ.data
    ? PENDING
    : reviewsQ.data.length === 0
    ? { status: 'done' } // queue empty => nothing to review
    : { status: 'running', count: reviewsQ.data.length };

  const publishView: DiagnosisStatusView = publishesQ.error
    ? PENDING
    : !publishesQ.data
    ? PENDING
    : publishStatusInline(publishesQ.data);

  const monitorView: DiagnosisStatusView = monitorsQ.error
    ? PENDING
    : !monitorsQ.data
    ? PENDING
    : (() => {
        const active = monitorsQ.data.filter((m) => m.is_active).length;
        const total = monitorsQ.data.length;
        if (total === 0) return { status: 'pending' };
        return { status: active > 0 ? 'running' : 'done', count: active };
      })();

  // Track stage — for P0 we synthesize from monitor view: if monitors are running, track is running.
  // P1+ can replace with: const [trendsQ] = useQueries({...getMonitorTrends(firstActiveId)...}).
  const trackView: DiagnosisStatusView = monitorsQ.error
    ? PENDING
    : (monitorView.status === 'running'
        ? { status: 'running' }
        : monitorView.status === 'done'
        ? { status: 'done' }
        : PENDING);

  const views: Record<PipelineNodeKey, DiagnosisStatusView> = {
    diagnose: diagnoseView,
    generate: generateView,
    review: reviewView,
    publish: publishView,
    monitor: monitorView,
    track: trackView,
  };

  const nodes: PipelineNode[] = (
    [
      {
        key: 'diagnose',
        label: '诊断',
        to: '/',
        matchPrefixes: ['/', '/new', '/diagnosis', '/reports', '/agent/diagnose'],
      },
      {
        key: 'generate',
        label: '生成',
        to: '/tasks',
        matchPrefixes: ['/tasks'],
      },
      {
        key: 'review',
        label: '审核',
        to: '/reviews',
        matchPrefixes: ['/reviews'],
      },
      {
        key: 'publish',
        label: '发布',
        to: '/publishes',
        matchPrefixes: ['/publishes', '/publishers'],
      },
      {
        key: 'monitor',
        label: '监测',
        to: '/monitors',
        matchPrefixes: ['/monitors'],
      },
      {
        key: 'track',
        label: '跟踪',
        to: '/monitors',
        matchPrefixes: ['/agent', '/notifications'],
      },
    ] as Array<{ key: PipelineNodeKey; label: string; to: string; matchPrefixes: string[] }>
  ).map((cfg) => ({
    key: cfg.key,
    label: cfg.label,
    to: cfg.to,
    matchPrefixes: cfg.matchPrefixes,
    status: views[cfg.key].status,
    count: views[cfg.key].count,
  }));

  return {
    nodes,
    isLoading: results.some((r) => r.isLoading),
  };
}
