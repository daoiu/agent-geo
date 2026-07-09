import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';

const STATUS_LABELS: Record<string, string> = {
  pending: '等待开始',
  crawling: '正在抓取官网',
  querying_llm: '正在向 AI 提问',
  scoring: '正在评分',
  rendering: '正在生成报告',
  completed: '完成',
  failed: '失败',
};

export default function DiagnosisStatus() {
  const { taskId = '' } = useParams<{ taskId: string }>();
  const navigate = useNavigate();

  const { data: task, error } = useQuery({
    queryKey: ['task-status', taskId],
    queryFn: () => api.getStatus(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'completed' || status === 'failed') return false;
      return 1500;
    },
  });

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-red-50 p-6 rounded-lg">
          <h2 className="text-red-700 font-medium">加载失败</h2>
          <p className="text-red-600 text-sm mt-1">{String(error)}</p>
        </div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500">
        加载中...
      </div>
    );
  }

  if (task.status === 'completed') {
    setTimeout(() => navigate(`/reports/${taskId}`), 0);
    return <div className="min-h-screen flex items-center justify-center">跳转中...</div>;
  }

  if (task.status === 'failed') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-red-50 p-6 rounded-lg max-w-md">
          <h2 className="text-red-700 font-medium text-lg">诊断失败</h2>
          <p className="text-red-600 mt-2">{task.error_message}</p>
          <button
            type="button"
            onClick={() => navigate('/new')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md"
          >
            重新诊断
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-md max-w-md w-full">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          {STATUS_LABELS[task.status] ?? '处理中...'}
        </h1>
        <p className="text-gray-600 mb-6">
          品牌：<strong>{task.request.brand_name}</strong>
        </p>

        {/* Progress bar */}
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden mb-2">
          <div
            className="bg-blue-600 h-full transition-all duration-500"
            style={{ width: `${task.progress}%` }}
          />
        </div>
        <p className="text-sm text-gray-500 text-right">{task.progress}%</p>

        {/* Stage indicators */}
        <div className="mt-6 space-y-2">
          {['crawling', 'querying_llm', 'scoring', 'rendering'].map((stage) => {
            const stageOrder = ['pending', 'crawling', 'querying_llm', 'scoring', 'rendering', 'completed'];
            const currentIdx = stageOrder.indexOf(task.status);
            const stageIdx = stageOrder.indexOf(stage);
            const isDone = currentIdx > stageIdx;
            const isCurrent = currentIdx === stageIdx;
            return (
              <div key={stage} className="flex items-center text-sm">
                <div
                  className={`w-5 h-5 rounded-full mr-2 flex items-center justify-center text-xs ${
                    isDone ? 'bg-green-500 text-white' : isCurrent ? 'bg-blue-500 text-white' : 'bg-gray-200'
                  }`}
                >
                  {isDone ? '✓' : isCurrent ? '●' : ''}
                </div>
                <span className={isCurrent ? 'font-medium' : 'text-gray-500'}>
                  {STATUS_LABELS[stage]}
                </span>
              </div>
            );
          })}
        </div>

        <p className="mt-6 text-xs text-gray-400 text-center">
          通常需要 60-90 秒。请勿关闭页面。
        </p>
      </div>
    </div>
  );
}
