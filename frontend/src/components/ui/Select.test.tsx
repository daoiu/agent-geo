import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Select } from './Select';

describe('Select', () => {
  it('renders options from the options prop', () => {
    renderWithRouter(
      <Select id="style" label="风格" options={[
        { value: 'friendly', label: '亲切' },
        { value: 'formal', label: '正式' },
      ]} />
    );
    expect(screen.getByLabelText('风格')).toBeInTheDocument();
    expect(screen.getByText('亲切')).toBeInTheDocument();
    expect(screen.getByText('正式')).toBeInTheDocument();
  });

  it('renders error message and aria-invalid when error is set', () => {
    renderWithRouter(
      <Select id="style" label="风格" error="必选" options={[{ value: 'a', label: 'A' }]} />
    );
    expect(screen.getByRole('alert')).toHaveTextContent('必选');
    expect(screen.getByLabelText('风格')).toHaveAttribute('aria-invalid', 'true');
  });
});
