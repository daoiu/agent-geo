/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // shadcn compat — preserved for opacity modifiers (`bg-primary/50`)
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

        // v0.6 brand aliases (still used by some flow/page classes)
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

        // v0.7 HarmonyOS — explicit hex aliases for components that want a
        // direct color reference (no opacity, no theme-via-CSS-var indirection).
        success: 'hsl(var(--brand-success))',
        warning: 'hsl(var(--brand-warning))',
        danger: 'hsl(var(--brand-danger))',
      },
      borderRadius: {
        xs: '4px',
        sm: '8px',
        md: '12px',
        lg: '16px',
        xl: '24px',
        '2xl': '32px',
        // shadcn compat kept
        pill: '9999px',
      },
      fontFamily: {
        sans: [
          '"HarmonyOS Sans"',
          '-apple-system',
          'PingFang SC',
          'Microsoft YaHei',
          'sans-serif',
        ],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      boxShadow: {
        card: '0 2px 12px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)',
        popover: '0 8px 32px rgba(0,0,0,0.12)',
        floating: '0 16px 48px rgba(0,0,0,0.16)',
      },
      transitionTimingFunction: {
        'spring-gentle': 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
        'spring-bounce': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
        'spring-exit': 'cubic-bezier(0.4, 0, 0.6, 1)',
      },
      screens: {
        xs: '640px',
        sm: '1024px',
        md: '1280px',
        lg: '1536px',
        xl: '1920px',
      },
    },
  },
  plugins: [],
};
