import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Textarea } from './Textarea';

describe('Textarea', () => {
  it('associates label with textarea via htmlFor/id', () => {
    renderWithRouter(<Textarea id="topic" label="主题" />);
    expect(screen.getByLabelText('主题')).toBeInTheDocument();
  });

  it('renders error message in alert role', () => {
    renderWithRouter(<Textarea id="topic" label="主题" error="必填" />);
    expect(screen.getByRole('alert')).toHaveTextContent('必填');
  });
});
