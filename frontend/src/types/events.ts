// Event SSE của /agent/chat/stream và /agent/chat/resume (xem backend/app/agent/streaming.py)

export const PLATFORMS = ["linkedin", "twitter", "facebook"] as const;
export type Platform = (typeof PLATFORMS)[number];
export const PLATFORM_LABELS: Record<Platform, string> = {
  linkedin: "LinkedIn",
  twitter: "X Thread",
  facebook: "Facebook",
};

export type Drafts = Record<Platform, string>;
export const emptyDrafts = (): Drafts => ({ linkedin: "", twitter: "", facebook: "" });

export interface StatusEvent {
  step: string;
  message: string;
  thread_id?: string;
}

export interface TokenEvent {
  node: "generate_outline" | "multi_format_generator" | "refine_generator";
  token: string;
  platform?: Platform;
}

export interface CostUpdateEvent {
  node: string;
  model_id: string;
  prompt_tokens: number;
  completion_tokens: number;
  tokens: number;
  cost_usd: number;
  pricing_missing: boolean;
}

export interface FactCheckIssue {
  platform: string;
  kind: "fact" | "cliche";
  claim: string;
  problem: string;
  suggestion: string;
}

export interface FactCheckReport {
  passed: boolean;
  summary: string;
  issues: FactCheckIssue[];
  round: number;
}

/** Chunk agent đã tra cứu (RAG) cho lượt này; `ref` khớp số [i] trong context gửi LLM. */
export interface RagSource {
  ref: number;
  chunk_id: string;
  document_id: string;
  document_title: string;
  chunk_index: number;
  headings: string[];
  content: string;
  score: number;
  ranks: Partial<Record<"vector" | "fts", number>>;
}

export interface OutlineInterrupt {
  stage: "OUTLINE_APPROVAL";
  message: string | null;
  data: { outline: string; sources?: RagSource[] };
}

export interface DraftsInterrupt {
  stage: "DRAFTS_APPROVAL";
  message: string | null;
  data: { drafts: Drafts; fact_check_report: FactCheckReport | null };
}

export type HitlInterruptEvent = OutlineInterrupt | DraftsInterrupt;

export interface ErrorEvent {
  code: string;
  message: string;
}

export interface CompleteEvent {
  thread_id: string;
  status: string;
  total_tokens: number;
  total_cost_usd: number;
}

export type AgentEvent =
  | { event: "status"; data: StatusEvent }
  | { event: "token"; data: TokenEvent }
  | { event: "cost_update"; data: CostUpdateEvent }
  | { event: "hitl_interrupt"; data: HitlInterruptEvent }
  | { event: "error"; data: ErrorEvent }
  | { event: "complete"; data: CompleteEvent };

export type ResumeDecision =
  | { stage: "OUTLINE_APPROVAL"; action: "APPROVE" }
  | { stage: "OUTLINE_APPROVAL"; action: "EDIT"; updated_outline: string }
  | { stage: "OUTLINE_APPROVAL"; action: "REJECT"; feedback?: string }
  | { stage: "DRAFTS_APPROVAL"; action: "APPROVE" }
  | { stage: "DRAFTS_APPROVAL"; action: "EDIT"; updated_drafts: Partial<Drafts> };
