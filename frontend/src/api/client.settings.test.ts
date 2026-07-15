import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiError } from './client';

describe('settingsApi (v0.7+)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('getModelConfig calls GET /settings/models', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        providers: [],
        tiers: { cheap: '', standard: '', premium: '' },
        fallback_chain: [],
        llm_providers: [],
        source: 'env',
        updated_at: '',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const { settingsApi } = await import('./client');
    const r = await settingsApi.getModelConfig();
    expect(r.source).toBe('env');
    expect(fetchMock).toHaveBeenCalledWith('/api/settings/models', expect.objectContaining({
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
    }));
  });

  it('updateModelConfig sends PATCH with body', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        providers: [],
        tiers: {},
        fallback_chain: [],
        llm_providers: [],
        source: 'json',
        updated_at: '2026-07-15T00:00:00+00:00',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const { settingsApi } = await import('./client');
    await settingsApi.updateModelConfig({
      providers: [{ name: 'deepseek', api_key: 'sk-new', model: 'm' }],
    });
    expect(fetchMock).toHaveBeenCalledWith('/api/settings/models', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({
        providers: [{ name: 'deepseek', api_key: 'sk-new', model: 'm' }],
      }),
    }));
  });

  it('resetModelConfig calls POST /settings/models/reset', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ providers: [], tiers: {}, fallback_chain: [], llm_providers: [], source: 'env', updated_at: '' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const { settingsApi } = await import('./client');
    await settingsApi.resetModelConfig();
    expect(fetchMock).toHaveBeenCalledWith('/api/settings/models/reset', expect.objectContaining({
      method: 'POST',
    }));
  });

  it('throws ApiError with status on non-OK', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: async () => JSON.stringify({ detail: { code: 'unknown_provider', message: 'x' } }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const { settingsApi } = await import('./client');
    await expect(settingsApi.getModelConfig()).rejects.toBeInstanceOf(ApiError);
    await expect(settingsApi.getModelConfig()).rejects.toMatchObject({ status: 422 });
  });
});