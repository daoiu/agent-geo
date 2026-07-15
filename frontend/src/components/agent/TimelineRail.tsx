import { cn } from '@/lib/utils';
import type { HandoffLog } from '@/types/v0.7';

/**
 * v0.7 TimelineRail — slide-in right panel mounted beside
 * AgentWorkspace's main pane. Renders the multi-agent handoff history
 * as a vertical chain: each node is a specialist with a 1.5px dashed
 * connector to the next. The current specialist is highlighted with a
 * primary ring and pulse.
 *
 * `onSelectHandoff` lets a future chat-scroll integration (Task 17) jump
 * to the message that triggered a given handoff — kept decoupled so the
 * component itself stays pure.
 */

export interface TimelineRailProps {
  sessionId: string;
  handoffs: HandoffLog[];
  currentAgent: string;
  className?: string;
  onSelectHandoff?: (handoffId: string) => void;
}

export function TimelineRail({
  handoffs,
  currentAgent,
  className,
  onSelectHandoff,
}: TimelineRailProps) {
  if (handoffs.length === 0) {
    return (
      <aside
        aria-label="Multi-Agent 时间线"
        className={cn(
          'flex h-full w-72 flex-col items-center justify-center border-l border-glass-border bg-[var(--glass-bg)] p-6 text-center text-sm text-fg-muted backdrop-blur-[20px]',
          className,
        )}
      >
        <p>还没有 specialist 切换,Agent 在 main 中。</p>
      </aside>
    );
  }
  // First handoff's from_agent is implied "main"; show as the first node.
  const seed: string = handoffs[0]?.fromAgent ?? 'main';
  const steps: { agent: string; log?: HandoffLog }[] = [{ agent: seed }];
  for (const h of handoffs) steps.push({ agent: h.toAgent, log: h });

  return (
    <aside
      aria-label="Multi-Agent 时间线"
      data-testid="timeline-rail"
      className={cn(
        'flex h-full w-72 flex-col gap-1 overflow-y-auto border-l border-glass-border bg-[var(--glass-bg)] p-4 backdrop-blur-[20px]',
        className,
      )}
    >
      <header className="mb-2">
        <h2 className="text-sm font-semibold text-fg">Multi-Agent 时间线</h2>
        <p className="text-xs text-fg-muted">
          当前: <span className="text-primary">{currentAgent}</span>
        </p>
      </header>
      <ol className="relative space-y-1">
        {steps.map((step, i) => (
          <li key={`${step.agent}-${i}`} className="flex flex-col items-stretch">
            {i > 0 && (
              <div
                aria-hidden="true"
                className="mx-5 my-0.5 h-4 border-l-[1.5px] border-dashed border-primary/40"
              />
            )}
            <button
              type="button"
              onClick={() => step.log && onSelectHandoff?.(step.log.id)}
              disabled={!step.log}
              aria-current={
                step.agent === currentAgent ? 'true' : undefined
              }
              className={cn(
                'flex items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors duration-400 ease-spring-gentle',
                step.agent === currentAgent
                  ? 'bg-primary-tint ring-2 ring-primary/40 animate-pulse text-primary'
                  : 'hover:bg-primary-tint/40 text-fg-muted',
                step.log ? '' : 'cursor-default',
              )}
            >
              <span
                aria-hidden="true"
                className="flex h-6 w-6 items-center justify-center rounded-full border border-border bg-card text-[10px] font-bold"
              >
                {i + 1}
              </span>
              <span className="min-w-0 truncate font-medium">{step.agent}</span>
              {step.log?.taskSummary && (
                <span className="ml-auto truncate text-[10px] text-fg-muted">
                  {step.log.taskSummary}
                </span>
              )}
            </button>
          </li>
        ))}
      </ol>
    </aside>
  );
}
