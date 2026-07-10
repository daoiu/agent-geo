import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';
import { FieldWrapper } from './FieldWrapper';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, required, id, className, type = 'text', ...rest },
  ref
) {
  return (
    <FieldWrapper label={label} error={error} hint={hint} id={id} required={required}>
      <input
        id={id}
        ref={ref}
        type={type}
        required={required}
        aria-invalid={!!error}
        className={cn(
          'h-10 w-full rounded-md border bg-bg px-3 text-sm text-fg',
          'placeholder:text-fg-dim',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'transition-colors',
          error
            ? 'border-danger focus-within:shadow-[0_0_0_3px_rgba(220,38,38,0.25)]'
            : 'border-border focus-within:border-primary',
          className
        )}
        {...rest}
      />
    </FieldWrapper>
  );
});
