/**
 * v0.7 知识库 (knowledge) endpoints.
 *
 * Mounted routes (App.tsx): `/knowledge/bases/*` + the cross-KB
 * `/knowledge/search` surface introduced in v0.6 P1.3.
 */
import type {
  GlobalKnowledgeSearchResult,
  KnowledgeBase,
  KnowledgeDetail,
} from '@/types/v0.2';
import { ApiError, request } from './infra';

export const knowledgeApi = {
  listKnowledgeBases(): Promise<KnowledgeBase[]> {
    return request('/knowledge');
  },

  createKnowledgeBase(body: { name: string; description?: string }): Promise<KnowledgeBase> {
    return request('/knowledge', { method: 'POST', body: JSON.stringify(body) });
  },

  getKnowledgeBase(kbId: string): Promise<KnowledgeDetail> {
    return request(`/knowledge/${kbId}`);
  },

  deleteKnowledgeBase(kbId: string): Promise<void> {
    return request(`/knowledge/${kbId}`, { method: 'DELETE' });
  },

  uploadDocument(kbId: string, file: File): Promise<KnowledgeDetail['documents'][number]> {
    const formData = new FormData();
    formData.append('file', file);
    // uploads skip the JSON content-type from authHeaders() — re-use fetch directly
    return fetch(`/api/knowledge/${kbId}/documents`, {
      method: 'POST',
      body: formData,
    }).then(async (r) => {
      if (!r.ok) {
        const text = await r.text();
        throw new ApiError(r.status, text || r.statusText);
      }
      return r.json();
    });
  },

  deleteDocument(kbId: string, docId: string): Promise<void> {
    return request(`/knowledge/${kbId}/documents/${docId}`, { method: 'DELETE' });
  },

  // v0.6 P1.3 — cross-KB hybrid recall (no kb_id required)
  searchKnowledgeGlobal(q: string, limit = 10): Promise<GlobalKnowledgeSearchResult> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return request(`/knowledge/search?${params.toString()}`);
  },
};

export type KnowledgeApi = typeof knowledgeApi;
