import { cn } from '@/lib/utils';

interface SpinnerProps {
  size?: 'sm' | 'md';
  className?: string;
  /** Accessible label. Defaults to "加载中" but should be set in context. */
  label?: string;
}

export function Spinner({ size = 'md', className, label = '加载中' }: SpinnerProps) {
  const dim = size === 'sm' ? 'h-4 w-4 border-2' : 'h-5 w-5 border-2';
  return (
    <span
      role="status"
      aria-label={label}
      className={cn(
        'inline-block rounded-full animate-spin border-current border-t-transparent',
        dim,
        className
      )}
    />
  );
}
