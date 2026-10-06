"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";

import { api, errorText } from "@/lib/api";
import { postEventStream } from "@/lib/sse";
import type { ThreadState } from "@/types/api";
import {
  emptyDrafts,
  type AgentEvent,
  type Drafts,
  type HitlInterruptEvent,
  type Platform,
  type ResumeDecision,
  type StatusEvent,
} from "@/types/events";
import { useCostTracker } from "./useCostTracker";

// idle → streaming → (awaiting_outline | awaiting_drafts | done | error); awaiting_* → resume → streaming
export type Phase = "idle" | "streaming" | "awaiting_outline" | "awaiting_drafts" | "done" | "error";

interface State {
  phase: Phase;
  threadId: string | null;
  status: StatusEvent | null;
  outline: string; // token outline đang stream
  drafts: Drafts; // token bản thảo đang stream theo kênh
  refined: Platform[]; // kênh đã bắt đầu nhận token refine trong vòng sửa hiện tại
  interrupt: HitlInterruptEvent | null;
  error: string | null;
}

type Action =
  | { type: "start"; threadId: string | null }
  | { type: "event"; event: AgentEvent }
  | { type: "fail"; message: string }
  | { type: "load"; threadId: string | null; interrupt: HitlInterruptEvent | null };

const initial: State = {
  phase: "idle",
  threadId: null,
  status: null,
  outline: "",
  drafts: emptyDrafts(),
  refined: [],
  interrupt: null,
  error: null,
};

const phaseFor = (i: HitlInterruptEvent | null): Phase =>
  !i ? "idle" : i.stage === "OUTLINE_APPROVAL" ? "awaiting_outline" : "awaiting_drafts";

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "start":
      return { ...initial, phase: "streaming", threadId: action.threadId };
    case "load":
      return { ...initial, threadId: action.threadId, interrupt: action.interrupt, phase: phaseFor(action.interrupt) };
    case "fail":
      return { ...state, phase: "error", error: action.message };
    case "event":
      return applyEvent(state, action.event);
  }
}

function applyEvent(state: State, ev: AgentEvent): State {
  switch (ev.event) {
    case "status": {
      const threadId = ev.data.thread_id ?? state.threadId;
      // Mỗi vòng refine viết lại từ đầu các kênh bị nêu lỗi
      const refined = ev.data.step === "REFINING_DRAFTS" ? [] : state.refined;
      return { ...state, threadId, status: ev.data, refined };
    }
    case "token": {
      const { node, token, platform } = ev.data;
      if (node === "generate_outline") return { ...state, outline: state.outline + token };
      if (!platform) return state;
      if (node === "refine_generator" && !state.refined.includes(platform)) {
        return { ...state, drafts: { ...state.drafts, [platform]: token }, refined: [...state.refined, platform] };
      }
      return { ...state, drafts: { ...state.drafts, [platform]: state.drafts[platform] + token } };
    }
    case "hitl_interrupt":
      return { ...state, phase: phaseFor(ev.data), interrupt: ev.data, status: null };
    case "error":
      return { ...state, phase: "error", error: ev.data.message, status: null };
    case "complete":
      return { ...state, phase: "done", status: null };
    case "cost_update":
      return state;
  }
}

const TERMINAL = new Set(["hitl_interrupt", "error", "complete"]);

interface Options {
  /** Gọi sau mỗi lượt stream kết thúc (để tải lại lịch sử / danh sách thread). */
  onSettled?: (threadId: string | null) => void;
}

export function useAgentStream({ onSettled }: Options = {}) {
  const [state, dispatch] = useReducer(reducer, initial);
  const cost = useCostTracker();
  const { add: addCost, reset: resetCost } = cost;
  const controller = useRef<AbortController | null>(null);
  const threadRef = useRef<string | null>(null);
  threadRef.current = state.threadId;
  const settledRef = useRef(onSettled);
  settledRef.current = onSettled;

  useEffect(() => () => controller.current?.abort(), []);

  const run = useCallback(
    async (path: string, body: Record<string, unknown>, threadId: string | null) => {
      controller.current?.abort();
      const ctrl = new AbortController();
      controller.current = ctrl;
      dispatch({ type: "start", threadId });
      let finished = false;
      let tid = threadId;
      try {
        await postEventStream(path, body, {
          signal: ctrl.signal,
          onEvent: (ev) => {
            if (ev.event === "status" && ev.data.thread_id) tid = ev.data.thread_id;
            if (ev.event === "cost_update") addCost(ev.data);
            if (ev.event === "complete") resetCost(ev.data.total_tokens, ev.data.total_cost_usd);
            if (TERMINAL.has(ev.event)) finished = true;
            dispatch({ type: "event", event: ev });
          },
        });
        if (!finished && !ctrl.signal.aborted) dispatch({ type: "fail", message: "Stream kết thúc bất thường." });
      } catch (err) {
        if (!ctrl.signal.aborted) dispatch({ type: "fail", message: errorText(err) });
      } finally {
        if (controller.current === ctrl) controller.current = null;
        if (!ctrl.signal.aborted) settledRef.current?.(tid);
      }
    },
    [addCost, resetCost],
  );

  const send = useCallback(
    (message: string, modelId?: string) => {
      const threadId = threadRef.current;
      return run("/api/v1/agent/chat/stream", { thread_id: threadId, message, model_id: modelId || null }, threadId);
    },
    [run],
  );

  const resume = useCallback(
    (decision: ResumeDecision) => {
      const threadId = threadRef.current;
      if (!threadId) return Promise.resolve();
      return run("/api/v1/agent/chat/resume", { thread_id: threadId, ...decision }, threadId);
    },
    [run],
  );

  /** Mở một thread có sẵn: khôi phục HITL đang chờ + tổng chi phí. null = cuộc trò chuyện mới. */
  const loadThread = useCallback(
    async (threadId: string | null) => {
      controller.current?.abort();
      dispatch({ type: "load", threadId, interrupt: null });
      resetCost();
      if (!threadId) return;
      try {
        const s = await api<ThreadState>(`/api/v1/agent/threads/${encodeURIComponent(threadId)}/state`);
        if (threadRef.current !== threadId) return; // người dùng đã chuyển thread khác
        dispatch({ type: "load", threadId, interrupt: s.pending });
        resetCost(s.total_tokens, s.total_cost_usd);
      } catch (err) {
        dispatch({ type: "fail", message: errorText(err) });
      }
    },
    [resetCost],
  );

  return { ...state, cost, send, resume, loadThread };
}
