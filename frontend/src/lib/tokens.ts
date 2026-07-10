/**
 * Design tokens — single source of truth for the v0.6 design system.
 *
 * These literals are mirrored into:
 *   1. CSS variables in src/index.css (`:root { --color-primary: ... }`)
 *   2. Tailwind config theme.extend (so `bg-primary`, `text-fg-muted`, etc. work)
 *
 * Keep this file in sync with both; the unit test guards against accidental drift.
 */

export const tokens = {
  color: {
    // Brand
    primary: '#0D9488', // teal-600
    primary50: '#F0FDFA',
    primary100: '#CCFBF1',
    primaryFg: '#FFFFFF',
    secondary: '#14B8A6',

    // CTA / accent
    accent: '#EA580C', // orange-600
    accentFg: '#FFFFFF',

    // Status
    success: '#10B981',
    warning: '#F59E0B',
    danger: '#DC2626',
    info: '#0EA5E9',

    // Surface
    bg: '#FFFFFF',
    bgSubtle: '#F8FAFC',
    bgStage: '#ECFEFF',

    // Text
    fg: '#0F172A',
    fgMuted: '#475569',
    fgDim: '#94A3B8',

    // Border / focus
    border: '#E2E8F0',
    borderStrong: '#CBD5E1',
    ring: '#0D9488',
  },
  font: {
    sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
    mono: ['JetBrains Mono', 'Consolas', 'monospace'],
  },
  radius: {
    sm: '6px',
    md: '10px',
    lg: '16px',
    pill: '9999px',
  },
  shadow: {
    card: '0 1px 3px rgba(15,23,42,0.06), 0 4px 12px rgba(15,23,42,0.04)',
    popover: '0 8px 32px rgba(15,23,42,0.12)',
    focus: '0 0 0 3px rgba(13,148,136,0.35)',
  },
} as const;

export type Tokens = typeof tokens;
