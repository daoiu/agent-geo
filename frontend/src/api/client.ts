import type {
  DiagnosisRequest,
  DiagnosisTask,
  Report,
  ReportSummary,
} from '@/types/diagnosis';
import type {
  Article,
  GlobalKnowledgeSearchResult,
  KnowledgeBase,
  KnowledgeDetail,
  Task,
} from '@/types/v0.2';
import type {
  MentionSnapshot,
  MonitorTask,
  PublishJob,
  PublisherConfig,
  TrendData,
} from '@/types/v0.3';
import type {
  AgentEvent,
  AgentSession,
  AgentSessionDetail,
} from '@/types/v0.4';

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

  // v0.6 P1.3 — cross-KB hybrid recall (no kb_id required)
  searchKnowledgeGlobal(
    q: string,
    limit: number = 10,
  ): Promise<GlobalKnowledgeSearchResult> {
    const params = new URLSearchParams({ q, limit: String(limit) });
    return request(`/knowledge/search?${params.toString()}`);
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

  // ---- v0.3: Publishers ----
  listPublishers(): Promise<PublisherConfig[]> {
    return request('/publishers');
  },
  createPublisher(body: {
    name: string;
    site_url: string;
    username: string;
    app_password: string;
    is_default?: boolean;
  }): Promise<PublisherConfig> {
    return request('/publishers', { method: 'POST', body: JSON.stringify(body) });
  },
  updatePublisher(id: string, body: Partial<{
    name: string;
    site_url: string;
    username: string;
    app_password: string;
    is_default: boolean;
  }>): Promise<PublisherConfig> {
    return request(`/publishers/${id}`, { method: 'PUT', body: JSON.stringify(body) });
  },
  deletePublisher(id: string): Promise<void> {
    return request(`/publishers/${id}`, { method: 'DELETE' });
  },
  testPublisher(id: string): Promise<{ ok: boolean; user?: unknown; error?: string }> {
    return request(`/publishers/${id}/test`, { method: 'POST' });
  },

  // ---- v0.3: Publish Jobs ----
  listPublishJobs(status?: string): Promise<PublishJob[]> {
    const qs = status ? `?status=${status}` : '';
    return request(`/publishes${qs}`);
  },
  createPublishJob(body: {
    article_id: string;
    config_id: string;
    title_override?: string;
  }): Promise<PublishJob> {
    return request('/publishes', { method: 'POST', body: JSON.stringify(body) });
  },
  retryPublishJob(id: string): Promise<PublishJob> {
    return request(`/publishes/${id}/retry`, { method: 'POST' });
  },
  cancelPublishJob(id: string): Promise<PublishJob> {
    return request(`/publishes/${id}/cancel`, { method: 'POST' });
  },

  // ---- v0.3: Monitor Tasks ----
  listMonitors(): Promise<MonitorTask[]> {
    return request('/monitors');
  },
  createMonitor(body: {
    name: string;
    brand: string;
    industry: string;
    target_questions: string[];
    frequency: 'hourly' | 'daily' | 'weekly';
    providers?: string[];
    notify_email?: string;
    change_threshold?: number;
  }): Promise<MonitorTask> {
    return request('/monitors', { method: 'POST', body: JSON.stringify(body) });
  },
  updateMonitor(
    id: string,
    body: {
      name: string;
      brand: string;
      industry: string;
      target_questions: string[];
      frequency: 'hourly' | 'daily' | 'weekly';
      providers?: string[];
      notify_email?: string;
      change_threshold?: number;
    },
  ): Promise<MonitorTask> {
    return request(`/monitors/${id}`, { method: 'PUT', body: JSON.stringify(body) });
  },
  deleteMonitor(id: string): Promise<void> {
    return request(`/monitors/${id}`, { method: 'DELETE' });
  },
  runMonitorNow(id: string): Promise<{ status: string }> {
    return request(`/monitors/${id}/run`, { method: 'POST' });
  },
  getMonitorSnapshots(id: string, days = 30): Promise<MentionSnapshot[]> {
    return request(`/monitors/${id}/snapshots?days=${days}`);
  },
  getMonitorTrends(id: string, days = 30): Promise<TrendData> {
    return request(`/monitors/${id}/trends?days=${days}`);
  },

  // ---- v0.3: Notifications ----
  sendTestEmail(to: string): Promise<{ ok: boolean; error?: string }> {
    return request('/notifications/test', { method: 'POST', body: JSON.stringify({ to }) });
  },

  // ---- v0.4: Agent ----
  listAgentSessions(): Promise<AgentSession[]> {
    return request('/agent/sessions');
  },
  createAgentSession(title?: string): Promise<AgentSession> {
    return request('/agent/sessions', {
      method: 'POST',
      body: JSON.stringify(title ? { title } : {}),
    });
  },
  getAgentSession(id: string): Promise<AgentSessionDetail> {
    return request(`/agent/sessions/${id}`);
  },
  deleteAgentSession(id: string): Promise<void> {
    return request(`/agent/sessions/${id}`, { method: 'DELETE' });
  },
  updateAgentSessionTitle(id: string, title: string): Promise<AgentSession> {
    return request(`/agent/sessions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    });
  },
  confirmAgentAction(
    sessionId: string,
    messageId: string,
    approved: boolean,
  ): Promise<{ status: string; message_id: string }> {
    return request(
      `/agent/sessions/${sessionId}/messages/${messageId}/confirm`,
      {
        method: 'POST',
        body: JSON.stringify({ approved }),
      },
    );
  },
};

// SSE 流：fetch + ReadableStream 消费服务端 SSE
export async function* sendAgentMessageStream(
  sessionId: string,
  content: string,
): AsyncGenerator<AgentEvent> {
  const response = await fetch(
    `${BASE}/agent/sessions/${sessionId}/messages`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    },
  );
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }
  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, remainder } = parseSSE(buffer);
    buffer = remainder;
    for (const evt of events) yield evt;
  }
}

export async function* confirmAgentActionStream(
  sessionId: string,
  messageId: string,
  approved: boolean,
): AsyncGenerator<AgentEvent> {
  const response = await fetch(
    `${BASE}/agent/sessions/${sessionId}/messages/${messageId}/confirm`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved }),
    },
  );
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }
  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, remainder } = parseSSE(buffer);
    buffer = remainder;
    for (const evt of events) yield evt;
  }
}

interface ParsedSSE {
  events: AgentEvent[];
  remainder: string;
}

function parseSSE(buffer: string): ParsedSSE {
  const events: AgentEvent[] = [];
  const lines = buffer.split('\n');
  let remainder = '';
  let currentEvent: string | null = null;
  let currentData: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith('event: ')) {
      currentEvent = line.slice(7).trim();
    } else if (line.startsWith('data: ')) {
      currentData.push(line.slice(6).trim());
    } else if (line === '' && currentEvent && currentData.length > 0) {
      try {
        const data = JSON.parse(currentData.join('\n'));
        events.push({ event: currentEvent, ...data } as AgentEvent);
      } catch {
        // 忽略格式错误的 event
      }
      currentEvent = null;
      currentData = [];
    } else if (i === lines.length - 1 && line !== '') {
      // 最后一行不完整，留到下次
      remainder = line;
    }
  }
  return { events, remainder };
}

export { ApiError };
