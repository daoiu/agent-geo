import { tokens } from './src/lib/tokens';

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: tokens.color.primary,
        'primary-fg': tokens.color.primaryFg,
        secondary: tokens.color.secondary,
        accent: tokens.color.accent,
        'accent-fg': tokens.color.accentFg,
        success: tokens.color.success,
        warning: tokens.color.warning,
        danger: tokens.color.danger,
        info: tokens.color.info,
        bg: tokens.color.bg,
        'bg-subtle': tokens.color.bgSubtle,
        'bg-stage': tokens.color.bgStage,
        fg: tokens.color.fg,
        'fg-muted': tokens.color.fgMuted,
        'fg-dim': tokens.color.fgDim,
        border: tokens.color.border,
        'border-strong': tokens.color.borderStrong,
        ring: tokens.color.ring,
      },
      fontFamily: {
        sans: tokens.font.sans,
        mono: tokens.font.mono,
      },
      borderRadius: {
        sm: tokens.radius.sm,
        md: tokens.radius.md,
        lg: tokens.radius.lg,
        pill: tokens.radius.pill,
      },
      boxShadow: {
        card: tokens.shadow.card,
        popover: tokens.shadow.popover,
      },
    },
  },
  plugins: [],
};
