import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RejectReasonForm } from './RejectReasonForm';

describe('RejectReasonForm (v0.7)', () => {
  it('renders a textarea + a submit button (initially disabled)', () => {
    render(<RejectReasonForm onSubmit={vi.fn()} onCancel={vi.fn()} />);
    const ta = screen.getByRole('textbox');
    expect(ta).toBeInTheDocument();
    const submit = screen.getByRole('button', { name: /确认拒绝/ });
    expect(submit).toBeDisabled();
  });

  it('shows the counter and the helper line', () => {
    render(<RejectReasonForm onSubmit={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText(/常见理由/)).toBeInTheDocument();
    expect(screen.getByText(/0 \/ 500/)).toBeInTheDocument();
  });

  it('enables submit only when a non-empty reason is typed', () => {
    const onSubmit = vi.fn();
    render(<RejectReasonForm onSubmit={onSubmit} onCancel={vi.fn()} />);
    const ta = screen.getByRole('textbox');
    fireEvent.change(ta, { target: { value: '成本过高' } });
    const submit = screen.getByRole('button', { name: /确认拒绝/ });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    expect(onSubmit).toHaveBeenCalledWith('成本过高');
  });

  it('caps reason at 500 characters', () => {
    render(<RejectReasonForm onSubmit={vi.fn()} onCancel={vi.fn()} />);
    const ta = screen.getByRole('textbox') as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: 'x'.repeat(600) } });
    expect(ta.value.length).toBeLessThanOrEqual(500);
  });

  it('calls onCancel when cancel button is clicked', () => {
    const onCancel = vi.fn();
    render(<RejectReasonForm onSubmit={vi.fn()} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole('button', { name: /取消/ }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
