import { describe, it, expect } from 'vitest';
import {
  tokens,
  colors,
  radius,
  motion,
  breakpoints,
  fontFamily,
} from './tokens';

describe('HarmonyOS tokens — new named exports', () => {
  it('exports primary #0A59F7', () => {
    expect(colors.primary).toBe('#0A59F7');
  });

  it('exports card radius 16px (lg)', () => {
    expect(radius.lg).toBe(16);
  });

  it('exports spring-gentle cubic-bezier 400ms', () => {
    expect(motion.springGentle.duration).toBe(400);
  });

  it('exports 5 breakpoints xs/sm/md/lg/xl', () => {
    expect(Object.keys(breakpoints)).toEqual(['xs', 'sm', 'md', 'lg', 'xl']);
  });

  it('fontFamily leads with HarmonyOS Sans', () => {
    expect(fontFamily.startsWith('HarmonyOS Sans')).toBe(true);
  });
});

describe('HarmonyOS tokens — backward-compatible tokens.color.*', () => {
  it('tokens.color.primary migrated to #0A59F7', () => {
    expect(tokens.color.primary).toBe('#0A59F7');
  });

  it('tokens.color.accent migrated to HarmonyOS accent #A8B0FF', () => {
    expect(tokens.color.accent).toBe('#A8B0FF');
  });

  it('tokens.color.success migrated to #34D77F', () => {
    expect(tokens.color.success).toBe('#34D77F');
  });

  it('tokens.color.ring migrated to #0A59F7', () => {
    expect(tokens.color.ring).toBe('#0A59F7');
  });

  it('tokens.font.sans font family leads with HarmonyOS Sans', () => {
    expect(tokens.font.sans[0]).toBe('HarmonyOS Sans');
  });
});
