/**
 * v0.7 生成 (generate) endpoints — covers both task CRUD and the
 * HITL review queue (articles that need human approval before publish).
 *
 * Mounted routes (App.tsx): `/generate/tasks/*` + `/generate/reviews/*`.
 */
import type { Article, Task } from '@/types/v0.2';
import { ApiError, authHeaders, request } from './infra';

export const generateApi = {
  listTasks(): Promise<Task[]> {
    return request('/tasks');
  },

  createTask(body: {
    name: string;
    kb_id: string;
    brand?: string;
    topic: string;
    keywords?: string[];
    article_count?: number;
    style?: 'neutral' | 'professional' | 'casual';
    target_length?: number;
  }): Promise<Task> {
    return request('/tasks', { method: 'POST', body: JSON.stringify(body) });
  },

  getTask(taskId: string): Promise<Task> {
    return request(`/tasks/${taskId}`);
  },

  deleteTask(taskId: string): Promise<void> {
    return request(`/tasks/${taskId}`, { method: 'DELETE' });
  },

  cancelTask(taskId: string): Promise<Task> {
    return request(`/tasks/${taskId}/cancel`, { method: 'POST' });
  },

  // ---- Reviews (HITL queue) ----
  listReviewQueue(
    status: 'pending' | 'approved' | 'rejected' = 'pending',
  ): Promise<Article[]> {
    return request(`/reviews?status=${status}`);
  },

  getArticle(articleId: string): Promise<Article> {
    return request(`/reviews/${articleId}`);
  },

  approveArticle(articleId: string, note?: string): Promise<Article> {
    // Omit `note` entirely when undefined so backend sees `None`, not `''`
    return request(`/reviews/${articleId}/approve`, {
      method: 'POST',
      body: JSON.stringify(note !== undefined ? { note } : {}),
    });
  },

  rejectArticle(articleId: string, note: string): Promise<Article> {
    return request(`/reviews/${articleId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    });
  },

  /**
   * v0.6 P1.5 — serve the raw markdown of a reviewed article.
   * Returns a relative URL so the browser can stream the .md directly.
   */
  getArticleDownloadUrl(articleId: string): string {
    return `/api/reviews/${articleId}/download`;
  },

  /**
   * Stream the article markdown from the backend (spec §7.1 / Task 15).
   * The browser-side `Blob` route is faster for small articles; the
   * streaming route is preferred for very long articles where the
   * server can apply formatting fixes in the same response.
   */
  async downloadArticle(articleId: string): Promise<Blob> {
    const resp = await fetch(generateApi.getArticleDownloadUrl(articleId), {
      headers: authHeaders(),
    });
    if (!resp.ok) throw new ApiError(resp.status, await resp.text());
    return resp.blob();
  },
};

export type GenerateApi = typeof generateApi;
