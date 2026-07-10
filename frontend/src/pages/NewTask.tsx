import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';

export default function NewTask() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const prefillBrand = params.get('brand') || '';
  const prefillTopic = params.get('topic') || '';

  const { data: kbs } = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: () => api.listKnowledgeBases(),
  });

  const [form, setForm] = useState({
    name: '',
    kb_id: '',
    brand: prefillBrand,
    topic: prefillTopic,
    keywords: '',
    article_count: 1,
    style: 'neutral' as 'neutral' | 'professional' | 'casual',
    target_length: 1500,
  });

  const create = useMutation({
    mutationFn: () =>
      api.createTask({
        name: form.name,
        kb_id: form.kb_id,
        brand: form.brand || undefined,
        topic: form.topic,
        keywords: form.keywords
          .split(/[,，\s]+/)
          .filter((k) => k.length > 0),
        article_count: form.article_count,
        style: form.style,
        target_length: form.target_length,
      }),
    onSuccess: (task) => navigate(`/tasks/${task.id}`),
  });

  const canSubmit =
    form.name.trim() &&
    form.kb_id &&
    form.topic.trim().length >= 5 &&
    !create.isPending;

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-2xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">任务名 *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">知识库 *</label>
            <select
              value={form.kb_id}
              onChange={(e) => setForm({ ...form, kb_id: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="">-- 选择知识库 --</option>
              {kbs?.map((kb) => (
                <option key={kb.id} value={kb.id}>
                  {kb.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">品牌名</label>
            <input
              type="text"
              value={form.brand}
              onChange={(e) => setForm({ ...form, brand: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
              placeholder={prefillBrand ? '' : '如：小米'}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">主题 *</label>
            <textarea
              value={form.topic}
              onChange={(e) => setForm({ ...form, topic: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
              rows={2}
              placeholder="如：撰写一篇关于小米 14 手机的深度评测"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              关键词（逗号分隔）
            </label>
            <input
              type="text"
              value={form.keywords}
              onChange={(e) => setForm({ ...form, keywords: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
              placeholder="如：性能, 拍照, 续航"
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">文章数</label>
              <input
                type="number"
                min={1}
                max={20}
                value={form.article_count}
                onChange={(e) =>
                  setForm({ ...form, article_count: Number(e.target.value) })
                }
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">风格</label>
              <select
                value={form.style}
                onChange={(e) =>
                  setForm({
                    ...form,
                    style: e.target.value as 'neutral' | 'professional' | 'casual',
                  })
                }
                className="w-full px-3 py-2 border rounded-md"
              >
                <option value="neutral">中性</option>
                <option value="professional">专业</option>
                <option value="casual">轻松</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">目标字数</label>
              <input
                type="number"
                min={300}
                max={10000}
                step={100}
                value={form.target_length}
                onChange={(e) =>
                  setForm({ ...form, target_length: Number(e.target.value) })
                }
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
          </div>

          {create.isError && (
            <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm">
              创建失败：{String(create.error)}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => navigate('/tasks')}
              className="px-4 py-2 text-muted-foreground"
            >
              取消
            </button>
            <button
              type="button"
              onClick={() => create.mutate()}
              disabled={!canSubmit}
              className="px-6 py-2 bg-primary text-white rounded-md disabled:opacity-50"
            >
              {create.isPending ? '创建中...' : '创建任务'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
