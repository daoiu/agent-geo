import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Input } from './Input';

describe('Input', () => {
  it('associates label with input via htmlFor/id', () => {
    renderWithRouter(<Input id="brand" label="品牌" />);
    const input = screen.getByLabelText('品牌');
    expect(input).toBeInTheDocument();
  });

  it('renders error message in alert role and applies aria-invalid', () => {
    renderWithRouter(<Input id="brand" label="品牌" error="必填" />);
    expect(screen.getByRole('alert')).toHaveTextContent('必填');
    expect(screen.getByLabelText('品牌')).toHaveAttribute('aria-invalid', 'true');
  });

  it('renders hint when no error', () => {
    renderWithRouter(<Input id="brand" label="品牌" hint="试试小米" />);
    expect(screen.getByText('试试小米')).toBeInTheDocument();
  });

  it('hides hint when error is set', () => {
    renderWithRouter(<Input id="brand" label="品牌" hint="试试小米" error="必填" />);
    expect(screen.queryByText('试试小米')).not.toBeInTheDocument();
  });
});
