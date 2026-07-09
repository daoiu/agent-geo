export type TaskStatus =
  | 'pending'
  | 'crawling'
  | 'querying_llm'
  | 'scoring'
  | 'rendering'
  | 'completed'
  | 'failed';

export interface DiagnosisRequest {
  brand_name: string;
  industry: string;
  official_url: string;
  target_questions: string[];
  competitors: string[];
  contact_email?: string;
}

export interface DiagnosisTask {
  id: string;
  request: DiagnosisRequest;
  status: TaskStatus;
  progress: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface MentionResult {
  question: string;
  llm_provider: string;
  llm_answer: string;
  brand_mentioned: boolean;
  mention_position: number | null;
  competitors_mentioned: string[];
  sentiment: 'positive' | 'neutral' | 'negative';
  error: string | null;
}

export interface DimensionScore {
  name: string;
  score: number;
  weight: number;
  evidence: string[];
}

export interface ScoreCard {
  authority: DimensionScore;
  relevance: DimensionScore;
  structure: DimensionScore;
  freshness: DimensionScore;
  verifiability: DimensionScore;
  overall: number;
  mention_rate: number;
  avg_mention_position: number | null;
}

export interface Suggestion {
  priority: 'P0' | 'P1' | 'P2';
  category: string;
  title: string;
  detail: string;
  action_steps: string[];
  expected_impact: string;
}

export interface BrandInfo {
  name: string;
  industry: string;
  official_url: string;
}

export interface SiteAudit {
  url: string;
  crawl_status: 'success' | 'partial' | 'failed';
  crawled_at: string;
  schema: Record<string, unknown>;
  eeat: Record<string, unknown>;
  structure: Record<string, unknown>;
  freshness: Record<string, unknown>;
  page_load_ms: number | null;
  robots_txt_allows_ai_bots: Record<string, boolean>;
}

export interface Report {
  id: string;
  task_id: string;
  brand: BrandInfo;
  site_audit: SiteAudit | null;
  mentions: MentionResult[];
  score_card: ScoreCard;
  suggestions: Suggestion[];
  summary: string;
  created_at: string;
  pdf_available: boolean;
}

export interface ReportSummary {
  id: string;
  brand_name: string;
  industry: string;
  status: TaskStatus;
  created_at: string;
  overall_score: number | null;
}
