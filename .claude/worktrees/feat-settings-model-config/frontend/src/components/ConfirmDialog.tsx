interface ConfirmDialogProps {
  toolName: string;
  arguments: Record<string, unknown>;
  onApprove: () => void;
  onCancel: () => void;
  pending: boolean;
}

const TOOL_LABELS: Record<string, string> = {
  diagnose_brand: '诊断品牌',
  search_knowledge: '查询知识库',
  generate_article: '生成文章',
};

export function ConfirmDialog({
  toolName,
  arguments: args,
  onApprove,
  onCancel,
  pending,
}: ConfirmDialogProps) {
  const label = TOOL_LABELS[toolName] || toolName;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold mb-3">确认执行：{label}</h3>
        <div className="bg-gray-50 p-3 rounded mb-4 text-sm">
          <pre className="overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(args, null, 2)}
          </pre>
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="px-4 py-2 text-gray-600 hover:text-gray-900 disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onApprove}
            disabled={pending}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {pending ? '处理中...' : '确认'}
          </button>
        </div>
      </div>
    </div>
  );
}