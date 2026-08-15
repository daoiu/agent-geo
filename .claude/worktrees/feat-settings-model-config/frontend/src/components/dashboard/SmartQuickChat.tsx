import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

/**
 * SmartQuickChat — Dashboard 内的智能助手快捷入口。
 *
 * 行为：用户在 textarea 输入，按下方「立即对话 →」或 Enter 跳转
 * `/agent?prefill=...`。AgentWorkspace 会自动创建一个新对话并填充输入。
 *
 * 极简：不做模式选择，不带任何「没有的东西」（无登录邮箱、无第三方账号）。
 */
export function SmartQuickChat() {
  const navigate = useNavigate();
  const [text, setText] = useState('');

  function launch() {
    const q = text.trim();
    const url = q ? `/agent?prefill=${encodeURIComponent(q)}` : `/agent`;
    navigate(url);
  }

  return (
    <Card aria-label="智能助手快捷对话">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle>智能助手</CardTitle>
            <CardDescription>
              自然语言入口 · 诊断 / 知识库 / 内容生成
            </CardDescription>
          </div>
          <Button asChild variant="ghost" size="sm" aria-label="打开完整助手页面">
            <a href="/agent">
              <ArrowRight className="h-4 w-4" />
            </a>
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-2xl border border-border bg-card">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                launch();
              }
            }}
            rows={2}
            placeholder="说一句话 · 如「帮我诊断小米」（Shift+Enter 换行）"
            aria-label="快速对话输入"
            className="block w-full resize-none rounded-2xl bg-transparent px-4 py-3 text-sm leading-6 placeholder:text-muted-foreground focus:outline-none"
          />
          <div className="flex items-center justify-end border-t px-3 py-2">
            <Button type="button" size="sm" onClick={launch}>
              立即对话
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
