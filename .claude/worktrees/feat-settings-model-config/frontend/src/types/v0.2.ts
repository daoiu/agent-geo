export type Style = 'neutral' | 'professional' | 'casual';
export type TaskStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';
export type ReviewStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'revise_requested';

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface KnowledgeDocument {
  id: string;
  kb_id: string;
  filename: string;
  file_type: string;
  file_size: number | null;
  parse_status: 'pending' | 'success' | 'failed';
  parse_error: string | null;
  chunk_count: number;
  created_at: string;
}

export interface KnowledgeChunk {
  id: string;
  doc_id: string;
  chunk_index: number;
  content: string;
  content_length: number;
}

export interface KnowledgeDetail {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  documents: KnowledgeDocument[];
}

// v0.6 P1.3 — cross-KB hybrid recall (no kb_id required at API level)
export interface GlobalKnowledgeHit {
  kb_id: string;
  kb_name: string;
  doc_id: string;
  doc_filename: string;
  chunk_id: string;
  chunk_index: number;
  content: string;
  score: number;
  sources: ('vector' | 'keyword')[];
}

export interface GlobalKnowledgeSearchResult {
  query: string;
  hits: GlobalKnowledgeHit[];
}

export interface Task {
  id: string;
  name: string;
  kb_id: string;
  brand: string | null;
  topic: string;
  keywords: string[];
  article_count: number;
  style: Style;
  target_length: number;
  status: TaskStatus;
  progress: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  articles?: Article[];
}

export interface Article {
  id: string;
  task_id: string;
  title: string | null;
  content: string | null;
  content_length: number | null;
  review_status: ReviewStatus;
  review_note: string | null;
  reviewed_at: string | null;
  cited_chunks: string[];
  llm_provider: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}
