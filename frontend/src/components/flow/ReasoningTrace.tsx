import { useState } from 'react';
import { cn } from '@/lib/utils';

export type TraceEvent =
  | { kind: 'thought'; text: string; ts: number }
  | { kind: 'tool_call'; tool: string; args: Record<string, unknown>; status: 'running' | 'done' | 'error'; ts: number; result?: unknown }
  | { kind: 'llm_query'; provider: string; status: 'pending' | 'done' | 'error'; durationMs?: number; ts: number }
  | { kind: 'final'; text: string; ts: number; needsConfirmation?: boolean };

export interface ReasoningTraceProps {
  events: TraceEvent[];
  /** When events exceed this, collapsed view shows only the latest N. Default 50. */
  collapsibleThreshold?: number;
  className?: string;
}

function statusColor(s: 'running' | 'done' | 'error' | 'pending'): string {
  switch (s) {
    case 'running':
      return 'bg-info text-white';
    case 'done':
      return 'bg-success text-white';
    case 'error':
      return 'bg-danger text-white';
    case 'pending':
      return 'bg-fg-dim/40 text-fg-muted';
  }
}

function EventRow({ ev }: { ev: TraceEvent }) {
  const ts = new Date(ev.ts).toLocaleTimeString('zh-CN', { hour12: false });
  if (ev.kind === 'thought') {
    return (
      <div className="flex items-start gap-2 text-sm">
        <span aria-hidden="true" className="mt-0.5 text-info">💭</span>
        <div className="min-w-0">
          <p className="text-fg-muted">{ev.text}</p>
          <span className="text-[10px] text-fg-dim">{ts}</span>
        </div>
      </div>
    );
  }
  if (ev.kind === 'tool_call') {
    return (
      <div className="rounded-md border border-border bg-bg p-2 text-xs">
        <div className="flex items-center gap-2">
          <span aria-hidden="true">🔧</span>
          <code className="font-mono text-fg">{ev.tool}</code>
          <span aria-hidden="true" className={cn('rounded-pill px-1.5 py-0.5 text-[10px]', statusColor(ev.status))}>
            {ev.status}
          </span>
          <span className="ml-auto text-[10px] text-fg-dim">{ts}</span>
        </div>
        <details className="mt-1">
          <summary className="cursor-pointer text-fg-dim hover:text-fg">参数</summary>
          <pre className="mt-1 overflow-auto rounded bg-bg-subtle p-1 font-mono text-[10px]">
            {JSON.stringify(ev.args, null, 2)}
          </pre>
        </details>
        {ev.result != null && (
          <details className="mt-1">
            <summary className="cursor-pointer text-fg-dim hover:text-fg">结果</summary>
            <pre className="mt-1 overflow-auto rounded bg-bg-subtle p-1 font-mono text-[10px]">
              {JSON.stringify(ev.result, null, 2)}
            </pre>
          </details>
        )}
      </div>
    );
  }
  if (ev.kind === 'llm_query') {
    return (
      <div className="flex items-center gap-2 text-xs text-fg-muted">
        <span aria-hidden="true">🌐</span>
        <span className="font-medium text-fg">{ev.provider}</span>
        <span aria-hidden="true" className={cn('rounded-pill px-1.5 py-0.5 text-[10px]', statusColor(ev.status))}>
          {ev.status}
        </span>
        {ev.durationMs != null && (
          <span className="tabular-nums">{Math.round(ev.durationMs)}ms</span>
        )}
        <span className="ml-auto text-[10px] text-fg-dim">{ts}</span>
      </div>
    );
  }
  // final
  return (
    <div
      className={cn(
        'rounded-md border p-2 text-sm',
        ev.needsConfirmation
          ? 'border-warning/40 bg-warning/10'
          : 'border-primary/30 bg-primary/10'
      )}
      aria-label={ev.needsConfirmation ? '需要确认的最终回复' : '最终回复'}
    >
      <div className="flex items-start gap-2">
        <span aria-hidden="true">{ev.needsConfirmation ? '⚠️' : '✅'}</span>
        <p className="text-fg">{ev.text}</p>
      </div>
      <span className="mt-1 block text-[10px] text-fg-dim">{ts}</span>
    </div>
  );
}

/**
 * ReasoningTrace — visualizes an Agent's ReAct loop step-by-step.
 * Collapses very long traces to avoid UI overflow.
 */
export function ReasoningTrace({
  events,
  collapsibleThreshold = 50,
  className,
}: ReasoningTraceProps) {
  const [expanded, setExpanded] = useState(false);
  const overflow = events.length > collapsibleThreshold;
  const visible = overflow && !expanded ? events.slice(-collapsibleThreshold) : events;
  const hiddenCount = events.length - visible.length;

  return (
    <ol
      role="list"
      aria-label="Agent 推理时间线"
      className={cn('space-y-3', className)}
    >
      {overflow && (
        <li className="text-center text-xs text-fg-dim">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="rounded-md border border-border px-3 py-1 hover:bg-bg-subtle"
          >
            {expanded ? `收起 ${events.length - collapsibleThreshold} 条` : `展开 ${hiddenCount} 条历史推理`}
          </button>
        </li>
      )}
      {visible.map((ev, i) => (
        <li key={i}>
          <EventRow ev={ev} />
        </li>
      ))}
    </ol>
  );
}
