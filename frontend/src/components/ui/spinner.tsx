import { cn } from '@/lib/utils';

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  /** Accessible label. Defaults to "加载中". */
  label?: string;
}

/**
 * Spinner — small loading indicator (kept as project utility).
 * shadcn has a different spinner pattern (Loader2 + spin); this version uses
 * a CSS-only ring and integrates with the project's tokens via `border-current`.
 */
export function Spinner({ size = 'md', className, label = '加载中' }: SpinnerProps) {
  const dim =
    size === 'sm' ? 'h-4 w-4 border-2' : size === 'lg' ? 'h-8 w-8 border-4' : 'h-5 w-5 border-2';
  return (
    <span
      role="status"
      aria-label={label}
      className={cn(
        'inline-block rounded-full animate-spin border-current border-t-transparent',
        dim,
        className,
      )}
    />
  );
}
