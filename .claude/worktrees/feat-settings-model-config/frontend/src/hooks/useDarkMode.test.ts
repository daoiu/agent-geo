import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useDarkMode } from './useDarkMode';

describe('useDarkMode', () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  afterEach(() => {
    window.localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  it('toggles the html.dark class and persists to localStorage', () => {
    const { result } = renderHook(() => useDarkMode());
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(window.localStorage.getItem('geo.theme')).toBe('light');

    act(() => {
      result.current.toggle();
    });

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(window.localStorage.getItem('geo.theme')).toBe('dark');

    act(() => {
      result.current.toggle();
    });

    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(window.localStorage.getItem('geo.theme')).toBe('light');
  });

  it('reads initial value from localStorage', () => {
    window.localStorage.setItem('geo.theme', 'dark');
    const { result } = renderHook(() => useDarkMode());
    expect(result.current.theme).toBe('dark');
  });
});
