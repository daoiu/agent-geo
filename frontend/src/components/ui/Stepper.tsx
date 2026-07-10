import { cn } from '@/lib/utils';

export interface Step {
  key: string;
  title: string;
  description?: string;
}

export interface StepperProps {
  steps: Step[];
  /** 0-based index of the active step. Steps before are "done", after are "pending". */
  current: number;
  orientation?: 'horizontal' | 'vertical';
  className?: string;
}

/**
 * Stepper — visual indicator for multi-step wizards / wizards.
 * Shown for both horizontal (top of wizard pages) and vertical (side-panel flows).
 */
export function Stepper({ steps, current, orientation = 'horizontal', className }: StepperProps) {
  const isH = orientation === 'horizontal';

  return (
    <ol
      role="list"
      data-orientation={orientation}
      className={cn(isH ? 'flex items-center gap-3' : 'space-y-3', className)}
    >
      {steps.map((s, i) => {
        const state = i < current ? 'done' : i === current ? 'current' : 'pending';
        return (
          <li
            key={s.key}
            data-step-state={state}
            className={cn(isH ? 'flex items-center gap-2' : 'flex items-start gap-3')}
          >
            <span
              className={cn(
                'flex h-7 w-7 shrink-0 items-center justify-center rounded-pill text-xs font-medium',
                state === 'done' && 'bg-success text-white',
                state === 'current' && 'bg-primary text-primary-fg',
                state === 'pending' && 'border border-border bg-bg text-fg-dim'
              )}
            >
              {state === 'done' ? '✓' : i + 1}
            </span>
            <span
              className={cn(
                'text-sm',
                state === 'current' ? 'font-medium text-fg' : 'text-fg-muted'
              )}
            >
              {s.title}
            </span>
            {!isH && s.description && (
              <span className="ml-1 text-xs text-fg-dim">{s.description}</span>
            )}
            {isH && i < steps.length - 1 && (
              <span aria-hidden="true" className="ml-2 h-px w-8 bg-border" />
            )}
          </li>
        );
      })}
    </ol>
  );
}
