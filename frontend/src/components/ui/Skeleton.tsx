import { cn } from '@/lib/utils';

export interface SkeletonProps {
  /** Tailwind classes for sizing / shape. Defaults to full width × 16px tall. */
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      role="status"
      aria-label="加载中"
      className={cn('animate-pulse rounded-md bg-fg-dim/15', className)}
    />
  );
}

export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div role="status" aria-label="加载列表" className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full" />
      ))}
    </div>
  );
}
