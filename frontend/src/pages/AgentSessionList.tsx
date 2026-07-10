import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

export default function AgentSessionList() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: sessions, isLoading } = useQuery({
    queryKey: ['agent-sessions'],
    queryFn: () => api.listAgentSessions(),
  });

  const create = useMutation({
    mutationFn: () => api.createAgentSession(),
    onSuccess: (session) => {
      qc.invalidateQueries({ queryKey: ['agent-sessions'] });
      navigate(`/agent/${session.id}`);
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteAgentSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-sessions'] }),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Agent 会话</h1>
          <button
            type="button"
            onClick={() => create.mutate()}
            disabled={create.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {create.isPending ? '创建中...' : '+ 新建对话'}
          </button>
        </div>

        {isLoading && <p className="text-gray-500">加载中...</p>}

        {sessions && sessions.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            还没有对话。<br />
            <span className="text-sm">试试说"帮我诊断小米"</span>
          </div>
        )}

        {sessions && sessions.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {sessions.map((s) => (
              <div
                key={s.id}
                className="p-4 flex justify-between items-center hover:bg-gray-50"
              >
                <Link to={`/agent/${s.id}`} className="flex-1">
                  <div className="font-medium text-gray-900">{s.title}</div>
                  <div className="text-sm text-gray-500">
                    {formatDate(s.updated_at)}
                  </div>
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    if (confirm(`删除对话「${s.title}」？`)) {
                      remove.mutate(s.id);
                    }
                  }}
                  className="text-red-600 text-sm px-2 hover:text-red-800"
                >
                  删除
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}