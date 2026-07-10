import { forwardRef, type TextareaHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';
import { FieldWrapper } from './FieldWrapper';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, hint, required, id, className, rows = 4, ...rest },
  ref
) {
  return (
    <FieldWrapper label={label} error={error} hint={hint} id={id} required={required}>
      <textarea
        id={id}
        ref={ref}
        rows={rows}
        required={required}
        aria-invalid={!!error}
        className={cn(
          'w-full rounded-md border bg-bg px-3 py-2 text-sm text-fg',
          'placeholder:text-fg-dim',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'transition-colors',
          error ? 'border-danger' : 'border-border',
          className
        )}
        {...rest}
      />
    </FieldWrapper>
  );
});
