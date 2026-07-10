import { useState } from 'react';

export interface ToolCallDisplay {
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  result?: Record<string, unknown>;
  pending?: boolean;
}

const TOOL_LABELS: Record<string, string> = {
  diagnose_brand: '诊断品牌',
  search_knowledge: '查询知识库',
  generate_article: '生成文章',
};

export function ToolCallCard({ display }: { display: ToolCallDisplay }) {
  const [expanded, setExpanded] = useState(false);

  if (display.pending || display.result === undefined) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3 mb-3 text-sm">
        <div className="flex items-center">
          <span className="animate-spin mr-2">⏳</span>
          <span>
            正在调用 <code className="font-mono">{display.tool_name}</code>...
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 border rounded-md p-3 mb-3 text-sm">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div>
          ✓ 工具{' '}
          <code className="font-mono">
            {TOOL_LABELS[display.tool_name] || display.tool_name}
          </code>{' '}
          返回
        </div>
        <span>{expanded ? '▼' : '▶'}</span>
      </div>
      {expanded && (
        <pre className="mt-2 bg-white p-2 rounded text-xs overflow-x-auto">
          {JSON.stringify(display.result, null, 2)}
        </pre>
      )}
    </div>
  );
}