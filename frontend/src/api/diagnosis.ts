/**
 * v0.7 诊断 (diagnosis) endpoints.
 *
 * Mounted routes (App.tsx): `/diagnose/*`, `/diagnosis/:taskId/status`.
 * Backed by `backend/app/api/diagnosis.py` + `/api/reports/*`.
 */
import type {
  DiagnosisRequest,
  DiagnosisTask,
  Report,
  ReportSummary,
} from '@/types/diagnosis';
import { request, BASE } from './infra';

export const diagnosisApi = {
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
};

export type DiagnosisApi = typeof diagnosisApi;
