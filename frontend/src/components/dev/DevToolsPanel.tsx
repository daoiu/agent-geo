import { useEffect, useState } from 'react';
import type { FaultConfig } from '@/types/v0.7';

/**
 * v0.7 DevToolsPanel — dev-only fault injector (P2 #31).  Lets engineers
 * simulate LLM timeouts, tool errors, network 503s, rate-limits and
 * partial SSE streams without standing up the broken code path.
 *
 * Persists the choice in `localStorage` under `fault_config` so any new
 * requests pick it up.  Backend hooks read this at call time and apply
 * the configured fault.
 *
 * **Red line (spec §4 + Global Constraint):** this module is loaded
 * exclusively via a `import.meta.env.DEV` guard at the mount site
 * (Settings.tsx). The production bundle must not contain a reference
 * to this component; CI checks `vite build` output for `DevTools`.
 */

const KINDS: Array<{ value: FaultConfig['kind']; label: string }> = [
  { value: 'llm_timeout', label: 'LLM 超时' },
  { value: 'tool_error', label: '工具错误' },
  { value: 'network_503', label: '网络 503' },
  { value: 'rate_limit', label: '限流' },
  { value: 'partial_stream', label: '部分流' },
];

const STORAGE_KEY = 'fault_config';

const EMPTY: FaultConfig = { kind: 'llm_timeout', target: 'next' };

function loadFault(): FaultConfig {
  if (typeof window === 'undefined') return EMPTY;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY;
    const parsed = JSON.parse(raw) as FaultConfig;
    return { ...EMPTY, ...parsed };
  } catch {
    return EMPTY;
  }
}

export function DevToolsPanel() {
  const [cfg, setCfg] = useState<FaultConfig>(EMPTY);
  useEffect(() => {
    setCfg(loadFault());
  }, []);

  function update(patch: Partial<FaultConfig>) {
    const next: FaultConfig = { ...cfg, ...patch };
    setCfg(next);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    }
  }

  return (
    <section
      aria-label="DevTools"
      className="flex flex-col gap-3 rounded-xl border border-dashed border-warning/40 bg-warning/5 p-4 text-sm"
      data-testid="dev-tools-panel"
    >
      <header>
        <h2 className="text-sm font-semibold text-fg">DevTools — FaultInjector</h2>
        <p className="text-xs text-fg-muted">
          dev 模式可见。后端会读取此处配置并按需应用。
        </p>
      </header>

      <fieldset className="flex flex-wrap gap-3">
        <legend className="sr-only">故障类型</legend>
        {KINDS.map((k) => (
          <label key={k.value} className="inline-flex items-center gap-1.5">
            <input
              type="radio"
              name="fault-kind"
              value={k.value}
              checked={cfg.kind === k.value}
              onChange={() => update({ kind: k.value })}
            />
            <span>{k.label}</span>
          </label>
        ))}
      </fieldset>

      <fieldset className="flex items-center gap-3">
        <legend className="sr-only">触发目标</legend>
        <label className="inline-flex items-center gap-1.5">
          <input
            type="radio"
            name="fault-target"
            value="next"
            checked={cfg.target === 'next'}
            onChange={() => update({ target: 'next' })}
          />
          仅下一次
        </label>
        <label className="inline-flex items-center gap-1.5">
          <input
            type="radio"
            name="fault-target"
            value="600"
            checked={
              typeof cfg.target === 'object' && cfg.target.durationSec === 600
            }
            onChange={() => update({ target: { durationSec: 600 } })}
          />
          10 分钟
        </label>
      </fieldset>

      <p className="text-xs text-fg-muted">
        当前配置: <code className="rounded bg-bg-subtle px-1 py-0.5">{JSON.stringify(cfg)}</code>
      </p>
    </section>
  );
}
