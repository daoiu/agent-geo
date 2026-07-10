import { describe, it, expect, vi } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from './Button';

describe('Button', () => {
  it('renders with primary variant by default', () => {
    renderWithRouter(<Button>保存</Button>);
    const btn = screen.getByRole('button', { name: '保存' });
    expect(btn).toHaveClass('bg-primary');
  });

  it('renders accent variant as CTA', () => {
    renderWithRouter(<Button variant="accent">开始诊断</Button>);
    const btn = screen.getByRole('button', { name: '开始诊断' });
    expect(btn).toHaveClass('bg-accent');
  });

  it('shows loading spinner and disables click when loading', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    renderWithRouter(
      <Button loading onClick={onClick}>
        提交
      </Button>
    );
    const btn = screen.getByRole('button', { name: /加载中.*提交|提交/ });
    expect(btn).toBeDisabled();
    await user.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('forwards onClick handler', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    renderWithRouter(<Button onClick={onClick}>点</Button>);
    await user.click(screen.getByRole('button', { name: '点' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('uses button type when no type is passed', () => {
    renderWithRouter(<Button>无类型</Button>);
    expect(screen.getByRole('button', { name: '无类型' })).toHaveAttribute('type', 'button');
  });
});
