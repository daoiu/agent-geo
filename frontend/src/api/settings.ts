/**
 * v0.7+ settings API — model configuration endpoints (Task 41).
 */
import { request } from './infra';

export interface ProviderDTO {
  name: string;
  base_url: string;
  model: string;
  api_key_set: boolean;
  api_key_masked: string;
}

export interface ModelConfigDTO {
  providers: ProviderDTO[];
  tiers: { cheap: string; standard: string; premium: string };
  fallback_chain: string[];
  llm_providers: string[];
  source: 'env' | 'json';
  updated_at: string;
}

export interface ProviderUpdate {
  name: string;
  api_key?: string | null;
  base_url?: string | null;
  model?: string | null;
}

export interface ModelConfigUpdate {
  providers?: ProviderUpdate[];
  tiers?: { cheap?: string; standard?: string; premium?: string };
  fallback_chain?: string[];
  llm_providers?: string[];
}

export const settingsApi = {
  getModelConfig(): Promise<ModelConfigDTO> {
    return request<ModelConfigDTO>('/settings/models');
  },

  updateModelConfig(payload: ModelConfigUpdate): Promise<ModelConfigDTO> {
    return request<ModelConfigDTO>('/settings/models', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  resetModelConfig(): Promise<ModelConfigDTO> {
    return request<ModelConfigDTO>('/settings/models/reset', { method: 'POST' });
  },
};

export type SettingsApi = typeof settingsApi;