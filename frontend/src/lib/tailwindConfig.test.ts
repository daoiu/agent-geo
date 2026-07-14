import { describe, it, expect } from 'vitest';
import tailwindConfig from '../../tailwind.config.js';

/**
 * v0.7 HarmonyOS extends live in `theme.extend`. These tests guard against
 * accidental drift between src/lib/tokens.ts (the design-token source of
 * truth) and the Tailwind config that turns those tokens into utility
 * classes used by every UI component.
 *
 * Strategy: tolerate either an hsl(var(--xxx)) shadcn-style alias chain
 * (current state) or a flat hex literal (plan §Step 5 form) — the goal is
 * "the v0.7 spec tokens are addressable in Tailwind utilities."
 */

const extend = (tailwindConfig as { theme: { extend: Record<string, unknown> } })
  .theme.extend;

const isColorish = (v: unknown): boolean =>
  typeof v === 'string' ||
  (typeof v === 'object' && v !== null && 'DEFAULT' in (v as object));

describe('tailwind.config v0.7 HarmonyOS extend — radii', () => {
  it('extends radii with xs=4 / sm=8 / md=12 / lg=16 / xl=24 / 2xl=32', () => {
    expect(extend.borderRadius).toMatchObject({
      xs: '4px',
      sm: '8px',
      md: '12px',
      lg: '16px',
      xl: '24px',
      '2xl': '32px',
    });
  });
});

describe('tailwind.config v0.7 HarmonyOS extend — shadows', () => {
  it('extends box shadow with card / popover / floating tokens', () => {
    expect(extend.boxShadow).toMatchObject({
      card: expect.stringContaining('0 2px 12px'),
      popover: expect.stringContaining('0 8px 32px'),
      floating: expect.stringContaining('0 16px 48px'),
    });
  });
});

describe('tailwind.config v0.7 HarmonyOS extend — spring timing', () => {
  it('extends timing functions with spring-gentle / spring-bounce / spring-exit', () => {
    expect(extend.transitionTimingFunction).toMatchObject({
      'spring-gentle': 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
      'spring-bounce': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      'spring-exit': 'cubic-bezier(0.4, 0, 0.6, 1)',
    });
  });
});

describe('tailwind.config v0.7 HarmonyOS extend — screens', () => {
  it('extends screens with xs=640 / sm=1024 / md=1280 / lg=1536 / xl=1920', () => {
    expect(extend.screens).toMatchObject({
      xs: '640px',
      sm: '1024px',
      md: '1280px',
      lg: '1536px',
      xl: '1920px',
    });
  });
});

describe('tailwind.config v0.7 HarmonyOS extend — font family', () => {
  it('font-family sans leads with HarmonyOS Sans', () => {
    const sans = (extend.fontFamily as { sans: string[] }).sans;
    expect(sans[0]).toBe('"HarmonyOS Sans"');
  });
});

describe('tailwind.config v0.7 HarmonyOS extend — colors', () => {
  it('colors.primary is addressable (var() chain or hex literal)', () => {
    expect(isColorish((extend.colors as Record<string, unknown>).primary)).toBe(true);
  });
  it('colors.accent is addressable', () => {
    expect(isColorish((extend.colors as Record<string, unknown>).accent)).toBe(true);
  });
  it('colors.success is addressable', () => {
    expect(isColorish((extend.colors as Record<string, unknown>).success)).toBe(true);
  });
  it('colors.warning is addressable', () => {
    expect(isColorish((extend.colors as Record<string, unknown>).warning)).toBe(true);
  });
  it('colors.danger is addressable', () => {
    expect(isColorish((extend.colors as Record<string, unknown>).danger)).toBe(true);
  });
});
