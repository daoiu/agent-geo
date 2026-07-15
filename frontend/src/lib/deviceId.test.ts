import { describe, it, expect, beforeEach, vi } from 'vitest';
import { getDeviceId, _resetDeviceIdForTest } from './deviceId';

describe('deviceId', () => {
  beforeEach(() => {
    _resetDeviceIdForTest();
  });

  it('generates a v4 UUID and persists to localStorage when empty', () => {
    const id = getDeviceId();
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
    expect(window.localStorage.getItem('geo.deviceId')).toBe(id);
  });

  it('returns the persisted value without re-generating', () => {
    const preset = '11111111-2222-4333-8444-555555555555';
    window.localStorage.setItem('geo.deviceId', preset);
    const randomSpy = vi.spyOn(crypto, 'randomUUID');
    expect(getDeviceId()).toBe(preset);
    expect(randomSpy).not.toHaveBeenCalled();
  });

  it('returns the cached value across multiple calls (single read cycle)', () => {
    const id1 = getDeviceId();
    const id2 = getDeviceId();
    expect(id1).toBe(id2);
  });

  it('returns empty string when window is undefined (SSR safety)', () => {
    const originalWindow = globalThis.window;
    // The type assertions below make the `@ts-expect-error` directives
    // unnecessary on the current TypeScript config; if a stricter tsconfig
    // re-enables them, just uncomment the directives.
    delete (globalThis as { window?: Window }).window;
    try {
      const id = getDeviceId();
      expect(id).toBe('');
    } finally {
      globalThis.window = originalWindow;
    }
  });
});
