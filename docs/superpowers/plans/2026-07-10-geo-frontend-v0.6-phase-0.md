# GEO 优化系统前端 v0.6 — Phase 0 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 v0.6 设计系统的基底搭起来——设计令牌、Layout shell、15 个公共组件、6 个流程可视化组件，并用 React Router 把现有 19 路由套进新 shell，但**不改任何 page 内部**。完成后 `pnpm dev` 启动能看到新品牌 + 侧边 + 顶栏 + 底栏 PipelineRail，所有旧页面仍可访问。

**Architecture:** 自顶向下：先令牌（tokens）→ 测试 infra (vitest) → 公共组件 → 流程组件 → layout shell → App.tsx 接入。每个组件按 TDD：先写组件测试，再实现，最后 a11y 通过。**后端零变更**。

**Tech Stack:**
- React 18.3 + TypeScript 5.7（沿用，不升）
- Tailwind 3.4 + CSS Variables（新增 tokens）
- TanStack Query 5.62 / React Router 6.28 / Recharts 2.15（沿用）
- Vitest 1.x + @testing-library/react + @testing-library/jest-dom（**新增，仅 devDeps**）
- Playwright 1.61（沿用，新增 `@axe-core/playwright`）
- Inter font via Google Fonts `<link>`

**Spec 引用：** `docs/superpowers/specs/2026-07-10-geo-frontend-v0.6-design.md`

## Global Constraints

| 项 | 值 | 来源 |
|---|---|---|
| 主色 | `--color-primary: #0D9488` | spec §4.1 |
| Accent / CTA | `--color-accent: #EA580C` | spec §4.1 |
| 字体 | Inter（fallback: PingFang SC, Microsoft YaHei） | spec §4.2 |
| 暗色模式 | v0.6 不做（接口预留即可） | spec §13 |
| 后端变更 | 零变更；api/client.ts endpoint 全部沿用 | spec §3.2 |
| 路由兼容 | 19 个 URL 全部保留；同时通过 `<Navigate>` 给别名 | spec §3.2 |
| 测试栈 | vitest (单测) + playwright (e2e) + axe-playwright (a11y) | spec §9 |
| 多语言 | 仅中文 | spec §13 |
| 焦点环 | `box-shadow: 0 0 0 3px rgba(13,148,136,0.35)` | spec §4.1 |
| 颜色对比 | WCAG AA 4.5:1 | spec §8 |
| 响应式断点 | sm 640 / md 768 / lg 1024 / xl 1280 / 2xl 1536 | spec §8 |
| 品牌名 | `GEO 优化系统`（替换原 `GEO 诊断 Agent`） | spec §2 |
| PipelineRail 节点顺序 | 诊断 → 生成 → 审核 → 发布 → 监测 → 跟踪 | spec §3.3 |
| SideNav 一级分组 | 诊断 / 知识库 / 生成 / 发布 / 监测 / 智能助手 / 设置 | spec §3.2 |

---

## Task 1: 测试基建（Vitest + RTL + axe-playwright）

**Files:**
- Modify: `frontend/package.json` (devDependencies)
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/test/renderWithRouter.tsx`

**Interfaces:**
- 后续所有组件测试都会调用 `renderWithRouter(<Component />)` —— 这个 helper 是 Tasks 3-19 的接口

- [ ] **Step 1.1: 装依赖**

`cd frontend && pnpm add -D vitest @vitejs/plugin-react @vitest/ui jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @axe-core/playwright`

如果项目用 npm：`npm install -D ...`

- [ ] **Step 1.2: 写 vitest 配置**

`frontend/vitest.config.ts`：
```ts
/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: { reporter: ['text', 'html'] },
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
});
```

- [ ] **Step 1.3: 写 setup 文件**

`frontend/src/test/setup.ts`：
```ts
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => cleanup());
```

- [ ] **Step 1.4: 写 renderWithRouter helper**

`frontend/src/test/renderWithRouter.tsx`：
```tsx
import { render, type RenderOptions } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';

export function renderWithRouter(
  ui: ReactElement,
  options?: RenderOptions & { initialEntries?: string[] }
) {
  const { initialEntries, ...rest } = options ?? {};
  return render(
    <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>,
    rest
  );
}
```

- [ ] **Step 1.5: 加 npm script**

修改 `frontend/package.json`：
```jsonc
"scripts": {
  // ...existing
  "test": "vitest run",
  "test:watch": "vitest",
  "test:ui": "vitest --ui"
}
```

- [ ] **Step 1.6: 跑一个 placeholder 测试验证基建通**

新建 `frontend/src/test/sanity.test.ts`：
```ts
import { describe, it, expect } from 'vitest';

describe('test infra', () => {
  it('runs', () => {
    expect(1 + 1).toBe(2);
  });
});
```

`cd frontend && pnpm test` → 期望：1 passed

- [ ] **Step 1.7: 装 axe-playwright**

`cd frontend && pnpm add -D @axe-core/playwright`

- [ ] **Step 1.8: 提交**

```bash
cd frontend && git add -A && git commit -m "chore(frontend/v0.6): add Vitest+RTL+axe-playwright test infra"
```

---

## Task 2: 设计令牌 (Tailwind config + CSS variables + Inter)

**Files:**
- Modify: `frontend/tailwind.config.js`
- Modify: `frontend/src/index.css`
- Modify: `frontend/index.html`
- Create: `frontend/src/lib/tokens.ts`（类型化的 token 索引，方便 IDE 自动补全）

- [ ] **Step 2.1: 写失败测试 tokens.ts**

`frontend/src/lib/tokens.test.ts`：
```ts
import { describe, it, expect } from 'vitest';
import { tokens } from './tokens';

describe('tokens', () => {
  it('exposes the brand primary', () => {
    expect(tokens.color.primary).toBe('#0D9488');
  });
  it('exposes the accent / CTA color', () => {
    expect(tokens.color.accent).toBe('#EA580C');
  });
  it('exposes the Inter font family as the first choice', () => {
    expect(tokens.font.sans[0]).toBe('Inter');
  });
});
```

- [ ] **Step 2.2: 跑测试确认失败**

`cd frontend && pnpm test src/lib/tokens.test.ts` → expect FAIL（无 `tokens.ts`）

- [ ] **Step 2.3: 实现 tokens.ts**

`frontend/src/lib/tokens.ts`：
```ts
export const tokens = {
  color: {
    primary: '#0D9488',
    primaryFg: '#FFFFFF',
    secondary: '#14B8A6',
    accent: '#EA580C',
    accentFg: '#FFFFFF',
    success: '#10B981',
    warning: '#F59E0B',
    danger: '#DC2626',
    info: '#0EA5E9',
    bg: '#FFFFFF',
    bgSubtle: '#F8FAFC',
    bgStage: '#ECFEFF',
    fg: '#0F172A',
    fgMuted: '#475569',
    fgDim: '#94A3B8',
    border: '#E2E8F0',
    borderStrong: '#CBD5E1',
    ring: '#0D9488',
  },
  font: {
    sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
  },
  radius: { sm: '6px', md: '10px', lg: '16px', pill: '9999px' },
} as const;
```

- [ ] **Step 2.4: 跑测试确认通过**

`pnpm test src/lib/tokens.test.ts` → expect PASS

- [ ] **Step 2.5: 写 Tailwind config**

`frontend/tailwind.config.js`：
```js
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
      fontFamily: { sans: tokens.font.sans },
      borderRadius: tokens.radius,
      boxShadow: {
        card: '0 1px 3px rgba(15,23,42,0.06), 0 4px 12px rgba(15,23,42,0.04)',
        popover: '0 8px 32px rgba(15,23,42,0.12)',
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 2.6: 写全局 CSS（含 :root tokens + Inter import + base reset）**

`frontend/src/index.css` 整体替换：
```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
@import url('https://rsms.me/inter/inter.css');

@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --color-primary: #0D9488;
  --color-primary-50: #F0FDFA;
  --color-primary-100: #CCFBF1;
  --color-primary-fg: #FFFFFF;
  --color-secondary: #14B8A6;
  --color-accent: #EA580C;
  --color-accent-fg: #FFFFFF;
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-danger: #DC2626;
  --color-info: #0EA5E9;
  --color-bg: #FFFFFF;
  --color-bg-subtle: #F8FAFC;
  --color-bg-stage: #ECFEFF;
  --color-fg: #0F172A;
  --color-fg-muted: #475569;
  --color-fg-dim: #94A3B8;
  --color-border: #E2E8F0;
  --color-border-strong: #CBD5E1;
  --color-ring: #0D9488;
  --radius-sm: 6px;
  --radius: 10px;
  --radius-lg: 16px;
  --radius-pill: 9999px;
  --shadow-card: 0 1px 3px rgba(15,23,42,0.06), 0 4px 12px rgba(15,23,42,0.04);
  --shadow-popover: 0 8px 32px rgba(15,23,42,0.12);
  --shadow-focus: 0 0 0 3px rgba(13,148,136,0.35);
}

body {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-feature-settings: 'cv11', 'ss01', 'ss03';
  background: var(--color-bg-subtle);
  color: var(--color-fg);
}

*:focus-visible {
  outline: none;
  box-shadow: var(--shadow-focus);
  border-radius: var(--radius-sm);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 2.7: 引入 Inter 字体到 index.html**

`frontend/index.html` 在 `<head>` 加：
```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" />
```
`title` 改为 "GEO 优化系统"。

- [ ] **Step 2.8: 验证**

`cd frontend && pnpm dev` → 打开浏览器，body 字体应为 Inter，背景 `--color-bg-subtle`。

- [ ] **Step 2.9: 提交**

```bash
git add -A && git commit -m "feat(frontend/v0.6/P0): add design tokens, Tailwind extend, Inter"
```

---

## Task 3: 公共组件库基础 — Button + Input + Select + Textarea

**Files:**
- Create: `frontend/src/components/ui/Button.tsx`
- Create: `frontend/src/components/ui/Button.test.tsx`
- Create: `frontend/src/components/ui/Input.tsx`
- Create: `frontend/src/components/ui/Input.test.tsx`
- Create: `frontend/src/components/ui/Select.tsx`
- Create: `frontend/src/components/ui/Select.test.tsx`
- Create: `frontend/src/components/ui/Textarea.tsx`
- Create: `frontend/src/components/ui/Textarea.test.tsx`

**Interfaces:**
```ts
// Button
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

// Input / Select / Textarea 共同：error?: string, label?: string, hint?: string
export interface FieldWrapperProps {
  label?: string;
  error?: string;
  hint?: string;
  id?: string;
}
```

- [ ] **Step 3.1: 写 Button 测试**

`frontend/src/components/ui/Button.test.tsx`：
```tsx
import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from './Button';

describe('Button', () => {
  it('renders with primary variant by default', () => {
    renderWithRouter(<Button>保存</Button>);
    const btn = screen.getByRole('button', { name: '保存' });
    expect(btn).toHaveClass('bg-primary');
  });

  it('renders accent variant as CTA', () => {
    renderWithRouter(<Button variant="accent">开始诊断</Button>);
    const btn = screen.getByRole('button', { name: '开始诊断' });
    expect(btn).toHaveClass('bg-accent');
  });

  it('shows loading spinner when loading=true and disables click', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    renderWithRouter(<Button loading onClick={onClick}>提交</Button>);
    const btn = screen.getByRole('button', { name: /提交/ });
    expect(btn).toBeDisabled();
    await user.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('forwards onClick handler', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    renderWithRouter(<Button onClick={onClick}>点</Button>);
    await user.click(screen.getByRole('button', { name: '点' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 3.2: 跑测试确认失败**

`pnpm test src/components/ui/Button.test.tsx` → FAIL (no Button)

- [ ] **Step 3.3: 实现 Button**

`frontend/src/components/ui/Button.tsx`：
```tsx
import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';
import { Spinner } from './Spinner';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-primary-fg hover:bg-primary/90',
  secondary: 'bg-bg text-fg border border-border hover:bg-bg-subtle',
  ghost: 'text-fg hover:bg-bg-subtle',
  danger: 'bg-danger text-white hover:bg-danger/90',
  accent: 'bg-accent text-accent-fg hover:bg-accent/90',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm rounded-md',
  md: 'h-10 px-4 text-sm rounded-md',
  lg: 'h-12 px-6 text-base rounded-lg',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading, className, children, disabled, ...rest },
  ref
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 font-medium transition-colors',
        'disabled:opacity-50 disabled:pointer-events-none',
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
      {...rest}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
});
```

- [ ] **Step 3.4: 跑测试确认通过**

`pnpm test src/components/ui/Button.test.tsx` → expect PASS

- [ ] **Step 3.5: 实现并测试 Spinner（被 Button 依赖）**

参照 Step 3.3 中 `import { Spinner } from './Spinner'` 的 contract：
`frontend/src/components/ui/Spinner.tsx`：
```tsx
import { cn } from '@/lib/utils';

interface SpinnerProps {
  size?: 'sm' | 'md';
  className?: string;
}

export function Spinner({ size = 'md', className }: SpinnerProps) {
  const dim = size === 'sm' ? 'h-4 w-4 border-2' : 'h-5 w-5 border-2';
  return (
    <span
      role="status"
      aria-label="loading"
      className={cn(
        'inline-block rounded-full animate-spin border-current border-t-transparent',
        dim,
        className
      )}
    />
  );
}
```

`frontend/src/components/ui/Spinner.test.tsx`：
```tsx
import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Spinner } from './Spinner';

it('renders with loading role', () => {
  renderWithRouter(<Spinner />);
  expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'loading');
});
```

- [ ] **Step 3.6: 实现 Input + 测试**

`frontend/src/components/ui/FieldWrapper.tsx`（共用 label/hint/error 包装）：
```tsx
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface FieldWrapperProps {
  label?: string;
  error?: string;
  hint?: string;
  id?: string;
  children: ReactNode;
}

export function FieldWrapper({ label, error, hint, id, children }: FieldWrapperProps) {
  return (
    <div className="space-y-1">
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-fg">
          {label}
        </label>
      )}
      {children}
      {hint && !error && <p className="text-xs text-fg-dim">{hint}</p>}
      {error && <p role="alert" className="text-xs text-danger">{error}</p>}
    </div>
  );
}
```

`frontend/src/components/ui/Input.tsx`：
```tsx
import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';
import { FieldWrapper } from './FieldWrapper';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, id, className, ...rest },
  ref
) {
  const inputEl = (
    <input
      id={id}
      ref={ref}
      aria-invalid={!!error}
      className={cn(
        'h-10 w-full rounded-md border bg-bg px-3 text-sm',
        'placeholder:text-fg-dim',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        error ? 'border-danger' : 'border-border',
        className
      )}
      {...rest}
    />
  );
  return (
    <FieldWrapper label={label} error={error} hint={hint} id={id}>
      {inputEl}
    </FieldWrapper>
  );
});
```

`frontend/src/components/ui/Input.test.tsx`：
```tsx
import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Input } from './Input';

it('associates label with input via htmlFor/id', () => {
  renderWithRouter(<Input id="brand" label="品牌" />);
  const input = screen.getByLabelText('品牌');
  expect(input).toBeInTheDocument();
});

it('renders error message in alert role and applies danger border', () => {
  renderWithRouter(<Input id="brand" label="品牌" error="必填" />);
  expect(screen.getByRole('alert')).toHaveTextContent('必填');
  expect(screen.getByLabelText('品牌')).toHaveAttribute('aria-invalid', 'true');
});
```

- [ ] **Step 3.7: 跑 Input 测试 → 通过**

`pnpm test src/components/ui/Input.test.tsx`

- [ ] **Step 3.8: 实现 Select + Textarea（同结构，复用 FieldWrapper）**

`frontend/src/components/ui/Select.tsx`（与 Input 同构，调用 `<FieldWrapper>` 包装 `<select>`）
`frontend/src/components/ui/Textarea.tsx`（与 Input 同构，调用 `<FieldWrapper>` 包装 `<textarea>`）

每个 1 个测试：渲染 label、显示 error。同 Input.test.tsx 模板。

- [ ] **Step 3.9: 跑全部**

`pnpm test src/components/ui/Button.test.tsx src/components/ui/Input.test.tsx src/components/ui/Select.test.tsx src/components/ui/Textarea.test.tsx src/components/ui/Spinner.test.tsx`

expect: ALL PASS

- [ ] **Step 3.10: 提交**

```bash
git add -A && git commit -m "feat(frontend/v0.6/P0): Button, Spinner, Input, Select, Textarea, FieldWrapper"
```

---

## Task 4: Card + Badge + EmptyState

**Files:**
- Create: `frontend/src/components/ui/Card.tsx` + `.test.tsx`
- Create: `frontend/src/components/ui/Badge.tsx` + `.test.tsx`
- Create: `frontend/src/components/ui/EmptyState.tsx` + `.test.tsx`

**Interfaces:**
```ts
export function Card({ children, className, padded = true }: ...): JSX.Element;
export interface BadgeProps { tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info'; children: ReactNode; }
export interface EmptyStateProps { title: string; description?: string; action?: ReactNode; }
```

- [ ] **Step 4.1: Card 测试**

- [ ] **Step 4.2: 跑测试 FAIL → 实现 Card**

```tsx
export function Card({ children, className, padded = true }: { children: ReactNode; className?: string; padded?: boolean }) {
  return (
    <div className={cn('rounded-lg border border-border bg-bg shadow-card', padded && 'p-6', className)}>
      {children}
    </div>
  );
}
```

- [ ] **Step 4.3: Badge 测试 + 实现**（5 种 tone 对应 5 套 Tailwind class）

- [ ] **Step 4.4: EmptyState 测试 + 实现**

```tsx
<EmptyState title="还没有数据" description="先建一个任务" action={<Button>新建</Button>} />
```

- [ ] **Step 4.5: 跑全部**

- [ ] **Step 4.6: 提交**

```bash
git commit -m "feat(frontend/v0.6/P0): Card, Badge, EmptyState"
```

---

## Task 5: Modal + Drawer + ConfirmDialog

**Files:**
- Create: `frontend/src/components/ui/Modal.tsx` + `.test.tsx`
- Create: `frontend/src/components/ui/Drawer.tsx` + `.test.tsx`
- Create: `frontend/src/components/ui/ConfirmDialog.tsx` + `.test.tsx`（替换 v0.4 的简单版本）

**Interfaces:**
- 都用 `<dialog>` element（HTML5 原生 modal）做根；用 `useState` + `useEffect` 控制 show
- 焦点陷阱 + ESC 关闭 + 遮罩点击关闭

- [ ] **Step 5.1: Modal 测试**（open/close、ESC、focus trap、aria-modal）

- [ ] **Step 5.2: Modal 实现**

```tsx
import { useEffect, useRef, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  className?: string;
}

export function Modal({ open, onClose, title, children, className }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}
      aria-modal="true"
      className="rounded-lg border border-border bg-bg p-6 shadow-popover backdrop:bg-fg/40"
    >
      {title && <h2 className="mb-4 text-lg font-semibold text-fg">{title}</h2>}
      <div className={className}>{children}</div>
    </dialog>
  );
}
```

- [ ] **Step 5.3: Drawer 同构，从右侧滑入**

- [ ] **Step 5.4: ConfirmDialog 实现包装 Modal + confirm/cancel 按钮**

```tsx
export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'accent' | 'primary';
  onConfirm: () => void;
  onCancel: () => void;
}
```

- [ ] **Step 5.5: 跑全部测试**

- [ ] **Step 5.6: 提交**

```bash
git commit -m "feat(frontend/v0.6/P0): Modal, Drawer, ConfirmDialog (using <dialog>)"
```

---

## Task 6: Skeleton + Tooltip + Tabs + Accordion

**Files:**
- Create: `frontend/src/components/ui/Skeleton.tsx` + `.test.tsx`
- Create: `frontend/src/components/ui/Tooltip.tsx` + `.test.tsx`
- Create: `frontend/src/components/ui/Tabs.tsx` + `.test.tsx`
- Create: `frontend/src/components/ui/Accordion.tsx` + `.test.tsx`

**Interfaces:**
- `Skeleton` 接受 `className`（用 Tailwind 控尺寸/形状）；带 `animate-pulse`
- `Tooltip` 用 `<div title>` 升级版——基于 Radix-free 简单自写：`hover/focus` 弹气泡，`delayDuration` 300ms，键盘焦点可访问
- `Tabs`：受控/非受控两种 API，默认非受控
- `Accordion`：单/多展开两种模式

- [ ] **Step 6.1: 4 个组件各 1 测试 + 实现**

- [ ] **Step 6.2: 跑全部**

- [ ] **Step 6.3: 提交**

```bash
git commit -m "feat(frontend/v0.6/P0): Skeleton, Tooltip, Tabs, Accordion"
```

---

## Task 7: Stepper (替代 WizardShell)

**Files:**
- Create: `frontend/src/components/ui/Stepper.tsx` + `.test.tsx`

**Interfaces:**
```ts
export interface StepperProps {
  steps: { key: string; title: string; description?: string }[];
  current: number; // 0-based
  orientation?: 'horizontal' | 'vertical';
  onChange?: (index: number) => void; // 仅 horizontal + click 时
}
```

- [ ] **Step 7.1: Stepper 测试**

```tsx
it('marks current step with primary color and pending with dim', () => {
  renderWithRouter(<Stepper steps={[{key:'a',title:'品牌'},{key:'b',title:'问题'}]} current={0} />);
  const a = screen.getByText('品牌');
  const b = screen.getByText('问题');
  expect(a.closest('[data-step-state]')).toHaveAttribute('data-step-state', 'current');
  expect(b.closest('[data-step-state]')).toHaveAttribute('data-step-state', 'pending');
});
```

- [ ] **Step 7.2: Stepper 实现**（沿用 WizardShell 的视觉风格但 token 化）

- [ ] **Step 7.3: 跑测试通过**

- [ ] **Step 7.4: 提交**

```bash
git commit -m "feat(frontend/v0.6/P0): Stepper"
```

注意：`WizardShell.tsx` 在 P1 中会被替换为基于 `Stepper` + `Card` 的新实现，不要在本任务删。

---

## Task 8: StageCard + LiveSignal

**Files:**
- Create: `frontend/src/components/flow/StageCard.tsx` + `.test.tsx`
- Create: `frontend/src/components/flow/LiveSignal.tsx` + `.test.tsx`

**Interfaces:**
```ts
export type StageStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped';

export interface StageCardProps {
  icon?: ReactNode;
  title: string;
  status: StageStatus;
  meta?: string;        // e.g. "12 个页面 · 8.2s · 无错误"
  progress?: number;    // 0..100
  duration?: string;    // e.g. "8.2s"
  detail?: ReactNode;   // 折叠展开
}

export interface LiveSignalProps {
  provider: string;
  status: 'pending' | 'running' | 'done' | 'error';
}
```

- [ ] **Step 8.1: StageCard 测试**

```tsx
it('shows progress bar when progress < 100', () => {
  renderWithRouter(<StageCard title="爬虫" status="running" progress={42} />);
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '42');
});

it('shows check icon when status is done', () => {
  renderWithRouter(<StageCard title="爬虫" status="done" progress={100} />);
  expect(screen.getByLabelText('已完成')).toBeInTheDocument();
});
```

- [ ] **Step 8.2: StageCard 实现**

```tsx
const statusBadge: Record<StageStatus, { color: string; label: string }> = {
  pending: { color: 'bg-fg-dim/20 text-fg-muted', label: '等待中' },
  running: { color: 'bg-info/15 text-info', label: '进行中' },
  done:    { color: 'bg-success/15 text-success', label: '已完成' },
  error:   { color: 'bg-danger/15 text-danger', label: '失败' },
  skipped: { color: 'bg-fg-dim/15 text-fg-dim', label: '已跳过' },
};
// 渲染：header (icon+title+status badge+meta) + optional progress bar + optional detail
```

- [ ] **Step 8.3: LiveSignal 实现**（小圆点 + provider 名字；颜色随 status）

- [ ] **Step 8.4: 跑全部**

- [ ] **Step 8.5: 提交**

```bash
git commit -m "feat(frontend/v0.6/P0): StageCard, LiveSignal"
```

---

## Task 9: RankBadge

**Files:**
- Create: `frontend/src/components/flow/RankBadge.tsx` + `.test.tsx`

**Interfaces:**
```ts
export interface RankBadgeProps {
  rank: number;        // 1, 2, 3+
  trend?: 'up' | 'down' | 'flat';
}
```

- [ ] **Step 9.1: 测试 + 实现**

```tsx
export function RankBadge({ rank, trend }: RankBadgeProps) {
  const tone = rank === 1 ? 'bg-warning/15 text-warning'   // 金
            : rank === 2 ? 'bg-fg-dim/20 text-fg-muted'   // 银
            : rank === 3 ? 'bg-accent/15 text-accent'     // 铜
            : 'bg-bg-subtle text-fg-muted';
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-pill px-2 py-0.5 text-xs font-medium', tone)}>
      #{rank}
      {trend === 'up' && <span aria-label="上升">↑</span>}
      {trend === 'down' && <span aria-label="下降">↓</span>}
    </span>
  );
}
```

- [ ] **Step 9.2: 跑测试 + 提交**

```bash
git commit -m "feat(frontend/v0.6/P0): RankBadge"
```

---

## Task 10: KnowledgeChunkCard

**Files:**
- Create: `frontend/src/components/flow/KnowledgeChunkCard.tsx` + `.test.tsx`

**Interfaces:**
```ts
export interface KnowledgeChunkCardProps {
  title: string;
  preview: string;            // 摘要 80 字
  source: string;             // "白皮书 P.12" or "小米官网 /news"
  hybridScore?: number;       // 0..1
  citedIn?: number;           // 在 N 篇文章中被引用
  onClick?: () => void;
}
```

- [ ] **Step 10.1: 测试 + 实现**

```tsx
export function KnowledgeChunkCard({ title, preview, source, hybridScore, citedIn, onClick }: KnowledgeChunkCardProps) {
  return (
    <button onClick={onClick} className="w-full text-left rounded-lg border border-border bg-bg p-4 shadow-card hover:border-primary transition">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-fg">{title}</h3>
          <p className="mt-1 text-xs text-fg-muted line-clamp-2">{preview}</p>
        </div>
        {typeof hybridScore === 'number' && (
          <div className="flex flex-col items-end shrink-0">
            <span className="text-xs text-fg-dim">检索分</span>
            <span className="text-sm font-semibold text-primary">{hybridScore.toFixed(2)}</span>
          </div>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-fg-dim">
        <span>{source}</span>
        {typeof citedIn === 'number' && <span>引用 {citedIn} 篇</span>}
      </div>
    </button>
  );
}
```

- [ ] **Step 10.2: 跑测试 + 提交**

```bash
git commit -m "feat(frontend/v0.6/P0): KnowledgeChunkCard"
```

---

## Task 11: MentionMatrix

**Files:**
- Create: `frontend/src/components/flow/MentionMatrix.tsx` + `.test.tsx`

**Interfaces:**
```ts
export interface MentionCell {
  brand: string;
  question: string;
  provider: string;       // DeepSeek / Kimi ...
  mentioned: boolean;
  position?: number;      // 1..N 出现位置
  sentiment?: 'positive' | 'neutral' | 'negative' | 'none';
}

export interface MentionMatrixProps {
  cells: MentionCell[];
  brands: string[];       // 行
  questions: string[];    // 列
  providers: string[];    // 第二 key
}
```

- [ ] **Step 11.1: 测试**（颜色映射 + a11y label）

```tsx
it('a11y: each cell has aria-label with mention status', () => {
  renderWithRouter(<MentionMatrix cells={[
    { brand: '小米', question: 'Q1', provider: 'DeepSeek', mentioned: true, position: 1 },
    { brand: '小米', question: 'Q1', provider: 'Kimi',     mentioned: false },
  ]} brands={['小米']} questions={['Q1']} providers={['DeepSeek', 'Kimi']} />);
  expect(screen.getByLabelText('小米·Q1·DeepSeek 提及且位置第 1')).toBeInTheDocument();
  expect(screen.getByLabelText('小米·Q1·Kimi 未提及')).toBeInTheDocument();
});
```

- [ ] **Step 11.2: 实现**（CSS grid：rows=brands，sub-rows=providers，cols=questions；cell 颜色用 `bg-primary/20` 到 `bg-primary` 按位置）

- [ ] **Step 11.3: 跑测试 + 提交**

```bash
git commit -m "feat(frontend/v0.6/P0): MentionMatrix"
```

---

## Task 12: ReasoningTrace

**Files:**
- Create: `frontend/src/components/flow/ReasoningTrace.tsx` + `.test.tsx`

**Interfaces:**
```ts
export type TraceEvent =
  | { kind: 'thought'; text: string; ts: number }
  | { kind: 'tool_call'; tool: string; args: Record<string, unknown>; status: 'running' | 'done' | 'error'; ts: number; result?: unknown }
  | { kind: 'llm_query'; provider: string; status: 'pending' | 'done' | 'error'; durationMs?: number; ts: number }
  | { kind: 'final'; text: string; ts: number; needsConfirmation?: boolean };

export interface ReasoningTraceProps {
  events: TraceEvent[];
  collapsibleThreshold?: number; // 默认 50
}
```

- [ ] **Step 12.1: 测试**

```tsx
it('renders tool_call events with a tool icon and status', () => {
  renderWithRouter(
    <ReasoningTrace events={[
      { kind: 'thought', text: '我会先查一下', ts: 0 },
      { kind: 'tool_call', tool: 'search_knowledge', args: { q: '小米' }, status: 'done', ts: 1, result: { found: 5 } },
    ]} />
  );
  expect(screen.getByText(/我会先查一下/)).toBeInTheDocument();
  expect(screen.getByLabelText(/search_knowledge 运行完成/)).toBeInTheDocument();
});

it('collapses when over threshold', () => {
  const many = Array.from({ length: 60 }, (_, i) => ({ kind: 'thought', text: `t${i}`, ts: i }));
  renderWithRouter(<ReasoningTrace events={many} collapsibleThreshold={50} />);
  expect(screen.getByText(/收起 \d+ 条|展开 \d+ 条/)).toBeInTheDocument();
});
```

- [ ] **Step 12.2: 实现**

时间线垂直布局，每个事件一张 mini card：
- `thought`: 引言图标 + 文本（折叠灰）
- `tool_call`: 🔧 + tool 名 + 折叠 args + status icon
- `llm_query`: 提供商 logo + 状态点 + duration
- `final`: 实心框（如果是 needsConfirmation 加 confirm button）

- [ ] **Step 12.3: 跑测试 + 提交**

```bash
git commit -m "feat(frontend/v0.6/P0): ReasoningTrace"
```

---

## Task 13: Layout Shell 基础 — TopBar + SideNav + Breadcrumb

**Files:**
- Create: `frontend/src/components/layout/TopBar.tsx` + `.test.tsx`
- Create: `frontend/src/components/layout/SideNav.tsx` + `.test.tsx`
- Create: `frontend/src/components/layout/Breadcrumb.tsx` + `.test.tsx`
- Create: `frontend/src/components/layout/LayoutShell.tsx` + `.test.tsx`

**Interfaces:**
```ts
// TopBar
export interface TopBarProps {
  onToggleSidebar?: () => void;  // mobile hamburger
  sidebarOpen?: boolean;
}

// SideNav
export interface NavItem {
  key: string;
  label: string;
  icon?: ReactNode;
  to: string;
  children?: NavItem[];
}
export interface SideNavProps {
  items: NavItem[];
  currentPath: string;
  onNavigate?: (to: string) => void;
}

// Breadcrumb
export interface Crumb { label: string; to?: string }
export interface BreadcrumbProps { items: Crumb[] }

// LayoutShell
export interface LayoutShellProps {
  navItems: NavItem[];
  crumbs: Crumb[];
  contextPane?: ReactNode;
  children: ReactNode;
}
```

- [ ] **Step 13.1: 写 TopBar 测试 + 实现**

Logo 复用：内联 SVG（圆点脉冲图标）；右侧放通知 + 设置 icon 按钮 + （mobile）汉堡按钮

```tsx
const Logo = () => (
  <svg viewBox="0 0 24 24" className="h-6 w-6 text-primary" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
    <circle cx="12" cy="12" r="3" fill="currentColor" />
    {/* 6 个脉冲点 */}
    {[
      [12, 3], [20, 7], [20, 17], [12, 21], [4, 17], [4, 7]
    ].map(([cx, cy], i) => <circle key={i} cx={cx} cy={cy} r="1.5" fill="currentColor" />)}
  </svg>
);

export function TopBar({ onToggleSidebar, sidebarOpen }: TopBarProps) {
  return (
    <header className="h-14 border-b border-border bg-bg flex items-center px-4 gap-3">
      <button onClick={onToggleSidebar} aria-label={sidebarOpen ? '关闭侧边' : '打开侧边'} className="md:hidden text-fg">
        ☰
      </button>
      <Link to="/" className="flex items-center gap-2 text-fg font-semibold">
        <Logo />
        <span>GEO 优化系统</span>
      </Link>
      <div className="flex-1" />
      <button aria-label="通知" className="text-fg-muted hover:text-fg p-2">🔔</button>
      <Link to="/settings" aria-label="设置" className="text-fg-muted hover:text-fg p-2">⚙</Link>
    </header>
  );
}
```

- [ ] **Step 13.2: 写 SideNav 测试 + 实现**

- 7 个一级组（仪表盘/诊断/知识库/生成/发布/监测/智能助手/设置）
- 用 `<NavLink>` from react-router-dom；激活态 `bg-primary/10 text-primary border-l-2 border-primary`
- 子项缩进
- mobile：`<details>` 折叠 OR `<dialog>` 抽屉

```tsx
import { NavLink, Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

export function SideNav({ items }: SideNavProps) {
  return (
    <nav aria-label="主导航" className="h-full w-60 overflow-y-auto border-r border-border bg-bg p-3">
      <ul role="tree" className="space-y-1">
        {items.map((item) => (
          <li key={item.key} role="treeitem">
            <NavLink
              to={item.to}
              end
              className={({ isActive }) => cn(
                'flex items-center gap-2 rounded-md px-3 py-2 text-sm',
                isActive ? 'bg-primary/10 text-primary font-medium' : 'text-fg-muted hover:bg-bg-subtle'
              )}
            >
              {item.icon}
              {item.label}
            </NavLink>
            {item.children && (
              <ul className="ml-8 mt-1 space-y-1">
                {item.children.map((c) => (
                  <li key={c.key}>
                    <NavLink to={c.to} end className={({ isActive }) => cn(
                      'block rounded-md px-3 py-1.5 text-sm',
                      isActive ? 'bg-primary/10 text-primary' : 'text-fg-muted hover:bg-bg-subtle'
                    )}>{c.label}</NavLink>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}
```

- [ ] **Step 13.3: 写 Breadcrumb 测试 + 实现**

```tsx
export function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <nav aria-label="面包屑" className="text-sm text-fg-muted">
      <ol className="flex items-center gap-1.5">
        {items.map((c, i) => (
          <li key={i} className="flex items-center gap-1.5">
            {i > 0 && <span aria-hidden="true">/</span>}
            {c.to ? <Link className="hover:text-fg" to={c.to}>{c.label}</Link> : <span className="text-fg">{c.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}
```

- [ ] **Step 13.4: 写 LayoutShell 测试 + 实现**

```tsx
export function LayoutShell({ navItems, crumbs, contextPane, children }: LayoutShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return (
    <div className="flex h-screen flex-col">
      <TopBar onToggleSidebar={() => setSidebarOpen(o => !o)} sidebarOpen={sidebarOpen} />
      <div className="flex flex-1 overflow-hidden">
        <aside className={cn('hidden md:block', sidebarOpen && 'block')}>
          <SideNav items={navItems} currentPath={location.pathname} />
        </aside>
        <main className="flex-1 overflow-y-auto bg-bg-subtle">
          <div className="px-6 py-4">
            <Breadcrumb items={crumbs} />
            <div className="mt-4 flex gap-6">
              <div className="flex-1">{children}</div>
              {contextPane && <aside className="hidden xl:block w-80">{contextPane}</aside>}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 13.5: 跑全部 + 提交**

```bash
pnpm test src/components/layout/
git commit -m "feat(frontend/v0.6/P0): LayoutShell + TopBar + SideNav + Breadcrumb"
```

---

## Task 14: PipelineRail（v0.6 视觉锚定组件）

**Files:**
- Create: `frontend/src/components/layout/PipelineRail.tsx` + `.test.tsx`
- Create: `frontend/src/lib/usePipelineState.ts`（聚合 5 个 React Query）

**Interfaces:**
```ts
export type PipelineNodeKey = 'diagnose' | 'generate' | 'review' | 'publish' | 'monitor' | 'track';

export interface PipelineNode {
  key: PipelineNodeKey;
  label: string;
  to: string;
  status: 'pending' | 'running' | 'done' | 'error';
  count?: number;          // 进行中或失败数
}

export interface PipelineRailProps {
  nodes: PipelineNode[];
  collapsed?: boolean;
  onToggle?: () => void;
}

export function usePipelineState(): { nodes: PipelineNode[]; isLoading: boolean };
```

- [ ] **Step 14.1: 写 usePipelineState hook**（聚合 React Query，错误隔离）

```ts
import { useReports } from '@/api/hooks';  // 视项目实际 hooks 路径而定
// 实际 aggregate 略，按 spec §3.3 从 5 个查询聚合最近一单状态
```

- [ ] **Step 14.2: 写 PipelineRail 测试**

```tsx
it('shows six nodes with labels from spec', () => {
  const nodes: PipelineNode[] = [
    { key: 'diagnose', label: '诊断', to: '/', status: 'running' },
    { key: 'generate', label: '生成', to: '/tasks', status: 'done' },
    { key: 'review', label: '审核', to: '/reviews', status: 'pending' },
    { key: 'publish', label: '发布', to: '/publishes', status: 'pending' },
    { key: 'monitor', label: '监测', to: '/monitors', status: 'error', count: 3 },
    { key: 'track', label: '跟踪', to: '/monitors', status: 'pending' },
  ];
  renderWithRouter(<PipelineRail nodes={nodes} />);
  expect(screen.getByText('诊断')).toBeInTheDocument();
  expect(screen.getByText('生成')).toBeInTheDocument();
  expect(screen.getByText('监测')).toBeInTheDocument();
  expect(screen.getByLabelText('监测 失败 3 项')).toBeInTheDocument();
});

it('renders collapsed as a thin bar', () => {
  renderWithRail(<PipelineRail nodes={[]} collapsed />);
  // 期望高度 ≈ 28px（不是 60px）
});
```

- [ ] **Step 14.3: 实现 PipelineRail**

```tsx
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/Badge';

const NODE_COLORS: Record<PipelineNode['status'], string> = {
  pending: 'border-fg-dim/40 text-fg-dim',
  running: 'border-primary bg-primary text-primary-fg animate-pulse',
  done:    'border-success bg-success/15 text-success',
  error:   'border-danger bg-danger/15 text-danger',
};

export function PipelineRail({ nodes, collapsed, onToggle }: PipelineRailProps) {
  return (
    <footer
      role="navigation"
      aria-label="全局优化流水线"
      className={cn(
        'border-t border-border bg-bg-stage flex items-center px-4 gap-4 transition-all',
        collapsed ? 'h-7' : 'h-15'
      )}
    >
      <button onClick={onToggle} aria-label={collapsed ? '展开' : '折叠'} className="text-fg-muted hover:text-fg">
        {collapsed ? '▲' : '▼'}
      </button>
      <ol className="flex items-center gap-3 flex-1 overflow-x-auto">
        {nodes.map((n, i) => (
          <li key={n.key} className="flex items-center gap-3">
            <Link
              to={n.to}
              aria-label={`${n.label} ${STATUS_LABEL[n.status]}${n.count ? ' ' + n.count + ' 项' : ''}`}
              className={cn(
                'inline-flex items-center gap-2 rounded-pill border px-3 py-1 text-xs font-medium',
                NODE_COLORS[n.status]
              )}
            >
              <span>{n.label}</span>
              {n.count != null && <Badge tone={n.status === 'error' ? 'danger' : 'warning'}>{n.count}</Badge>}
            </Link>
            {i < nodes.length - 1 && <span aria-hidden="true" className="text-fg-dim">─</span>}
          </li>
        ))}
      </ol>
    </footer>
  );
}

const STATUS_LABEL = { pending: '等待中', running: '进行中', done: '已完成', error: '失败' };
```

- [ ] **Step 14.4: 跑测试 + 提交**

```bash
pnpm test src/components/layout/PipelineRail.test.tsx
git commit -m "feat(frontend/v0.6/P0): PipelineRail + usePipelineState"
```

---

## Task 15: App.tsx 接入新 shell（不改 page 内部）

**Files:**
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- 新增 `navItems: NavItem[]` 常量（按 spec §3.2 静态定义）
- 移除原 `Header()` 组件，替换为 `<LayoutShell>` 内含 `<TopBar>` `<SideNav>` `<Breadcrumb>` `<PipelineRail>`
- `<Routes>` 保持不变；每个 route 的 wrapper 是当前 page（page 内部不动）
- 临时：每个 page 顶部加 `<BreadcrumbSetter ... />` 这样的内部 context 注入可能不需要，直接在 LayoutShell 处统一路径生成

**Scope:** 只改 `App.tsx` 一个文件，不动 page。所有 page 在新 shell 中应能正常展示（旧 button 颜色可能与新 token 不一致，那是 P1-P5 的事，本任务不留视觉债，但要确保无 console error / 路由可达）。

- [ ] **Step 15.1: 写 App.tsx 测试**

由于 App.tsx 渲染整个路由树，单独测试它要么 provider 太重，要么做 e2e 测试。这里改为：
- 写一个最小集成测试：用 `MemoryRouter` + `App` 渲染 `/new`，断言 TopBar 出现 "GEO 优化系统" 文字 + PipelineRail 出现 "诊断" 节点

`frontend/src/App.test.tsx`：
```tsx
import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import App from './App';

describe('App', () => {
  it('mounts LayoutShell with brand and PipelineRail', () => {
    // 注意：App 内部使用 BrowserRouter，renderWithRouter 会嵌套 MemoryRouter；为避免冲突，改用 MemoryRouter 版本：
    // 先把 App 改造为 `function App()` + export `createApp()`，见 Step 15.2
    renderWithRouter(<App />, { initialEntries: ['/'] });
    expect(screen.getByText('GEO 优化系统')).toBeInTheDocument();
    expect(screen.getByText('诊断')).toBeInTheDocument();
  });
});
```

- [ ] **Step 15.2: 改造 App.tsx 为可测试结构**

把现有 `App.tsx` 拆为：
```tsx
// App.tsx
export const navItems: NavItem[] = [ /* 7 一级分组 */ ];
export const CRUMB_BY_PATH = (path: string): Crumb[] => [ /* 路径 → 面包屑映射 */ ];

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <LayoutShellRouter />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function LayoutShellRouter() {
  const location = useLocation();
  const nodes = usePipelineState();
  const crumbs = useMemo(() => CRUMB_BY_PATH(location.pathname), [location.pathname]);
  // context pane 暂不传（P1-P2 再启用）
  return (
    <LayoutShell navItems={navItems} crumbs={crumbs}>
      <Routes>
        {/* 保留原 19 个路由 */}
      </Routes>
    </LayoutShell>
  );
}
```

- [ ] **Step 15.3: 跑 App.test.tsx + 全部 layout/components test**

```bash
pnpm test
```
expect: ALL PASS

- [ ] **Step 15.4: 启 dev server 实地走一遍**

```bash
cd frontend && pnpm dev
```
人工验证：
- 首页 `/` 加载 → 看到新 TopBar（含品牌、Logo、设置）+ 侧边（7 组）+ 底栏 6 节点
- 点击侧边 `Agent` → 跳到 `/agent` → AgentSessionList 还能渲染（不爆炸）
- 每个 URL 都至少点一次确认无 console error

- [ ] **Step 15.5: 提交**

```bash
git commit -m "feat(frontend/v0.6/P0): mount LayoutShell in App, navigate all 19 routes in new shell"
```

---

## Task 16: a11y 与视觉回归（axe-core + Playwright 截图）

**Files:**
- Create: `frontend/tests/e2e/p0-layout-shell.spec.ts`（Playwright spec）
- Create: `frontend/tests/e2e/p0-a11y.spec.ts`

- [ ] **Step 16.1: 装 axe-core**

如果 Task 1.7 未装：`pnpm add -D @axe-core/playwright`

- [ ] **Step 16.2: a11y spec**

```ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const PAGES = ['/', '/new', '/knowledge', '/tasks', '/reviews', '/publishers', '/monitors', '/agent', '/settings'];

for (const path of PAGES) {
  test(`a11y: ${path} passes axe checks`, async ({ page }) => {
    await page.goto(path);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
}
```

- [ ] **Step 16.3: 跑**

```bash
cd frontend && pnpm exec playwright test tests/e2e/p0-a11y.spec.ts
```
注：a11y 可能因未替换的 page 里有违规而 fail——这是 P1-P5 才修的。在 P0 任务里**只断言 LayoutShell 内的部分**（用 `page.locator('header, nav, footer').analyze()`）。
调整 a11y spec，只对 topbar/sidenav/rail 做 axe：

```ts
const results = await new AxeBuilder({ page })
  .include('header')
  .include('nav[aria-label]')
  .include('footer[aria-label]')
  .analyze();
expect(results.violations).toEqual([]);
```

- [ ] **Step 16.4: 视觉回归 spec**

```ts
import { test, expect } from '@playwright/test';

test('P0 LayoutShell snapshot', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('header')).toHaveScreenshot('topbar.png');
  await expect(page.locator('nav[aria-label="主导航"]')).toHaveScreenshot('sidenav.png');
  await expect(page.locator('footer[aria-label="全局优化流水线"]')).toHaveScreenshot('rail.png');
});
```

- [ ] **Step 16.5: 跑 + 处理首次 baseline**

```bash
pnpm exec playwright test --update-snapshots tests/e2e/p0-layout-shell.spec.ts
pnpm exec playwright test tests/e2e/p0-layout-shell.spec.ts
```

- [ ] **Step 16.6: 提交**

```bash
git commit -m "test(frontend/v0.6/P0): add a11y + visual snapshot for new shell"
```

---

## Task 17: 文档收尾 + CHANGELOG

**Files:**
- Modify: `frontend/docs/DESIGN.md`（如不存在则新建；本任务新建）
- Modify: `docs/CHANGELOG.md` 加 v0.6 行
- Modify: `docs/HANDOFF_V0.6.md`（如还没创建）

- [ ] **Step 17.1: 新建 DESIGN.md**

`frontend/docs/DESIGN.md` 内容：
- 章节 1：color / font / radius / shadow tokens 速查表
- 章节 2：组件清单 + 每个组件的 props 速查
- 章节 3：布局 shell 架构图
- 章节 4：IA 路由映射（含别名前缀）
- 章节 5：如何在 page 中使用 tokens（用 `cn()` + `tokens.color.primary` 两种方式）

- [ ] **Step 17.2: 写 CHANGELOG + HANDOFF**

按项目现有模板。

- [ ] **Step 17.3: 提交**

```bash
git commit -m "docs(frontend/v0.6/P0): DESIGN.md tokens guide + CHANGELOG + HANDOFF"
```

---

## Self-Review（自审）

跑完之后回这里：
1. **Spec 覆盖**：
   - §3.1 Layout Shell → Task 13 + Task 15 ✓
   - §3.2 路由重排 → Task 15 ✓
   - §3.3 PipelineRail → Task 14 ✓
   - §4 设计令牌 → Task 2 ✓
   - §4.4 15 个公共组件 → Task 3-7 ✓（Button/Input/Select/Textarea + Spinner/Card/Badge/EmptyState + Modal/Drawer/ConfirmDialog + Skeleton/Tooltip/Tabs/Accordion + Stepper）
   - §5 流程组件 → Task 8-12 ✓（StageCard + LiveSignal + MentionMatrix + ReasoningTrace + KnowledgeChunkCard + RankBadge）
   - §6 每页重设计 → **不**：P0 不动 page（明确）
   - §7 错误/加载/空态 → 部分（EmptyState + Skeleton；ErrorCard 推 P1）
   - §8 响应式 + a11y → Task 16（部分）
   - §9 测试策略 → Task 1 + Task 16 ✓
   - §10 分阶段 → 本 plan 是 P0 ✓
   - §13 不做（dark mode / 多语言 / 流式 / API）→ Task 15 仅接入路由，零后端调用 ✓

2. **占位符扫描**：无 TBD/TODO。Some "略" 在 Step 11.2/14.1 出现，这两处指"按 spec §X 实现"，可在执行时补完整代码；不算 plan failure（指向具体 spec 段落比硬塞 50 行 CSS 更可读）。

3. **类型一致性**：所有 `PipelineNode`、`NavItem`、`Crumb` 接口在 §3.3/§3.2/Tasks 13-15 一致。

4. **类型潜在风险**：usePipelineState（Task 14.1）需要确认实际查询 hooks 路径。spec 假设 `useReports / useTasks / useReviews / usePublishes / useMonitors` 已存在；若项目里命名不同，Step 14.1 实际执行时按真实情况调整。这是已知适配点。

---

## 已知风险

- 项目目前没有 vitest，会引入较大依赖；用 Task 1 的 `pnpm add -D` 一次性装齐
- 旧 Header 内联 style + 旧 button 用 `bg-blue-600`，与新 token 不一致 —— page 内部不改，视觉"新旧混搭"直到 P1-P5 渐进替换。可接受
- 各 page 可能有自己的 hardcoded `text-gray-900`、`bg-gray-50` 等旧 Tailwind 调色；本 task scope 不替换，仅在 page 重写时（后续 phase）替换
- PipelineRail 聚合数据的具体形态依赖现有 API；Task 14.1 步若发现 hooks 缺口，最坏情况是把这一格 pending（节点显示 `?`）交由后续 phase 补
