import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'langgraph_enabled';

/**
 * useLangGraphMode — tells the SSE parser and `useAgentStream` whether
 * to consume the new LangGraph schema (10 events including
 * `handoff` / `memory_injected` / `truncation_decision`) or stick with
 * the legacy react_loop schema.
 *
 * State persists in localStorage so the choice survives a reload and
 * survives the TopBar dev-only toggle (Task 11 wires the toggle
 * itself). Production builds never read this hook — the flag is also
 * baked at compile time from `import.meta.env.VITE_LANGGRAPH_ENABLED`
 * in `api/agent.ts`.
 */
export function useLangGraphMode(): {
  enabled: boolean;
  toggle: () => void;
  set: (v: boolean) => void;
} {
  const [enabled, setEnabled] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(STORAGE_KEY) === 'true';
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(STORAGE_KEY, String(enabled));
  }, [enabled]);

  const toggle = useCallback(() => setEnabled((v) => !v), []);
  const set = useCallback((v: boolean) => setEnabled(v), []);
  return { enabled, toggle, set };
}
