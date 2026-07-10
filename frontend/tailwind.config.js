/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },

        // v0.6 brand aliases (continued support for the few legacy classes
        // that may still reference `bg-primary`, `text-fg`, etc. before
        // pages are fully rewritten)
        'brand-primary': 'hsl(var(--brand-primary))',
        'brand-primary-fg': 'hsl(var(--brand-primary-fg))',
        'brand-accent': 'hsl(var(--brand-accent))',
        'brand-accent-fg': 'hsl(var(--brand-accent-fg))',
        'brand-success': 'hsl(var(--brand-success))',
        'brand-warning': 'hsl(var(--brand-warning))',
        'brand-danger': 'hsl(var(--brand-danger))',
        'brand-info': 'hsl(var(--brand-info))',
        'brand-bg': 'hsl(var(--brand-bg))',
        'brand-bg-subtle': 'hsl(var(--brand-bg-subtle))',
        'brand-bg-stage': 'hsl(var(--brand-bg-stage))',
        'brand-fg': 'hsl(var(--brand-fg))',
        'brand-fg-muted': 'hsl(var(--brand-fg-muted))',
        'brand-fg-dim': 'hsl(var(--brand-fg-dim))',
        'brand-border': 'hsl(var(--brand-border))',
        'brand-border-strong': 'hsl(var(--brand-border-strong))',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 3px rgba(15,23,42,0.06), 0 4px 12px rgba(15,23,42,0.04)',
        popover: '0 8px 32px rgba(15,23,42,0.12)',
      },
    },
  },
  plugins: [],
};
