import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface FieldWrapperProps {
  label?: string;
  error?: string;
  hint?: string;
  id?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}

/**
 * FieldWrapper — common label/hint/error scaffolding for form inputs.
 * Renders the label with proper htmlFor wiring, plus either a hint or
 * an error message (error takes priority; alert role for SR users).
 */
export function FieldWrapper({
  label,
  error,
  hint,
  id,
  required,
  children,
  className,
}: FieldWrapperProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-fg">
          {label}
          {required && (
            <span aria-hidden="true" className="ml-1 text-danger">
              *
            </span>
          )}
        </label>
      )}
      {children}
      {hint && !error && (
        <p className="text-xs text-fg-dim">{hint}</p>
      )}
      {error && (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
