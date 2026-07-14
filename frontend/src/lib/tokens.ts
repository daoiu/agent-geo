/**
 * Design tokens — single source of truth for the v0.7 HarmonyOS design system.
 *
 * Two views on the same data:
 *   1. Default-shape export `tokens` (object)  — kept for backward compat with
 *      v0.6 call sites that reach into `tokens.color.*` / `tokens.font.*`.
 *      Field names are preserved; only the values have migrated to HarmonyOS.
 *   2. Named exports `colors` / `radius` / `shadow` / `motion` / `breakpoints` /
 *      `fontFamily` — preferred for v0.7+ new code. Mirrors spec §4.
 *
 * These literals must stay in sync with:
 *   - CSS variables in src/index.css (`:root { --primary: #0A59F7; ... }`)
 *   - Tailwind config theme.extend (so `bg-primary`, `rounded-lg`, etc. work)
 *
 * The unit test (`tokens.test.ts`) guards against accidental drift between
 * the three layers.
 */

export const colors = {
  primary: '#0A59F7',
  primaryLight: '#2675F8',
  primaryTint: '#E8F0FE',
  accent: '#A8B0FF',
  success: '#34D77F',
  warning: '#FF7A45',
  danger: '#E54552',
  bgBase: '#F1F3F5',
  bgCard: '#FFFFFF',
  bgCardBlur: 'rgba(255,255,255,0.7)',
  bgDark: '#000000',
  bgCardDark: '#1A1A1F',
  textPrimaryLight: '#1A1A1F',
  textPrimaryDark: '#F1F3F5',
  textSecondary: '#6B7280',
} as const;

export const radius = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, '2xl': 32 } as const;

export const shadow = {
  card: '0 2px 12px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)',
  popover: '0 8px 32px rgba(0,0,0,0.12)',
  floating: '0 16px 48px rgba(0,0,0,0.16)',
} as const;

export const motion = {
  springGentle: { duration: 400, easing: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)' },
  springBounce: { duration: 600, easing: 'cubic-bezier(0.34, 1.56, 0.64, 1)' },
  springExit: { duration: 300, easing: 'cubic-bezier(0.4, 0, 0.6, 1)' },
} as const;

export const breakpoints = { xs: 640, sm: 1024, md: 1280, lg: 1536, xl: 1920 } as const;

export const fontFamily =
  'HarmonyOS Sans, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif';

/**
 * Backward-compatible named tokens. Field names preserved from v0.6; values
 * migrated to HarmonyOS. Existing callers (`tokens.color.primary`,
 * `tokens.font.sans[0]`, etc.) keep compiling with the same shape.
 */
export const tokens = {
  color: {
    primary: colors.primary,
    primaryLight: colors.primaryLight,
    primary50: colors.primaryTint, // alias used by some v0.6 utility classes
    primary100: colors.primaryTint,
    primaryFg: '#FFFFFF',
    secondary: colors.primaryLight,
    accent: colors.accent,
    accentFg: '#FFFFFF',
    success: colors.success,
    warning: colors.warning,
    danger: colors.danger,
    info: colors.primaryLight,
    bg: colors.bgCard,
    bgSubtle: colors.bgBase,
    bgStage: colors.primaryTint,
    fg: colors.textPrimaryLight,
    fgMuted: colors.textSecondary,
    fgDim: '#9CA3AF',
    border: '#E5E7EB',
    borderStrong: '#D1D5DB',
    ring: colors.primary,
  },
  font: {
    sans: [
      'HarmonyOS Sans',
      '-apple-system',
      'PingFang SC',
      'Microsoft YaHei',
      'sans-serif',
    ] as string[],
    mono: ['JetBrains Mono', 'Consolas', 'monospace'] as string[],
  },
  radius: {
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '24px',
    pill: '9999px',
  },
  shadow: {
    card: shadow.card,
    popover: shadow.popover,
    focus: `0 0 0 3px ${colors.primary}59`, // ~35% alpha
  },
} as const;

export type Tokens = typeof tokens;
export type Colors = typeof colors;
export type Radius = typeof radius;
export type Shadow = typeof shadow;
export type Motion = typeof motion;
export type Breakpoints = typeof breakpoints;
