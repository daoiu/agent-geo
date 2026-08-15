import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';

export default function PublisherConfigPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', site_url: '', username: '', app_password: '' });

  const { data: configs, isLoading } = useQuery({
    queryKey: ['publishers'],
    queryFn: () => api.listPublishers(),
  });

  const create = useMutation({
    mutationFn: () => api.createPublisher(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['publishers'] });
      setShowForm(false);
      setForm({ name: '', site_url: '', username: '', app_password: '' });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deletePublisher(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['publishers'] }),
  });

  const test = useMutation({
    mutationFn: (id: string) => api.testPublisher(id),
  });

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-3xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6"><button
            type="button"
            onClick={() => setShowForm(true)}
            className="px-4 py-2 bg-primary text-white rounded-md"
          >
            + 添加凭证
          </button>
        </div>

        {showForm && (
          <div className="bg-white rounded-lg shadow p-6 mb-4">
            <h2 className="text-lg font-semibold mb-3">添加 WordPress 凭证</h2>
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="凭证名称（如：公司主站）" className="w-full px-3 py-2 border rounded-md mb-2" />
            <input type="url" value={form.site_url} onChange={(e) => setForm({ ...form, site_url: e.target.value })}
              placeholder="https://example.com" className="w-full px-3 py-2 border rounded-md mb-2" />
            <input type="text" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })}
              placeholder="WordPress 用户名" className="w-full px-3 py-2 border rounded-md mb-2" />
            <input type="password" value={form.app_password} onChange={(e) => setForm({ ...form, app_password: e.target.value })}
              placeholder="Application Password (WordPress 后台生成)" className="w-full px-3 py-2 border rounded-md mb-3" />
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowForm(false)} className="px-3 py-1 text-muted-foreground">取消</button>
              <button type="button" onClick={() => create.mutate()} disabled={!form.name || !form.site_url || form.app_password.length < 10 || create.isPending}
                className="px-4 py-1 bg-primary text-white rounded-md disabled:opacity-50">
                {create.isPending ? '添加中...' : '添加'}
              </button>
            </div>
          </div>
        )}

        {isLoading && <p className="text-muted-foreground">加载中...</p>}

        {configs && configs.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-muted-foreground">
            还没有凭证。
          </div>
        )}

        {configs && configs.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {configs.map((c) => (
              <div key={c.id} className="p-4 flex justify-between items-center">
                <div>
                  <div className="font-medium">{c.name}</div>
                  <div className="text-sm text-muted-foreground">{c.site_url} · {c.username}</div>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={async () => {
                      const result = await test.mutateAsync(c.id);
                      alert(result.ok ? '连接成功！' : `连接失败：${result.error}`);
                    }}
                    className="px-3 py-1 text-sm bg-[hsl(var(--brand-success))] text-white rounded"
                  >
                    测试
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (confirm(`删除凭证「${c.name}」？`)) remove.mutate(c.id);
                    }}
                    className="px-3 py-1 text-sm bg-destructive text-white rounded"
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
