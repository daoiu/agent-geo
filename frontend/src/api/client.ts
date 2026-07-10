import type {
  DiagnosisRequest,
  DiagnosisTask,
  Report,
  ReportSummary,
} from '@/types/diagnosis';
import type {
  Article,
  KnowledgeBase,
  KnowledgeDetail,
  Task,
} from '@/types/v0.2';

const BASE = '/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new ApiError(resp.status, body || resp.statusText);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

export const api = {
  submitDiagnosis(req: DiagnosisRequest): Promise<{ task_id: string; status: string }> {
    return request('/diagnosis', { method: 'POST', body: JSON.stringify(req) });
  },

  getStatus(taskId: string): Promise<DiagnosisTask> {
    return request(`/diagnosis/${taskId}/status`);
  },

  getReport(taskId: string): Promise<Report> {
    return request(`/reports/${taskId}`);
  },

  listReports(): Promise<ReportSummary[]> {
    return request('/reports');
  },

  getPdfUrl(taskId: string): string {
    return `${BASE}/reports/${taskId}/pdf`;
  },

  // ---- v0.2: Knowledge Base ----
  listKnowledgeBases(): Promise<KnowledgeBase[]> {
    return request('/knowledge');
  },
  createKnowledgeBase(body: {
    name: string;
    description?: string;
  }): Promise<KnowledgeBase> {
    return request('/knowledge', {
      method: 'POST',
      body: JSON.stringify(body),
    });
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
    return fetch(`${BASE}/knowledge/${kbId}/documents`, {
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
    return request(`/knowledge/${kbId}/documents/${docId}`, {
      method: 'DELETE',
    });
  },

  // ---- v0.2: Tasks ----
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

  // ---- v0.2: Reviews ----
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
};

export { ApiError };
