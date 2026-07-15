import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockGet = vi.fn();
const mockUpdate = vi.fn();
const mockReset = vi.fn();

vi.mock('@/api/client', async () => {
  return {
    settingsApi: {
      getModelConfig: () => mockGet(),
      updateModelConfig: (payload: unknown) => mockUpdate(payload),
      resetModelConfig: () => mockReset(),
    },
    ApiError: class ApiError extends Error {
      constructor(public status: number, message: string) {
        super(message);
        this.name = 'ApiError';
      }
    },
  };
});

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

import ModelsSettings from './ModelsSettings';

function renderWithClient(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const baseDTO = {
  providers: [
    { name: 'deepseek', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat', api_key_set: true, api_key_masked: 'sk-***abc' },
    { name: 'kimi', base_url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k', api_key_set: false, api_key_masked: '' },
    { name: 'openai', base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini', api_key_set: false, api_key_masked: '' },
  ],
  tiers: { cheap: 'deepseek', standard: 'deepseek', premium: 'deepseek' },
  fallback_chain: ['deepseek', 'kimi'],
  llm_providers: ['deepseek'],
  source: 'env' as const,
  updated_at: '',
};

function findProviderCard(name: string): HTMLElement {
  const card = document.querySelector(`[data-testid="provider-card-${name}"]`);
  if (!card) throw new Error(`provider card ${name} not found`);
  return card as HTMLElement;
}

describe('ModelsSettings (v0.7+)', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockUpdate.mockReset();
    mockReset.mockReset();
    mockGet.mockResolvedValue(baseDTO);
    mockUpdate.mockResolvedValue({ ...baseDTO, source: 'json' });
    mockReset.mockResolvedValue({ ...baseDTO, source: 'env' });
  });

  it('renders loading skeleton on mount', () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    renderWithClient(<ModelsSettings />);
    expect(document.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });

  it('renders three provider cards after load', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(findProviderCard('deepseek')).toBeTruthy());
    expect(findProviderCard('kimi')).toBeTruthy();
    expect(findProviderCard('openai')).toBeTruthy();
  });

  it('api_key input shows mask placeholder when set', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(findProviderCard('deepseek')).toBeTruthy());
    const card = findProviderCard('deepseek');
    const inputs = card.querySelectorAll('input');
    const maskedInput = Array.from(inputs).find((el) => (el as HTMLInputElement).placeholder.includes('***'));
    expect(maskedInput).toBeDefined();
  });

  it('api_key input shows "尚未设置" placeholder when unset', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(findProviderCard('kimi')).toBeTruthy());
    const card = findProviderCard('kimi');
    const inputs = card.querySelectorAll('input');
    const unsetInput = Array.from(inputs).find((el) => (el as HTMLInputElement).placeholder.includes('尚未设置'));
    expect(unsetInput).toBeDefined();
  });

  it('changing base_url or model marks dirty and enables save', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(findProviderCard('deepseek')).toBeTruthy());
    const saveBtn = screen.getByRole('button', { name: /^保存$/ });
    expect(saveBtn).toBeDisabled();
    const card = findProviderCard('deepseek');
    const modelInput = within(card).getByDisplayValue('deepseek-chat');
    fireEvent.change(modelInput, { target: { value: 'deepseek-reasoner' } });
    expect(saveBtn).not.toBeDisabled();
  });

  it('saving with no api_key field sends no api_key in payload', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(findProviderCard('deepseek')).toBeTruthy());
    const card = findProviderCard('deepseek');
    const modelInput = within(card).getByDisplayValue('deepseek-chat');
    fireEvent.change(modelInput, { target: { value: 'deepseek-reasoner' } });
    const saveBtn = screen.getByRole('button', { name: /^保存$/ });
    fireEvent.click(saveBtn);
    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    const payload = mockUpdate.mock.calls[0][0];
    const dp = payload.providers.find((p: { name: string }) => p.name === 'deepseek');
    expect(dp.api_key).toBeUndefined();
  });

  it('saving with new api_key sends the value', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(findProviderCard('deepseek')).toBeTruthy());
    const card = findProviderCard('deepseek');
    const apiKeyInput = Array.from(card.querySelectorAll('input')).find(
      (el) => (el as HTMLInputElement).placeholder.includes('***'),
    ) as HTMLInputElement;
    fireEvent.change(apiKeyInput, { target: { value: 'sk-brand-new' } });
    const saveBtn = screen.getByRole('button', { name: /^保存$/ });
    fireEvent.click(saveBtn);
    await waitFor(() => expect(mockUpdate).toHaveBeenCalled());
    const payload = mockUpdate.mock.calls[0][0];
    const dp = payload.providers.find((p: { name: string }) => p.name === 'deepseek');
    expect(dp.api_key).toBe('sk-brand-new');
  });

  it('save success shows toast', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(findProviderCard('deepseek')).toBeTruthy());
    const card = findProviderCard('deepseek');
    const modelInput = within(card).getByDisplayValue('deepseek-chat');
    fireEvent.change(modelInput, { target: { value: 'deepseek-v2' } });
    const saveBtn = screen.getByRole('button', { name: /^保存$/ });
    fireEvent.click(saveBtn);
    const { toast } = await import('sonner');
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
  });

  it('save validation error shows toast', async () => {
    mockUpdate.mockRejectedValueOnce(new Error(JSON.stringify({ detail: { code: 'invalid_base_url', field: 'providers[0].base_url' } })));
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(findProviderCard('deepseek')).toBeTruthy());
    const card = findProviderCard('deepseek');
    const modelInput = within(card).getByDisplayValue('deepseek-chat');
    fireEvent.change(modelInput, { target: { value: 'new' } });
    const saveBtn = screen.getByRole('button', { name: /^保存$/ });
    fireEvent.click(saveBtn);
    const { toast } = await import('sonner');
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });

  it('save encryption_key_missing shows banner', async () => {
    mockUpdate.mockRejectedValueOnce(new Error(JSON.stringify({ detail: { code: 'encryption_key_missing' } })));
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(findProviderCard('deepseek')).toBeTruthy());
    const card = findProviderCard('deepseek');
    const modelInput = within(card).getByDisplayValue('deepseek-chat');
    fireEvent.change(modelInput, { target: { value: 'new' } });
    const saveBtn = screen.getByRole('button', { name: /^保存$/ });
    fireEvent.click(saveBtn);
    await waitFor(() => expect(screen.getAllByText(/加密密钥未配置/).length).toBeGreaterThan(0));
  });

  it('reset button requires confirmation', async () => {
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(findProviderCard('deepseek')).toBeTruthy());
    const resetBtn = screen.getByRole('button', { name: /重置/ });
    fireEvent.click(resetBtn);
    await waitFor(() => expect(screen.getByText(/确认重置配置？/)).toBeInTheDocument());
    expect(mockReset).not.toHaveBeenCalled();
  });

  it('reset clears overrides and confirms via dialog', async () => {
    mockGet.mockResolvedValueOnce({ ...baseDTO, source: 'json' });
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(screen.getAllByText(/JSON 覆盖/).length).toBeGreaterThan(0));
    const resetBtn = screen.getByRole('button', { name: /重置/ });
    fireEvent.click(resetBtn);
    await waitFor(() => expect(screen.getByText(/确认重置配置？/)).toBeInTheDocument());
    const confirmBtn = screen.getByRole('button', { name: /^确认重置$/ });
    fireEvent.click(confirmBtn);
    await waitFor(() => expect(mockReset).toHaveBeenCalled());
  });

  it('concurrent save disables button while in-flight', async () => {
    mockUpdate.mockReturnValueOnce(new Promise(() => {}));
    renderWithClient(<ModelsSettings />);
    await waitFor(() => expect(findProviderCard('deepseek')).toBeTruthy());
    const card = findProviderCard('deepseek');
    const modelInput = within(card).getByDisplayValue('deepseek-chat');
    fireEvent.change(modelInput, { target: { value: 'deepseek-v3' } });
    const saveBtn = screen.getByRole('button', { name: /^保存$/ });
    fireEvent.click(saveBtn);
    // 等 mutation 进入 pending 状态（microtask 后）
    await waitFor(() => expect(saveBtn).toBeDisabled());
  });
});