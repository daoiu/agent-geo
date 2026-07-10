import { forwardRef, type SelectHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';
import { FieldWrapper } from './FieldWrapper';

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  options?: Array<{ value: string; label: string }>;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, hint, required, id, className, options, children, ...rest },
  ref
) {
  return (
    <FieldWrapper label={label} error={error} hint={hint} id={id} required={required}>
      <select
        id={id}
        ref={ref}
        required={required}
        aria-invalid={!!error}
        className={cn(
          'h-10 w-full appearance-none rounded-md border bg-bg px-3 pr-9 text-sm text-fg',
          'bg-[url("data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2212%22 height=%2212%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%23475569%22 stroke-width=%222%22><path d=%22M6 9l6 6 6-6%22/></svg>")] bg-no-repeat bg-[center_right_0.75rem]',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          error ? 'border-danger' : 'border-border',
          className
        )}
        {...rest}
      >
        {options
          ? options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))
          : children}
      </select>
    </FieldWrapper>
  );
});
