import { Link } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Bot,
  Compass,
  DollarSign,
  ListChecks,
  Plus,
  Settings as SettingsIcon,
} from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { SectionCardGrid, type SectionCard } from '@/components/layout/SectionCardGrid';
import { SmartQuickChat } from '@/components/dashboard/SmartQuickChat';

/**
 * v0.7 HarmonyOS Dashboard — the diagnostic home page (mounted at
 * `/diagnose` after Task 5's redirect-or-move refactor; legacy `/`
 * redirects here too).
 *
 * Composition (spec §5.2):
 *   - 7 service cards in a 1→2→3→4 responsive grid
 *   - SmartQuickChat card (prefill → /agent) preserved from v0.6
 *
 * Cards are static — no React Query on the home page itself; the actual
 * per-card data lives behind the destination routes.
 */
export default function Dashboard() {
  const cards: SectionCard[] = [
    {
      to: '/diagnose/new',
      title: '新建诊断',
      description: '启动 6 阶段流水线,5 分钟出报告',
      icon: <Plus className="h-5 w-5" aria-hidden="true" />,
      badge: '主入口',
    },
    {
      to: '/diagnose/reports',
      title: '最近报告',
      description: '按时间倒序 · Top 10',
      icon: <ListChecks className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/agent',
      title: 'Multi-Agent 时间线',
      description: 'specialist 切换 + handoff 一览',
      icon: <Bot className="h-5 w-5" aria-hidden="true" />,
      badge: '新',
    },
    {
      to: '/cost',
      title: '本月成本',
      description: '按 provider / model 拆分',
      icon: <DollarSign className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/agent',
      title: 'Replay 最近会话',
      description: '从断点续跑推理流',
      icon: <Activity className="h-5 w-5" aria-hidden="true" />,
    },
    {
      to: '/settings/dev-tools',
      title: '故障注入(dev)',
      description: 'LLM 超时 / 工具错误 / 网络故障',
      icon: <AlertTriangle className="h-5 w-5" aria-hidden="true" />,
      badge: 'dev',
    },
    {
      to: '/settings/general',
      title: '设置',
      description: '通用 · 通知 · 设备',
      icon: <SettingsIcon className="h-5 w-5" aria-hidden="true" />,
    },
  ];

  return (
    <div className="space-y-8">
      <header className="flex items-baseline gap-3">
        <Compass className="h-6 w-6 text-primary" aria-hidden="true" />
        <h1 className="text-2xl font-semibold text-fg">诊断</h1>
        <span className="text-sm text-fg-muted">
          从这里发起一次诊断,或进入下面任意一项
        </span>
      </header>

      <section aria-label="诊断服务卡片" className="-mx-6">
        <SectionCardGrid cards={cards} />
      </section>

      <Card>
        <CardContent>
          <SmartQuickChat />
          <div className="mt-3 text-right">
            <Link
              to="/agent"
              className="text-xs text-fg-muted transition-colors hover:text-primary"
            >
              打开完整工作台 →
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
