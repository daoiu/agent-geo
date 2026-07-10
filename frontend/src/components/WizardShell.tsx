import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface WizardShellProps {
  currentStep: number;
  totalSteps: number;
  stepTitles: string[];
  children: ReactNode;
}

export function WizardShell({ currentStep, totalSteps, stepTitles, children }: WizardShellProps) {
  return (
    <div className="bg-muted py-8">
      <div className="max-w-2xl mx-auto px-4">
        {/* Page title now comes from the breadcrumb via LayoutShell. */}

        {/* Step indicator */}
        <div className="flex items-center mb-8">
          {stepTitles.map((title, idx) => (
            <div key={title} className="flex items-center flex-1 last:flex-none">
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium',
                  idx < currentStep && 'bg-[hsl(var(--brand-success))] text-white',
                  idx === currentStep && 'bg-primary text-primary-foreground',
                  idx > currentStep && 'bg-muted text-muted-foreground',
                )}
              >
                {idx < currentStep ? '✓' : idx + 1}
              </div>
              <div className={cn('ml-2 text-sm', idx === currentStep ? 'font-medium text-foreground' : 'text-muted-foreground')}>
                {title}
              </div>
              {idx < totalSteps - 1 && (
                <div className={cn('flex-1 h-px mx-3', idx < currentStep ? 'bg-[hsl(var(--brand-success))]' : 'bg-border')} />
              )}
            </div>
          ))}
        </div>

        <div className="bg-card border border-border rounded-lg shadow-card p-6">{children}</div>
      </div>
    </div>
  );
}
