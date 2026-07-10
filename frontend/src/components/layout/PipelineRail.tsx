import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';

export type PipelineNodeKey = 'diagnose' | 'generate' | 'review' | 'publish' | 'monitor' | 'track';

export type PipelineNodeStatus = 'pending' | 'running' | 'done' | 'error';

export interface PipelineNode {
  key: PipelineNodeKey;
  label: string;
  /** Primary target URL — used as `<Link to>`. */
  to: string;
  /**
   * URL prefixes that should treat this node as the active one.
   * Use root '/', '/tasks', '/monitors' etc. Sub-paths (e.g. /tasks/abc) match
   * when their parent prefix is in this list.
   */
  matchPrefixes: string[];
  status: PipelineNodeStatus;
  count?: number;
}

export interface PipelineRailProps {
  nodes: PipelineNode[];
  collapsed?: boolean;
  onToggle?: () => void;
}

const NODE_TONE: Record<PipelineNodeStatus, string> = {
  pending: 'border-fg-dim/40 bg-bg text-fg-dim',
  running: 'border-primary bg-primary text-primary-fg animate-pulse',
  done: 'border-success bg-success/15 text-success',
  error: 'border-danger bg-danger/15 text-danger',
};

const STATUS_LABEL: Record<PipelineNodeStatus, string> = {
  pending: '等待中',
  running: '进行中',
  done: '已完成',
  error: '失败',
};

const STATUS_COUNT_LABEL: Record<PipelineNodeStatus, string> = {
  pending: '待处理',
  running: '进行',
  done: '已完成',
  error: '失败',
};

const ACTIVE_RING = 'ring-2 ring-primary ring-offset-2 ring-offset-bg-stage';

function isNodeActive(node: PipelineNode, pathname: string): boolean {
  if (pathname === node.to) return true;
  return node.matchPrefixes.some((p) => pathname === p || pathname.startsWith(p + '/'));
}

/**
 * PipelineRail — global bottom bar showing the 6 optimization pipeline nodes.
 * Reflects the most recent activity per stage. Click any node to drill into
 * that stage's dashboard. The node whose URL prefix matches the current path
 * is visually highlighted (and exposes `aria-current="page"`).
 */
export function PipelineRail({ nodes, collapsed, onToggle }: PipelineRailProps) {
  const location = useLocation();
  return (
    <footer
      role="navigation"
      aria-label="全局优化流水线"
      className={cn(
        'flex items-center gap-4 border-t border-border bg-bg-stage transition-all',
        collapsed ? 'h-7 px-3' : 'h-15 px-4'
      )}
    >
      {onToggle && (
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? '展开流水线' : '折叠流水线'}
          className="rounded-md p-1 text-fg-muted hover:bg-bg hover:text-fg"
        >
          {collapsed ? '▲' : '▼'}
        </button>
      )}
      <ol className="flex flex-1 items-center gap-3 overflow-x-auto">
        {nodes.map((n, i) => {
          const active = isNodeActive(n, location.pathname);
          return (
            <li key={n.key} className="flex items-center gap-3">
              <Link
                to={n.to}
                aria-current={active ? 'page' : undefined}
                aria-label={`${n.label} ${STATUS_LABEL[n.status]}${n.count != null ? ` ${STATUS_COUNT_LABEL[n.status]} ${n.count} 项` : ''}${active ? ' · 当前阶段' : ''}`}
                className={cn(
                  'inline-flex items-center gap-2 rounded-pill border px-3 py-1 text-xs font-medium transition-shadow',
                  NODE_TONE[n.status],
                  active && ACTIVE_RING
                )}
              >
                <span>{n.label}</span>
                {n.count != null && (
                  <span className="rounded-pill bg-white/20 px-1.5 text-[10px] tabular-nums">
                    {n.count}
                  </span>
                )}
              </Link>
              {i < nodes.length - 1 && (
                <span aria-hidden="true" className="text-fg-dim">
                  ─
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </footer>
  );
}
