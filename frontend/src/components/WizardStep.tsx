import type { ReactNode } from 'react';

interface WizardStepProps {
  title: string;
  description?: string;
  children: ReactNode;
  onBack?: () => void;
  onNext?: () => void;
  nextDisabled?: boolean;
  nextLabel?: string;
  isLastStep?: boolean;
}

export function WizardStep({
  title,
  description,
  children,
  onBack,
  onNext,
  nextDisabled,
  nextLabel = '下一步',
  isLastStep,
}: WizardStepProps) {
  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-2">{title}</h2>
      {description && <p className="text-gray-600 mb-6">{description}</p>}
      <div className="mb-6">{children}</div>
      <div className="flex justify-between">
        <button
          type="button"
          onClick={onBack}
          disabled={!onBack}
          className="px-4 py-2 text-gray-600 hover:text-gray-900 disabled:opacity-30"
        >
          ← 上一步
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={nextDisabled}
          className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {isLastStep ? '提交诊断' : `${nextLabel} →`}
        </button>
      </div>
    </div>
  );
}
