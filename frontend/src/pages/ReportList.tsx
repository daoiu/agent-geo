import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate, scoreColor } from '@/lib/utils';

export default function ReportList() {
  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.listReports(),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">历史报告</h1>
          <Link
            to="/new"
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            + 新建诊断
          </Link>
        </div>

        {isLoading && <p className="text-gray-500">加载中...</p>}

        {reports && reports.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            还没有诊断报告。<Link to="/new" className="text-blue-600">立即创建</Link>
          </div>
        )}

        {reports && reports.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {reports.map((r) => (
              <Link
                key={r.id}
                to={`/reports/${r.id}`}
                className="block p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex justify-between items-center">
                  <div>
                    <div className="font-medium text-gray-900">{r.brand_name}</div>
                    <div className="text-sm text-gray-500">
                      {r.industry} · {formatDate(r.created_at)}
                    </div>
                  </div>
                  <div className="text-right">
                    {r.overall_score != null ? (
                      <div className={`text-2xl font-bold ${scoreColor(r.overall_score)}`}>
                        {r.overall_score.toFixed(0)}
                      </div>
                    ) : (
                      <div className="text-sm text-gray-400">{r.status}</div>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
