/**
 * v0.7 监测 (monitor) endpoints — periodic brand-mention monitoring
 * tasks + the threshold-notification side-channel.
 *
 * Mounted routes (App.tsx): `/monitor/tasks/*`. The threshold
 * notification rules live at `/settings/notifications` (settings).
 */
import type { MentionSnapshot, MonitorTask, TrendData } from '@/types/v0.3';
import { request } from './infra';

export const monitorApi = {
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

  // Threshold-notification side channel (settings/notifications page uses this).
  sendTestEmail(to: string): Promise<{ ok: boolean; error?: string }> {
    return request('/notifications/test', { method: 'POST', body: JSON.stringify({ to }) });
  },
};

export type MonitorApi = typeof monitorApi;
