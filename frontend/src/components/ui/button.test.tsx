import { describe, it, expect, vi } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from './button.tsx';

describe('Button (shadcn)', () => {
  it('renders default variant with primary bg', () => {
    renderWithRouter(<Button>保存</Button>);
    const btn = screen.getByRole('button', { name: '保存' });
    expect(btn).toHaveClass('bg-primary');
  });

  it('renders accent variant for CTA', () => {
    renderWithRouter(<Button variant="accent">开始诊断</Button>);
    expect(screen.getByRole('button')).toHaveClass('bg-accent');
  });

  it('handles onClick', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    renderWithRouter(<Button onClick={onClick}>点</Button>);
    await user.click(screen.getByRole('button', { name: '点' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('disables when disabled', () => {
    renderWithRouter(<Button disabled>禁用</Button>);
    expect(screen.getByRole('button', { name: '禁用' })).toBeDisabled();
  });

  it('uses button type by default', () => {
    renderWithRouter(<Button>无类型</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('type', 'button');
  });
});
