export type PublishJobStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';
export type MonitorFrequency = 'hourly' | 'daily' | 'weekly';

export interface PublisherConfig {
  id: string;
  name: string;
  site_url: string;
  username: string;
  is_default: boolean;
  created_at: string;
}

export interface PublishJob {
  id: string;
  article_id: string;
  config_id: string;
  title_override: string | null;
  status: PublishJobStatus;
  remote_post_id: number | null;
  remote_url: string | null;
  error_message: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MonitorTask {
  id: string;
  name: string;
  brand: string;
  industry: string;
  target_questions: string[];
  frequency: MonitorFrequency;
  providers: string[];
  notify_email: string | null;
  change_threshold: number;
  is_active: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MentionSnapshot {
  id: string;
  monitor_task_id: string;
  run_at: string;
  mention_rate: number;
  mention_count: number;
  total_samples: number;
  avg_position: number | null;
  details: Array<Record<string, unknown>>;
  error_message: string | null;
  created_at: string;
}

export interface TrendPoint {
  run_at: string;
  mention_rate: number;
  mention_count: number;
  total_samples: number;
  avg_position: number | null;
}

export interface TrendData {
  monitor_id: string;
  days: number;
  points: TrendPoint[];
}
