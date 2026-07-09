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
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">GEO 诊断</h1>
        <p className="text-gray-600 mb-6">输入品牌信息，60-90 秒获取诊断报告</p>

        {/* Step indicator */}
        <div className="flex items-center mb-8">
          {stepTitles.map((title, idx) => (
            <div key={title} className="flex items-center flex-1 last:flex-none">
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium',
                  idx < currentStep && 'bg-green-500 text-white',
                  idx === currentStep && 'bg-blue-600 text-white',
                  idx > currentStep && 'bg-gray-200 text-gray-500',
                )}
              >
                {idx < currentStep ? '✓' : idx + 1}
              </div>
              <div className={cn('ml-2 text-sm', idx === currentStep ? 'font-medium' : 'text-gray-500')}>
                {title}
              </div>
              {idx < totalSteps - 1 && (
                <div className={cn('flex-1 h-px mx-3', idx < currentStep ? 'bg-green-500' : 'bg-gray-200')} />
              )}
            </div>
          ))}
        </div>

        <div className="bg-white rounded-lg shadow p-6">{children}</div>
      </div>
    </div>
  );
}
