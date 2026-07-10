import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Badge, type BadgeTone } from '@/components/ui/Badge';

export type StageStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped';

export interface StageCardProps {
  /** Title shown in the card header. */
  title: string;
  /** Status drives icon + colors. */
  status: StageStatus;
  /** Optional subline (e.g. "12 个页面 · 8.2s · 无错误"). */
  meta?: string;
  /** 0..100 — shows a progress bar when present and < 100. */
  progress?: number;
  /** Optional icon element shown before the title. */
  icon?: ReactNode;
  /** Optional detail area, can be collapsed/expanded in the future. */
  detail?: ReactNode;
  className?: string;
}

const toneByStatus: Record<StageStatus, BadgeTone> = {
  pending: 'neutral',
  running: 'info',
  done: 'success',
  error: 'danger',
  skipped: 'neutral',
};

const statusLabel: Record<StageStatus, string> = {
  pending: '等待中',
  running: '进行中',
  done: '已完成',
  error: '失败',
  skipped: '已跳过',
};

/**
 * StageCard — single step in a multi-stage flow (diagnosis pipeline, generation pipeline, etc).
 * Shows icon + title + status badge + optional progress + optional meta + optional detail.
 */
export function StageCard({
  title,
  status,
  meta,
  progress,
  icon,
  detail,
  className,
}: StageCardProps) {
  const hasProgress = typeof progress === 'number' && progress < 100;
  return (
    <div
      role="article"
      aria-label={`${title} ${statusLabel[status]}`}
      data-stage-status={status}
      className={cn(
        'rounded-lg border bg-bg p-4 shadow-card',
        status === 'running' && 'border-info/40 ring-2 ring-info/15',
        status === 'done' && 'border-border',
        status === 'error' && 'border-danger/40',
        status === 'pending' && 'border-border opacity-80',
        className
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {icon && (
            <span
              aria-hidden="true"
              className={cn(
                'flex h-9 w-9 items-center justify-center rounded-md',
                status === 'done' && 'bg-success/10 text-success',
                status === 'running' && 'bg-info/10 text-info',
                status === 'error' && 'bg-danger/10 text-danger',
                status === 'pending' && 'bg-bg-subtle text-fg-dim',
                status === 'skipped' && 'bg-bg-subtle text-fg-dim'
              )}
            >
              {icon}
            </span>
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-medium text-fg">{title}</h3>
              <Badge tone={toneByStatus[status]} dot>
                {statusLabel[status]}
              </Badge>
            </div>
            {meta && <p className="mt-1 text-xs text-fg-muted">{meta}</p>}
          </div>
        </div>
        {typeof progress === 'number' && progress === 100 && status === 'done' && (
          <span aria-hidden="true" className="text-success">✓</span>
        )}
      </div>
      {hasProgress && (
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
          aria-label={`${title}进度`}
          className="mt-3 h-1.5 w-full overflow-hidden rounded-pill bg-bg-subtle"
        >
          <div
            className="h-full bg-primary transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
      {detail && <div className="mt-3 text-sm text-fg-muted">{detail}</div>}
    </div>
  );
}
