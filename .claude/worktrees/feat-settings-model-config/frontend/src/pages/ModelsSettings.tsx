/**
 * 设置 — 模型配置页面 (Task 41)。
 *
 * 三个 provider 卡 + 三档 tier 选择 + fallback/llm_providers 多选 + 保存/重置。
 * 顶部 source badge 提示当前配置来自 env 还是 JSON 覆盖。
 */
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import {
  settingsApi,
  type ModelConfigDTO,
  type ProviderUpdate,
} from '@/api/client';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogTrigger,
  DialogClose,
} from '@/components/ui/dialog';

type ProviderFormState = {
  base_url: string;
  model: string;
  api_key_input: string;
  api_key_set: boolean;
  api_key_masked: string;
  api_key_dirty: boolean;
};

const PROVIDER_DISPLAY: Record<string, string> = {
  deepseek: 'DeepSeek',
  kimi: 'Kimi (Moonshot)',
  openai: 'OpenAI',
};

function extractApiError(err: unknown): { code?: string; message: string; field?: string } {
  if (err instanceof Error) {
    try {
      const parsed = JSON.parse(err.message);
      if (parsed?.detail && typeof parsed.detail === 'object') {
        return {
          code: parsed.detail.code,
          message: parsed.detail.message ?? '',
          field: parsed.detail.field,
        };
      }
    } catch {
      /* not JSON */
    }
    return { message: err.message };
  }
  return { message: String(err) };
}

export default function ModelsSettings() {
  const qc = useQueryClient();

  const configQ = useQuery({
    queryKey: ['settings', 'model-config'],
    queryFn: () => settingsApi.getModelConfig(),
  });

  const [providersState, setProvidersState] = useState<Record<string, ProviderFormState>>({});
  const [tiersState, setTiersState] = useState<{ cheap: string; standard: string; premium: string }>({
    cheap: '',
    standard: '',
    premium: '',
  });
  const [fallbackState, setFallbackState] = useState<string[]>([]);
  const [llmProvidersState, setLlmProvidersState] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false);
  const [encryptionBanner, setEncryptionBanner] = useState(false);

  // 首次 GET 成功后初始化表单 state
  useEffect(() => {
    if (!configQ.data) return;
    if (Object.keys(providersState).length > 0) return;
    const next: Record<string, ProviderFormState> = {};
    configQ.data.providers.forEach((p) => {
      next[p.name] = {
        base_url: p.base_url,
        model: p.model,
        api_key_input: '',
        api_key_set: p.api_key_set,
        api_key_masked: p.api_key_masked,
        api_key_dirty: false,
      };
    });
    setProvidersState(next);
    setTiersState(configQ.data.tiers);
    setFallbackState(configQ.data.fallback_chain);
    setLlmProvidersState(configQ.data.llm_providers);
    setDirty(false);
  }, [configQ.data, providersState]);

  const saveMutation = useMutation({
    mutationFn: (payload: Parameters<typeof settingsApi.updateModelConfig>[0]) =>
      settingsApi.updateModelConfig(payload),
    onSuccess: (newDto: ModelConfigDTO) => {
      toast.success('已保存，下次 LLM 调用生效');
      setEncryptionBanner(false);
      qc.setQueryData(['settings', 'model-config'], newDto);
      // 重置 api_key_dirty + input
      setProvidersState((prev) => {
        const next: Record<string, ProviderFormState> = {};
        for (const [n, s] of Object.entries(prev)) {
          const fresh = newDto.providers.find((p) => p.name === n);
          next[n] = {
            ...s,
            api_key_input: '',
            api_key_dirty: false,
            api_key_set: fresh?.api_key_set ?? s.api_key_set,
            api_key_masked: fresh?.api_key_masked ?? s.api_key_masked,
          };
        }
        return next;
      });
      setDirty(false);
    },
    onError: (err) => {
      const { code, message } = extractApiError(err);
      if (code === 'encryption_key_missing') {
        setEncryptionBanner(true);
        toast.error('加密密钥未配置，暂无法保存 API key');
      } else {
        toast.error(`保存失败: ${message || code || '未知错误'}`);
      }
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => settingsApi.resetModelConfig(),
    onSuccess: (newDto) => {
      toast.success('已重置为 .env 默认值');
      qc.setQueryData(['settings', 'model-config'], newDto);
    },
  });

  function handleProviderField(name: string, field: keyof ProviderFormState, value: string) {
    setProvidersState((prev) => ({
      ...prev,
      [name]: {
        ...prev[name],
        [field]: value,
        ...(field === 'api_key_input' ? { api_key_dirty: true } : {}),
      },
    }));
    setDirty(true);
  }

  function handleTiers(tier: 'cheap' | 'standard' | 'premium', value: string) {
    setTiersState((prev) => ({ ...prev, [tier]: value }));
    setDirty(true);
  }

  function handleFallback(name: string, checked: boolean) {
    setFallbackState((prev) =>
      checked ? [...prev, name] : prev.filter((x) => x !== name),
    );
    setDirty(true);
  }

  function handleLlmProviders(name: string, checked: boolean) {
    setLlmProvidersState((prev) =>
      checked ? [...prev, name] : prev.filter((x) => x !== name),
    );
    setDirty(true);
  }

  function buildPayload() {
    const providers: ProviderUpdate[] = Object.entries(providersState).map(([name, s]) => {
      const update: ProviderUpdate = { name };
      // 只在用户改过 api_key 字段时才发送 api_key（脏检测语义）
      if (s.api_key_dirty && s.api_key_input !== '') {
        update.api_key = s.api_key_input;
      }
      const original = configQ.data?.providers.find((p) => p.name === name);
      if (original && s.base_url !== original.base_url) update.base_url = s.base_url;
      if (original && s.model !== original.model) update.model = s.model;
      return update;
    });
    return {
      providers,
      tiers: tiersState,
      fallback_chain: fallbackState,
      llm_providers: llmProvidersState,
    };
  }

  if (configQ.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (configQ.error || !configQ.data) {
    return (
      <div className="rounded-lg border border-destructive bg-destructive/10 p-6">
        <h2 className="text-lg font-semibold text-destructive">加载失败</h2>
        <p className="mt-2 text-sm text-muted-foreground">{String(configQ.error)}</p>
      </div>
    );
  }

  const dto = configQ.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">模型配置</h1>
          <p className="text-sm text-muted-foreground">
            编辑各 provider 的 API key / base_url / 模型名、三档 tier、fallback chain 与默认 provider 顺序。
          </p>
        </div>
        <div className="flex items-center gap-2">
          {dto.source === 'json' ? (
            <Badge variant="warning" dot>JSON 覆盖</Badge>
          ) : (
            <Badge variant="outline" dot>环境变量</Badge>
          )}
        </div>
      </div>

      {encryptionBanner && (
        <div className="rounded-lg border border-warning bg-warning/10 p-4 text-sm">
          <strong className="text-warning-foreground">加密密钥未配置</strong>
          <p className="mt-1 text-muted-foreground">
            暂无法保存 API key；其它字段可保存。请先在 .env 设置 ENCRYPTION_KEY。
          </p>
        </div>
      )}

      {dto.providers.map((p) => {
        const state = providersState[p.name];
        if (!state) return null;
        return (
          <Card key={p.name} data-testid={`provider-card-${p.name}`}>
            <CardHeader>
              <CardTitle>{PROVIDER_DISPLAY[p.name] ?? p.name}</CardTitle>
              <CardDescription>provider 名: {p.name}</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor={`${p.name}-base-url`}>Base URL</Label>
                <Input
                  id={`${p.name}-base-url`}
                  value={state.base_url}
                  onChange={(e) => handleProviderField(p.name, 'base_url', e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor={`${p.name}-model`}>模型名</Label>
                <Input
                  id={`${p.name}-model`}
                  value={state.model}
                  onChange={(e) => handleProviderField(p.name, 'model', e.target.value)}
                />
              </div>
              <div className="space-y-1 md:col-span-2">
                <Label htmlFor={`${p.name}-api-key`}>API Key</Label>
                <Input
                  id={`${p.name}-api-key`}
                  type="password"
                  autoComplete="off"
                  placeholder={
                    state.api_key_set
                      ? state.api_key_masked || 'sk-***'
                      : '尚未设置'
                  }
                  value={state.api_key_input}
                  onChange={(e) => handleProviderField(p.name, 'api_key_input', e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  留空表示保留当前 key；填写新值将覆盖。
                </p>
              </div>
            </CardContent>
          </Card>
        );
      })}

      <Card>
        <CardHeader>
          <CardTitle>三档模型选择</CardTitle>
          <CardDescription>cheap = 轻量任务；standard = 默认；premium = 复杂任务</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {(['cheap', 'standard', 'premium'] as const).map((tier) => (
            <div key={tier} className="space-y-1">
              <Label htmlFor={`tier-${tier}`}>{tier}</Label>
              <select
                id={`tier-${tier}`}
                value={tiersState[tier]}
                onChange={(e) => handleTiers(tier, e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
              >
                {dto.providers.map((p) => (
                  <option key={p.name} value={p.name}>{p.name}</option>
                ))}
              </select>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Fallback Chain</CardTitle>
          <CardDescription>主 provider 失败时按顺序切下一个</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {dto.providers.map((p) => (
              <label key={p.name} className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={fallbackState.includes(p.name)}
                  onChange={(e) => handleFallback(p.name, e.target.checked)}
                />
                {p.name}
              </label>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>默认 Provider 列表</CardTitle>
          <CardDescription>用于 llm_providers 字段，控制 enabled 顺序</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {dto.providers.map((p) => (
              <label key={p.name} className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={llmProvidersState.includes(p.name)}
                  onChange={(e) => handleLlmProviders(p.name, e.target.checked)}
                />
                {p.name}
              </label>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-end gap-3">
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline" disabled={resetMutation.isPending}>
              重置为 .env 默认值
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>确认重置配置？</DialogTitle>
              <DialogDescription>
                将删除 <code>data/model_config.json</code>，所有运行时改动丢失，重启后端后回到纯 .env 配置。
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="ghost">取消</Button>
              </DialogClose>
              <Button
                variant="destructive"
                disabled={resetMutation.isPending}
                onClick={() => resetMutation.mutate()}
              >
                {resetMutation.isPending ? '重置中…' : '确认重置'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Button
          disabled={!dirty || saveMutation.isPending}
          onClick={() => saveMutation.mutate(buildPayload())}
        >
          {saveMutation.isPending ? '保存中…' : '保存'}
        </Button>
      </div>
    </div>
  );
}