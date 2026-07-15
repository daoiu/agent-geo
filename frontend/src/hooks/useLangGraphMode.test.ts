import { describe, it, expect, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useLangGraphMode } from './useLangGraphMode';

describe('useLangGraphMode', () => {
  beforeEach(() => {
    // Wipe any prior localStorage entry between tests so the initial
    // value is deterministic regardless of test order.
    window.localStorage.clear();
  });

  it('defaults to false when no persisted value exists', () => {
    const { result } = renderHook(() => useLangGraphMode());
    expect(result.current.enabled).toBe(false);
  });

  it('toggle() flips and persists the value', () => {
    const { result } = renderHook(() => useLangGraphMode());
    expect(result.current.enabled).toBe(false);
    act(() => result.current.toggle());
    expect(result.current.enabled).toBe(true);
    expect(window.localStorage.getItem('langgraph_enabled')).toBe('true');
    act(() => result.current.toggle());
    expect(result.current.enabled).toBe(false);
    expect(window.localStorage.getItem('langgraph_enabled')).toBe('false');
  });

  it('hydrates from a previously persisted "true" value', () => {
    window.localStorage.setItem('langgraph_enabled', 'true');
    const { result } = renderHook(() => useLangGraphMode());
    expect(result.current.enabled).toBe(true);
  });
});
