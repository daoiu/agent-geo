import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState, DefaultEmptyIllustration } from '@/components/ui/empty-state';
import { Badge } from '@/components/ui/badge';
import { api } from '@/api/client';

/**
 * Settings — system information, configuration status, and quick links.
 *
 * P0 version: read-only summary. P1+ will surface mutations (toggle SSRF mode,
 * rotate SMTP password, etc.) when those API endpoints exist.
 */
export default function SettingsPage() {
  // Light health probe — fetch publishers (cheap list endpoint) to verify
  // the backend is reachable from this page.
  const healthQ = useQuery({
    queryKey: ['settings', 'health'],
    queryFn: async () => {
      const start = Date.now();
      try {
        await api.listPublishers();
        return { ok: true, latencyMs: Date.now() - start };
      } catch (e) {
        return { ok: false, latencyMs: Date.now() - start, error: String(e) };
      }
    },
    refetchOnWindowFocus: false,
    retry: false,
  });

  return (
    <div className="space-y-6">
      <header className="rounded-lg border border-border bg-card p-6 shadow-card">
        <h1 className="text-2xl font-semibold text-foreground">系统设置</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          查看后端连通性、LLM 配置状态与各模块入口。变更类操作请前往对应模块页。
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>后端连通性</CardTitle>
              <CardDescription>采样自 /api/publishers 的最近一次请求</CardDescription>
            </div>
            <HealthBadge
              loading={healthQ.isLoading}
              data={healthQ.data}
              error={healthQ.error}
            />
          </CardHeader>
          <CardContent>
            {healthQ.isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-4 w-1/3" />
              </div>
            ) : healthQ.data ? (
              <dl className="grid grid-cols-2 gap-y-2 text-sm">
                <dt className="text-muted-foreground">状态</dt>
                <dd className="text-foreground">{healthQ.data.ok ? '可达' : '不可达'}</dd>
                <dt className="text-muted-foreground">延迟</dt>
                <dd className="tabular-nums text-foreground">{healthQ.data.latencyMs} ms</dd>
                {!healthQ.data.ok && (
                  <>
                    <dt className="text-muted-foreground">错误</dt>
                    <dd className="text-destructive">{healthQ.data.error}</dd>
                  </>
                )}
              </dl>
            ) : (
              <EmptyState
                title="未知"
                icon={<DefaultEmptyIllustration />}
                description="未获取连通性信息"
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>前端版本</CardTitle>
            <Badge>v0.6.0 (Phase 0)</Badge>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-muted-foreground">框架</dt>
              <dd className="text-foreground">React 18 + Vite 6</dd>
              <dt className="text-muted-foreground">设计系统</dt>
              <dd className="text-foreground">Teal + Orange · Inter</dd>
              <dt className="text-muted-foreground">构建</dt>
              <dd className="text-foreground">预发布</dd>
            </dl>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>模块入口</CardTitle>
            <CardDescription>常用配置分布在以下页面</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <ModuleLink
            to="/publishers"
            label="发布平台配置"
            desc="WordPress / 站点凭证 (Application Password)"
          />
          <ModuleLink
            to="/notifications"
            label="阈值与通知"
            desc="邮件渠道与监测阈值默认"
          />
          <ModuleLink to="/knowledge" label="知识库" desc="上传 PDF / Word / MD 用于内容生成" />
          <ModuleLink to="/agent" label="智能助手" desc="自然语言入口；ReAct + 3 工具" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>关于</CardTitle>
            <CardDescription>项目基本说明</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>
            GEO 优化系统 — 给非技术市场人员用：诊断品牌 GEO 健康度 + 基于自有知识库批量生成内容 + 自动发布到
            WordPress + 监测提及率变化 + 自然语言入口(自主决策 Agent)。
          </p>
          <p>
            本项目 <strong className="text-foreground">只做诊断、建议、内容生成辅助、发布辅助和监测</strong>，
            不做内容伪造、AI 投毒等黑帽 GEO 操作。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function HealthBadge({
  loading,
  data,
  error,
}: {
  loading: boolean;
  data?: { ok: boolean; latencyMs: number };
  error?: unknown;
}) {
  if (loading) return <Skeleton className="h-6 w-20" />;
  if (error) return <Badge variant="destructive" dot>错误</Badge>;
  if (!data) return <Badge variant="outline" dot>未知</Badge>;
  return data.ok ? (
    <Badge variant="success" dot>
      在线
    </Badge>
  ) : (
    <Badge variant="destructive" dot>
      离线
    </Badge>
  );
}

function ModuleLink({ to, label, desc }: { to: string; label: string; desc: string }) {
  return (
    <Link
      to={to}
      className="group rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary"
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{label}</span>
        <span className="text-muted-foreground group-hover:text-primary" aria-hidden="true">
          →
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{desc}</p>
    </Link>
  );
}
