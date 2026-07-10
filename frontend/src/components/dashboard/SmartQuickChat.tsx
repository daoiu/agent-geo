import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Compass, Image as ImageIcon, Sparkles } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type Mode = 'fast' | 'expert' | 'vision';

interface ModeOption {
  id: Mode;
  label: string;
  icon: typeof Sparkles;
  hint: string;
}

const MODES: ModeOption[] = [
  { id: 'fast', label: '⚡ 快速模式', icon: Sparkles, hint: 'ReAct + 3 工具' },
  { id: 'expert', label: '🛠 专家模式', icon: Compass, hint: '深度推理 · 多步' },
  { id: 'vision', label: '📷 识图模式', icon: ImageIcon, hint: '截图/页面解析' },
];

/**
 * SmartQuickChat — Dashboard 内的智能助手快捷入口。
 *
 * 行为：
 *   - 用户在 textarea 输入，按下方「立即对话 →」或 Enter 跳转 `/agent?prefill=...`
 *   - 跳转后 AgentWorkspace 自适应打开一个新对话并填充输入
 *
 * 复用率：依赖 App.tsx 的路由接线 + AgentWorkspace 的 prefill 自动创建 session。
 */
export function SmartQuickChat() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [mode, setMode] = useState<Mode>('fast');

  function launch() {
    const q = text.trim();
    const url = q
      ? `/agent?mode=${mode}&prefill=${encodeURIComponent(q)}`
      : `/agent?mode=${mode}`;
    navigate(url);
  }

  const canSubmit = true; // empty allowed → 立即进入空 workspace 让用户看到完整 UI

  return (
    <Card aria-label="智能助手快捷对话">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle>智能助手</CardTitle>
            <CardDescription>
              自然语言入口 · ReAct 推理 · 3 工具（诊断 / 知识库 / 内容生成）
            </CardDescription>
          </div>
          <Button asChild variant="ghost" size="sm">
            <a href="/agent" aria-label="打开完整助手页面">
              <ArrowRight className="h-4 w-4" />
            </a>
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div role="tablist" aria-label="对话模式" className="flex flex-wrap gap-2">
          {MODES.map((m) => {
            const Icon = m.icon;
            const active = mode === m.id;
            return (
              <button
                key={m.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setMode(m.id)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                  active
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border bg-card text-muted-foreground hover:text-foreground'
                )}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                {m.label.replace(/^[⚡🛠📷]\s/, '')}
              </button>
            );
          })}
        </div>
        <div className="rounded-2xl border border-border bg-card">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (canSubmit) launch();
              }
            }}
            rows={2}
            placeholder="说一句话 · 如「帮我诊断小米」 (Shift+Enter 换行)"
            aria-label="快速对话输入"
            className="block w-full resize-none rounded-t-2xl bg-transparent px-4 py-3 text-sm leading-6 placeholder:text-muted-foreground focus:outline-none"
          />
          <div className="flex items-center justify-end gap-2 border-t px-3 py-2">
            <span className="mr-auto text-[10px] text-muted-foreground">
              {MODES.find((m) => m.id === mode)?.hint}
            </span>
            <Button type="button" size="sm" onClick={launch} disabled={!canSubmit}>
              立即对话
              <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
