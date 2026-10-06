// Response REST của backend (xem backend/app/schemas)
import type { HitlInterruptEvent } from "./events";

export type Role = "USER" | "ADMIN";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: Role;
  is_active: boolean;
}

export interface AdminUser extends User {
  created_at: string;
}

export interface ModelOption {
  model_id: string;
  provider: string;
  is_default: boolean;
  available: boolean;
}

export interface Thread {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ThreadMessage {
  id: string;
  sender_role: "USER" | "ASSISTANT" | "SYSTEM" | "HUMAN_INTERRUPT";
  content: string;
  content_type: "TEXT" | "OUTLINE_CARD" | "DRAFTS_CARD" | "FACT_CHECK_REPORT";
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ThreadState {
  thread_id: string;
  pending: HitlInterruptEvent | null;
  total_tokens: number;
  total_cost_usd: number;
}

export type DocumentStatus = "PENDING" | "PROCESSING" | "READY" | "FAILED";

export const INGEST_STEPS = ["parse", "chunk", "embed", "save"] as const;
export type IngestStepName = (typeof INGEST_STEPS)[number];

export interface IngestStep {
  status: "pending" | "running" | "done" | "failed";
  done: number | null;
  total: number | null;
  unit: string | null;
  detail: string | null;
  started_at: string | null;
  finished_at: string | null;
  progress_at: string | null; // lần cuối done/detail thay đổi
}

/** documents.ingest_progress do worker ghi (backend/app/rag/progress.py). Rỗng với tài liệu cũ. */
export interface IngestProgress {
  stage?: IngestStepName | null;
  steps?: Record<IngestStepName, IngestStep>;
  heartbeat_at?: string | null;
}

export interface DocumentItem {
  id: string;
  user_id: string | null;
  scope: "SYSTEM" | "PRIVATE";
  title: string;
  file_type: string;
  file_size_bytes: number | null;
  processing_status: DocumentStatus;
  error_message: string | null;
  chunk_count: number;
  ingest_progress: IngestProgress;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunk {
  id: string;
  chunk_index: number;
  content: string;
  metadata: { headings?: string[]; token_count?: number; embedding_model?: string };
}

export interface DocumentChunkPage {
  total: number;
  offset: number;
  items: DocumentChunk[];
}

export type Provider = "google" | "openai" | "anthropic";

export interface Pricing {
  provider: Provider;
  model_id: string;
  input_price_per_1k: number;
  output_price_per_1k: number;
  is_system_active: boolean;
  is_default: boolean;
  updated_at: string;
}

export interface CostReport {
  total_tokens_consumed: number;
  total_cost_usd: number;
  breakdown_by_model: { model_id: string; tokens: number; cost_usd: number }[];
  breakdown_by_node: { node_name: string; tokens: number; cost_usd: number }[];
  breakdown_by_user: { user_id: string; tokens: number; cost_usd: number }[];
}
