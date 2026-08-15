import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { api } from '@/api/client';

export default function NotificationSettings() {
  const [to, setTo] = useState('');

  const send = useMutation({
    mutationFn: () => api.sendTestEmail(to),
  });

  return (
    <div className="min-h-screen bg-muted py-8">
      <div className="max-w-2xl mx-auto px-4"><div className="bg-white rounded-lg shadow p-6">
          <p className="text-sm text-muted-foreground mb-4">
            通知邮件使用 .env 中配置的 SMTP 服务。点击下方按钮发送测试邮件，验证 SMTP 配置正确。
          </p>
          <input
            type="email"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="收件人邮箱"
            className="w-full px-3 py-2 border rounded-md mb-3"
          />
          <button
            type="button"
            onClick={() => send.mutate()}
            disabled={!to || send.isPending}
            className="px-4 py-2 bg-primary text-white rounded-md disabled:opacity-50"
          >
            {send.isPending ? '发送中...' : '发送测试邮件'}
          </button>
          {send.isSuccess && (
            <p className={`mt-3 text-sm ${send.data.ok ? 'text-[hsl(var(--brand-success))]' : 'text-destructive'}`}>
              {send.data.ok ? '发送成功！请检查收件箱（包括垃圾邮件）。' : `失败：${send.data.error}`}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
