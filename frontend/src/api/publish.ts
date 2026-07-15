/**
 * v0.7 发布 (publish) endpoints — publisher platform configs +
 * publish-history jobs.
 *
 * Mounted routes (App.tsx): `/publish/configs` + `/publish/jobs`.
 */
import type { PublishJob, PublisherConfig } from '@/types/v0.3';
import { request } from './infra';

export const publishApi = {
  // ---- Publishers ----
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

  updatePublisher(
    id: string,
    body: Partial<{
      name: string;
      site_url: string;
      username: string;
      app_password: string;
      is_default: boolean;
    }>,
  ): Promise<PublisherConfig> {
    return request(`/publishers/${id}`, { method: 'PUT', body: JSON.stringify(body) });
  },

  deletePublisher(id: string): Promise<void> {
    return request(`/publishers/${id}`, { method: 'DELETE' });
  },

  testPublisher(id: string): Promise<{ ok: boolean; user?: unknown; error?: string }> {
    return request(`/publishers/${id}/test`, { method: 'POST' });
  },

  // ---- Publish Jobs ----
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
};

export type PublishApi = typeof publishApi;
