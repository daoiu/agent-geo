import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DevToolsPanel } from './DevToolsPanel';

describe('DevToolsPanel (v0.7)', () => {
  beforeEach(() => {
    // Stub localStorage so the panel starts blank every test.
    window.localStorage.clear();
  });

  it('renders the 5 fault kinds as radio options', () => {
    render(<DevToolsPanel />);
    expect(screen.getByLabelText(/LLM 超时/)).toBeInTheDocument();
    expect(screen.getByLabelText(/工具错误/)).toBeInTheDocument();
    expect(screen.getByLabelText(/网络 503/)).toBeInTheDocument();
    expect(screen.getByLabelText(/限流/)).toBeInTheDocument();
    expect(screen.getByLabelText(/部分流/)).toBeInTheDocument();
  });

  it('shows target as "next" by default and allows duration target', async () => {
    const user = userEvent.setup();
    render(<DevToolsPanel />);
    expect(screen.getByDisplayValue('next')).toBeChecked();
    const tenMin = screen.getByLabelText(/10 分钟/) as HTMLInputElement;
    await user.click(tenMin);
    expect(tenMin).toBeChecked();
  });

  it('persists selected fault into localStorage under fault_config', async () => {
    const user = userEvent.setup();
    render(<DevToolsPanel />);
    // default is LLM 超时 (checked) — pick "工具错误" so onChange actually fires
    await user.click(screen.getByLabelText(/工具错误/));
    const stored = JSON.parse(
      window.localStorage.getItem('fault_config') ?? 'null',
    );
    expect(stored?.kind).toBe('tool_error');
  });

  it('does not require any backend round-trip', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const user = userEvent.setup();
    render(<DevToolsPanel />);
    await user.click(screen.getByLabelText(/工具错误/));
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});
