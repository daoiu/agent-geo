/**
 * v0.7 生成 (generate) endpoints — covers both task CRUD and the
 * HITL review queue (articles that need human approval before publish).
 *
 * Mounted routes (App.tsx): `/generate/tasks/*` + `/generate/reviews/*`.
 */
import type { Article, Task } from '@/types/v0.2';
import { request } from './infra';

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
};

export type GenerateApi = typeof generateApi;
