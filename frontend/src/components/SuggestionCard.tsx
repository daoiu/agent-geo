import type { Suggestion } from '@/types/diagnosis';

import { cn } from '@/lib/utils';

interface Props {
  suggestion: Suggestion;
}

const PRIORITY_STYLES: Record<string, string> = {
  P0: 'border-l-red-500 bg-red-50',
  P1: 'border-l-yellow-500 bg-yellow-50',
  P2: 'border-l-green-500 bg-green-50',
};

const PRIORITY_LABEL: Record<string, string> = {
  P0: '紧急',
  P1: '重要',
  P2: '建议',
};

export function SuggestionCard({ suggestion }: Props) {
  return (
    <div className={cn('border-l-4 rounded-md p-4 mb-3', PRIORITY_STYLES[suggestion.priority])}>
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-semibold text-gray-900">{suggestion.title}</h4>
        <span className="text-xs px-2 py-1 rounded bg-white border">
          [{suggestion.priority}] {PRIORITY_LABEL[suggestion.priority]}
        </span>
      </div>
      <p className="text-sm text-gray-700 mb-3">{suggestion.detail}</p>
      {suggestion.action_steps.length > 0 && (
        <div className="text-sm">
          <strong className="text-gray-900">行动步骤：</strong>
          <ol className="list-decimal list-inside mt-1 space-y-1 text-gray-700">
            {suggestion.action_steps.map((step, idx) => (
              <li key={idx}>{step}</li>
            ))}
          </ol>
        </div>
      )}
      <p className="text-xs text-gray-500 mt-3">
        <strong>预期效果：</strong>{suggestion.expected_impact}
      </p>
    </div>
  );
}
