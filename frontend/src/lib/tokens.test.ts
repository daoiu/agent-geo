import { describe, it, expect } from 'vitest';
import { tokens } from './tokens';

describe('tokens', () => {
  it('exposes the brand primary', () => {
    expect(tokens.color.primary).toBe('#0D9488');
  });

  it('exposes the accent / CTA color', () => {
    expect(tokens.color.accent).toBe('#EA580C');
  });

  it('exposes the Inter font family as the first choice', () => {
    expect(tokens.font.sans[0]).toBe('Inter');
  });

  it('exposes the success status color', () => {
    expect(tokens.color.success).toBe('#10B981');
  });

  it('exposes a focus ring color', () => {
    expect(tokens.color.ring).toBe('#0D9488');
  });
});
