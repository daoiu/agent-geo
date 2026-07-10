import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground hover:bg-primary/80',
        secondary:
          'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80',
        destructive:
          'border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80',
        outline: 'text-foreground',
        success: 'border-transparent bg-[hsl(var(--brand-success))] text-white',
        warning: 'border-transparent bg-[hsl(var(--brand-warning))] text-foreground',
        info: 'border-transparent bg-[hsl(var(--brand-info))] text-white',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {
  dot?: boolean;
}

function Badge({ className, variant, dot, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props}>
      {dot && (
        <span
          aria-hidden="true"
          className={cn(
            'mr-1.5 inline-block h-1.5 w-1.5 rounded-full',
            variant === 'destructive' && 'bg-destructive-foreground',
            variant === 'success' && 'bg-white',
            variant === 'warning' && 'bg-foreground',
            variant === 'info' && 'bg-white',
            variant === 'secondary' && 'bg-secondary-foreground',
            variant === 'outline' && 'bg-foreground',
            (!variant || variant === 'default') && 'bg-primary-foreground',
          )}
        />
      )}
      {props.children}
    </div>
  );
}

export { Badge, badgeVariants };
