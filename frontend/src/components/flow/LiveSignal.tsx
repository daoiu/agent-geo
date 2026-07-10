import { cn } from '@/lib/utils';

export type SignalStatus = 'pending' | 'running' | 'done' | 'error';

export interface LiveSignalProps {
  /** Provider / source label (e.g. "DeepSeek", "Kimi"). */
  provider: string;
  status: SignalStatus;
  /** Optional progress 0..100 — used for `running`. */
  progress?: number;
  /** Optional duration string — used for `done`. */
  durationMs?: number;
  className?: string;
}

const statusRing: Record<SignalStatus, string> = {
  pending: 'border-fg-dim/40 bg-bg',
  running: 'border-info bg-info/10 text-info',
  done: 'border-success bg-success/10 text-success',
  error: 'border-danger bg-danger/10 text-danger',
};

const dotPulse: Record<SignalStatus, string> = {
  pending: 'bg-fg-dim',
  running: 'bg-info animate-pulse',
  done: 'bg-success',
  error: 'bg-danger',
};

const statusLabel: Record<SignalStatus, string> = {
  pending: '等待',
  running: '运行中',
  done: '完成',
  error: '失败',
};

/**
 * LiveSignal — small badge that shows a provider's progress state with a dot.
 * Used in DiagnosisStatus, PipelineRail, and per-provider breakdowns.
 */
export function LiveSignal({ provider, status, progress, durationMs, className }: LiveSignalProps) {
  return (
    <div
      role="status"
      aria-label={`${provider} ${statusLabel[status]}${typeof progress === 'number' ? ` ${progress}%` : ''}${durationMs ? ` 用时 ${Math.round(durationMs)}ms` : ''}`}
      className={cn(
        'inline-flex items-center gap-2 rounded-pill border px-2.5 py-1 text-xs',
        statusRing[status],
        className
      )}
    >
      <span aria-hidden="true" className={cn('h-1.5 w-1.5 rounded-pill', dotPulse[status])} />
      <span className="font-medium">{provider}</span>
      {status === 'running' && typeof progress === 'number' && (
        <span className="tabular-nums">{progress}%</span>
      )}
      {status === 'done' && durationMs != null && (
        <span className="text-fg-muted tabular-nums">{Math.round(durationMs)}ms</span>
      )}
    </div>
  );
}
