import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';

import { api } from '@/api/client';

export default function NewMonitor() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: '',
    brand: '',
    industry: '',
    target_questions: '',
    frequency: 'daily' as 'hourly' | 'daily' | 'weekly',
    providers: 'deepseek',
    notify_email: '',
    change_threshold: 0.15,
  });

  const create = useMutation({
    mutationFn: () =>
      api.createMonitor({
        name: form.name,
        brand: form.brand,
        industry: form.industry,
        target_questions: form.target_questions
          .split('\n')
          .map((q) => q.trim())
          .filter(Boolean),
        frequency: form.frequency,
        providers: form.providers.split(',').map((p) => p.trim()).filter(Boolean),
        notify_email: form.notify_email || undefined,
        change_threshold: form.change_threshold,
      }),
    onSuccess: (task) => navigate(`/monitors/${task.id}`),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-2xl mx-auto px-4"><form onSubmit={submit} className="bg-white rounded-lg shadow p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">任务名称</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">品牌</label>
              <input
                type="text"
                value={form.brand}
                onChange={(e) => setForm({ ...form, brand: e.target.value })}
                required
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">行业</label>
              <input
                type="text"
                value={form.industry}
                onChange={(e) => setForm({ ...form, industry: e.target.value })}
                required
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              监测问题（每行一个，1-5 个）
            </label>
            <textarea
              value={form.target_questions}
              onChange={(e) => setForm({ ...form, target_questions: e.target.value })}
              required
              rows={4}
              placeholder={'小米14 怎么样\n小米 vs 华为'}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">频率</label>
              <select
                value={form.frequency}
                onChange={(e) => setForm({ ...form, frequency: e.target.value as 'hourly' | 'daily' | 'weekly' })}
                className="w-full px-3 py-2 border rounded-md"
              >
                <option value="hourly">每小时</option>
                <option value="daily">每天</option>
                <option value="weekly">每周</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                变化阈值 (0.01-0.5)
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                max="0.5"
                value={form.change_threshold}
                onChange={(e) => setForm({ ...form, change_threshold: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              LLM Providers（逗号分隔）
            </label>
            <input
              type="text"
              value={form.providers}
              onChange={(e) => setForm({ ...form, providers: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">
              通知邮箱（变化时通知，可选）
            </label>
            <input
              type="email"
              value={form.notify_email}
              onChange={(e) => setForm({ ...form, notify_email: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => navigate('/monitors')}
              className="px-4 py-2 text-muted-foreground"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={create.isPending}
              className="px-4 py-2 bg-primary text-white rounded-md disabled:opacity-50"
            >
              {create.isPending ? '创建中...' : '创建'}
            </button>
          </div>
          {create.isError && (
            <p className="text-sm text-destructive">创建失败：{String(create.error)}</p>
          )}
        </form>
      </div>
    </div>
  );
}
