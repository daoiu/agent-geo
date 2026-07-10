import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  CircleDashed,
  FileText,
  LineChart,
  ListChecks,
  Plus,
  Sparkles,
  TriangleAlert,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState, DefaultEmptyIllustration } from '@/components/ui/empty-state';
import { StageCard, type StageStatus } from '@/components/flow/StageCard';
import { api } from '@/api/client';
import { formatDate, scoreColor } from '@/lib/utils';
import { usePipelineState } from '@/lib/usePipelineState';
import type { PipelineNode } from '@/components/layout/PipelineRail';

// ---------------------------------------------------------------------------
// Section: Hero CTA
// ---------------------------------------------------------------------------

function HeroCtas() {
  return (
    <div className="mt-4 flex flex-wrap items-center gap-3">
      <Button asChild size="lg">
        <Link to="/new">
          <Plus className="h-4 w-4" aria-hidden="true" />
          新建诊断
        </Link>
      </Button>
      <Button asChild variant="outline" size="lg">
        <Link to="/tasks/new">
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          启动批量生成
        </Link>
      </Button>
      <Button asChild variant="ghost" size="lg">
        <Link to="/monitors/new">
          <LineChart className="h-4 w-4" aria-hidden="true" />
          监测品牌表现
        </Link>
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Pipeline 6-stage overview
// ---------------------------------------------------------------------------

const STAGE_ICON: Record<PipelineNode['key'], typeof Activity> = {
  diagnose: Activity,
  generate: Sparkles,
  review: ListChecks,
  publish: FileText,
  monitor: LineChart,
  track: CheckCircle2,
};

function deriveStageMeta(node: PipelineNode): string {
  if (node.count != null) return `${node.count} 项进行中`;
  switch (node.status) {
    case 'done':
      return '当前阶段无待办';
    case 'error':
      return '需要处理';
    case 'running':
      return '处理中';
    default:
      return '等待开始';
  }
}

function mapNodeStatus(s: PipelineNode['status']): StageStatus {
  return s;
}

function PipelineOverview() {
  const { nodes, isLoading } = usePipelineState();
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {nodes.map((n) => {
        const Icon = STAGE_ICON[n.key];
        return (
          <Link
            key={n.key}
            to={n.to}
            aria-label={`${n.label} · 阶段详情`}
            className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <StageCard
              title={n.label}
              status={mapNodeStatus(n.status)}
              meta={deriveStageMeta(n)}
              icon={<Icon className="h-4 w-4" />}
            />
          </Link>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: KPI strip
// ---------------------------------------------------------------------------

interface KpiBlock {
  label: string;
  value: number;
  suffix?: string;
  tone: 'primary' | 'warning' | 'destructive' | 'success' | 'muted';
}

function KpiStrip() {
  const reportsQ = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.listReports(),
  });
  const reviewsQ = useQuery({
    queryKey: ['review-queue', 'pending'],
    queryFn: () => api.listReviewQueue('pending'),
  });
  const publishesQ = useQuery({
    queryKey: ['publish-jobs'],
    queryFn: () => api.listPublishJobs(),
  });
  const monitorsQ = useQuery({
    queryKey: ['monitors'],
    queryFn: () => api.listMonitors(),
  });

  const failed = publishesQ.data?.filter((j) => j.status === 'failed').length ?? 0;
  const queue = reviewsQ.data?.length ?? 0;
  const active = monitorsQ.data?.filter((m) => m.is_active).length ?? 0;
  const totalReports = reportsQ.data?.length ?? 0;

  const blocks: KpiBlock[] = [
    { label: '诊断报告', value: totalReports, tone: 'primary' },
    { label: '待审核', value: queue, tone: queue > 0 ? 'warning' : 'muted' },
    {
      label: '发布失败',
      value: failed,
      tone: failed > 0 ? 'destructive' : 'muted',
    },
    {
      label: '监测活跃',
      value: active,
      tone: active > 0 ? 'success' : 'muted',
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {blocks.map((b) => (
        <Card key={b.label} className="px-4 py-3">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs font-medium text-muted-foreground">{b.label}</span>
            {b.tone === 'destructive' && (
              <TriangleAlert className="h-4 w-4 text-destructive" aria-hidden="true" />
            )}
          </div>
          <div
            className={
              'mt-1 text-3xl font-semibold tabular-nums ' +
              (b.tone === 'destructive'
                ? 'text-destructive'
                : b.tone === 'warning'
                  ? 'text-foreground'
                  : 'text-foreground')
            }
          >
            {b.value}
            {b.suffix && <span className="ml-1 text-sm text-muted-foreground">{b.suffix}</span>}
          </div>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Recent reports (Top 3)
// ---------------------------------------------------------------------------

function RecentReports() {
  const { data, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.listReports(),
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="还没有诊断报告"
        description="启动一次诊断，5 分钟后即可在此处查看。"
        icon={<DefaultEmptyIllustration />}
        action={
          <Button asChild size="sm">
            <Link to="/new">+ 新建诊断</Link>
          </Button>
        }
      />
    );
  }
  const top = [...data]
    .sort((a, b) => (a.created_at > b.created_at ? -1 : 1))
    .slice(0, 3);
  return (
    <ul className="divide-y rounded-md border">
      {top.map((r) => (
        <li key={r.id}>
          <Link
            to={`/reports/${r.id}`}
            className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-muted"
          >
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-foreground">{r.brand_name}</div>
              <div className="truncate text-xs text-muted-foreground">
                {r.industry} · {formatDate(r.created_at)}
              </div>
            </div>
            <div className="shrink-0 text-right">
              {r.overall_score != null ? (
                <span className={`text-lg font-semibold tabular-nums ${scoreColor(r.overall_score)}`}>
                  {r.overall_score.toFixed(0)}
                </span>
              ) : (
                <Badge variant="outline">{r.status}</Badge>
              )}
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Section: Recent tasks (Top 3)
// ---------------------------------------------------------------------------

const TASK_STATUS_LABEL: Record<string, string> = {
  pending: '等待',
  running: '运行',
  completed: '完成',
  failed: '失败',
  cancelled: '取消',
};

const TASK_STATUS_TONE: Record<string, 'outline' | 'info' | 'success' | 'destructive'> = {
  pending: 'outline',
  running: 'info',
  completed: 'success',
  failed: 'destructive',
  cancelled: 'outline',
};

function RecentTasks() {
  const { data, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.listTasks(),
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="还没有生成任务"
        description="先准备一个知识库，再启动批量生成。"
        icon={<DefaultEmptyIllustration />}
        action={
          <Button asChild size="sm" variant="outline">
            <Link to="/tasks/new">创建任务</Link>
          </Button>
        }
      />
    );
  }
  const top = [...data]
    .sort((a, b) => (a.created_at > b.created_at ? -1 : 1))
    .slice(0, 3);
  return (
    <ul className="divide-y rounded-md border">
      {top.map((t) => (
        <li key={t.id}>
          <Link
            to={`/tasks/${t.id}`}
            className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-muted"
          >
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-foreground">{t.name}</div>
              <div className="truncate text-xs text-muted-foreground">
                {t.topic} · 进度 {Math.round(t.progress ?? 0)}%
              </div>
            </div>
            <Badge variant={TASK_STATUS_TONE[t.status] ?? 'outline'}>
              {TASK_STATUS_LABEL[t.status] ?? t.status}
            </Badge>
          </Link>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Section: Pending review queue preview (Top 5)
// ---------------------------------------------------------------------------

function ReviewPreview() {
  const { data, isLoading } = useQuery({
    queryKey: ['review-queue', 'pending'],
    queryFn: () => api.listReviewQueue('pending'),
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="审核队列干净"
        description="没有待审核文章。"
        icon={<CircleDashed className="h-10 w-10 text-muted-foreground" aria-hidden="true" />}
      />
    );
  }
  const top = data.slice(0, 5);
  return (
    <>
      <ul className="divide-y rounded-md border">
        {top.map((a) => (
          <li key={a.id}>
            <Link
              to={`/reviews/${a.id}`}
              className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-muted"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-foreground">
                  {a.title ?? '(无标题)'}
                </div>
                <div className="truncate text-xs text-muted-foreground">
                  {a.llm_provider ?? '未生成'} · {a.cited_chunks?.length ?? 0} 处引用
                </div>
              </div>
              <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
      <div className="mt-2 text-right">
        <Link
          to="/reviews"
          className="text-xs text-muted-foreground transition-colors hover:text-primary"
        >
          查看全部 →
        </Link>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Section: Monitor trends (Top 1 active monitor, 7-day trend)
// ---------------------------------------------------------------------------

function DeltaPill({ delta }: { delta: number }) {
  if (delta === 0) {
    return <span className="text-xs text-muted-foreground">与上周持平</span>;
  }
  const up = delta > 0;
  return (
    <span
      className={
        'text-xs tabular-nums ' + (up ? 'text-foreground font-medium' : 'text-destructive font-medium')
      }
    >
      {up ? '▲' : '▼'} {Math.abs(delta).toFixed(1)} pts
    </span>
  );
}

function MonitorTrendWidget() {
  const monitorsQ = useQuery({
    queryKey: ['monitors'],
    queryFn: () => api.listMonitors(),
  });

  const active = monitorsQ.data?.find((m) => m.is_active);
  const firstId = active?.id ?? monitorsQ.data?.[0]?.id;

  const trendsQ = useQuery({
    queryKey: ['monitor-trends', firstId ?? 'none'],
    queryFn: () => api.getMonitorTrends(firstId as string, 30),
    enabled: Boolean(firstId),
  });

  if (monitorsQ.isLoading) {
    return <Skeleton className="h-24 w-full" />;
  }
  if (!active && !firstId) {
    return (
      <EmptyState
        title="还没有监测任务"
        description="创建一个监测以查看品牌提及率趋势。"
        icon={<LineChart className="h-10 w-10 text-muted-foreground" aria-hidden="true" />}
        action={
          <Button asChild size="sm">
            <Link to="/monitors/new">+ 新建监测</Link>
          </Button>
        }
      />
    );
  }

  const points = trendsQ.data?.points ?? [];
  const recent = points.slice(-7);
  const earlier = points.slice(-14, -7);
  const recentAvg = recent.length
    ? recent.reduce((s, p) => s + p.mention_rate, 0) / recent.length
    : 0;
  const earlierAvg = earlier.length
    ? earlier.reduce((s, p) => s + p.mention_rate, 0) / earlier.length
    : 0;
  const delta = recentAvg - earlierAvg;

  const lastRate = points.at(-1)?.mention_rate;
  const total30 = points.length;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="truncate font-medium text-foreground">{active?.name ?? '趋势快照'}</span>
        <DeltaPill delta={delta} />
      </div>
      <div className="flex items-baseline gap-3">
        <span className="text-3xl font-semibold tabular-nums text-foreground">
          {lastRate != null ? `${lastRate.toFixed(1)}%` : '—'}
        </span>
        <span className="text-xs text-muted-foreground">最近一次提及率</span>
      </div>
      <div className="text-xs text-muted-foreground tabular-nums">
        {total30} 个采样 · {recent.length} / 14 天
      </div>
      {trendsQ.isLoading ? (
        <Skeleton className="h-8 w-full" />
      ) : points.length === 0 ? (
        <p className="text-xs text-muted-foreground">暂无采样</p>
      ) : (
        <SparkLine points={recent.map((p) => p.mention_rate)} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Quick links
// ---------------------------------------------------------------------------

const QUICK_LINKS = [
  { to: '/knowledge', title: '知识库', desc: 'PDF / Word / MD → Chunks' },
  { to: '/publishers', title: '发布平台', desc: 'WordPress Application Password' },
  { to: '/notifications', title: '阈值通知', desc: '邮件渠道与触发阈值' },
  { to: '/agent', title: '智能助手', desc: '自然语言入口 (ReAct · 3 工具)' },
] as const;

function QuickLinks() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {QUICK_LINKS.map((q) => (
        <Link
          key={q.to}
          to={q.to}
          className="group flex flex-col gap-1 rounded-md border bg-card p-3 transition-colors hover:border-primary"
        >
          <span className="text-sm font-medium text-foreground">{q.title}</span>
          <span className="text-xs text-muted-foreground">{q.desc}</span>
          <ArrowRight
            className="mt-1 h-3.5 w-3.5 self-end text-muted-foreground transition-colors group-hover:text-primary"
            aria-hidden="true"
          />
        </Link>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline deps: SparkLine is local to this file to keep the Dashboard cohesive
// ---------------------------------------------------------------------------

function SparkLine({ points }: { points: number[] }) {
  if (points.length < 2) return null;
  const w = 240;
  const h = 32;
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const span = Math.max(max - min, 0.1);
  const stepX = w / (points.length - 1);
  const path = points
    .map((y, i) => {
      const x = i * stepX;
      const ny = h - ((y - min) / span) * h;
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${ny.toFixed(1)}`;
    })
    .join(' ');
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label="7 天提及率趋势"
      className="h-8 w-full"
      preserveAspectRatio="none"
    >
      <path d={path} fill="none" stroke="hsl(var(--primary))" strokeWidth="1.5" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Dashboard root
// ---------------------------------------------------------------------------

/**
 * Dashboard — the `/` landing page.
 *
 * Wires up:
 *   1. Hero CTAs (create diagnosis / batch generate / monitor)
 *   2. 6-stage pipeline overview (re-uses usePipelineState())
 *   3. KPI strip (4 metric cards)
 *   4. Recent activity (Top 3 reports / Top 3 tasks / pending review preview)
 *   5. Monitor trend widget (Top 1 active monitor, 7-day delta)
 *   6. Quick-link tile set
 *
 * All data is fetched via React Query. Cache keys match the pages they
 * correspond to so navigation does not duplicate requests.
 */
export default function Dashboard() {
  return (
    <div className="space-y-8">
      <HeroCtas />
      <Section title="优化流水线" subtitle="按阶段聚合当前活动；点击进入对应阶段">
        <PipelineOverview />
      </Section>
      <KpiStrip />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>最近诊断</CardTitle>
            <CardDescription>按时间倒序的 Top 3</CardDescription>
          </CardHeader>
          <CardContent>
            <RecentReports />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>最近生成任务</CardTitle>
            <CardDescription>按时间倒序的 Top 3</CardDescription>
          </CardHeader>
          <CardContent>
            <RecentTasks />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>待审核队列</CardTitle>
            <CardDescription>Top 5 待审文章</CardDescription>
          </CardHeader>
          <CardContent>
            <ReviewPreview />
          </CardContent>
        </Card>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>监测趋势</CardTitle>
            <CardDescription>第一个活跃监测 · 7 天对比前 7 天</CardDescription>
          </CardHeader>
          <CardContent>
            <MonitorTrendWidget />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>快捷入口</CardTitle>
            <CardDescription>常用模块直链</CardDescription>
          </CardHeader>
          <CardContent>
            <QuickLinks />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tiny presentational wrapper — Section title + subtitle + children
// ---------------------------------------------------------------------------

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-label={title} className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        {subtitle && <span className="text-xs text-muted-foreground">{subtitle}</span>}
      </div>
      {children}
    </section>
  );
}
