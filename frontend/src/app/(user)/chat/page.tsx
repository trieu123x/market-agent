"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ChatWindow } from "@/components/chat/ChatWindow";
import { CostBar } from "@/components/chat/CostBar";
import { LivePanel } from "@/components/chat/LivePanel";
import { ThreadSidebar } from "@/components/chat/ThreadSidebar";
import { DraftsApprovalView } from "@/components/hitl/DraftsApprovalView";
import { OutlineApprovalModal } from "@/components/hitl/OutlineApprovalModal";
import { Alert, Button } from "@/components/ui";
import { useAgentStream } from "@/hooks/useAgentStream";
import { api, errorText } from "@/lib/api";
import type { ModelOption, Thread, ThreadMessage } from "@/types/api";
import type { ResumeDecision } from "@/types/events";

/** Đồng bộ ?thread= trên URL để reload trang vẫn mở đúng chiến dịch. */
function writeThreadParam(id: string | null) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set("thread", id);
  else url.searchParams.delete("thread");
  window.history.replaceState(null, "", url);
}

export default function ChatPage() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [history, setHistory] = useState<ThreadMessage[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelId, setModelId] = useState("");
  const [pendingUserText, setPendingUserText] = useState<string | null>(null);
  // Giữ phần đang stream trên màn hình tới khi lịch sử từ server đã tải xong (tránh nháy)
  const [syncing, setSyncing] = useState(false);
  const [outlineOpen, setOutlineOpen] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [runKey, setRunKey] = useState(0);
  const viewing = useRef<string | null>(null);

  const loadThreads = useCallback(async () => {
    try {
      setThreads(await api<Thread[]>("/api/v1/agent/threads"));
    } catch (err) {
      setLoadError(errorText(err));
    }
  }, []);

  const loadHistory = useCallback(async (threadId: string) => {
    try {
      const msgs = await api<ThreadMessage[]>(`/api/v1/agent/threads/${encodeURIComponent(threadId)}/messages`);
      if (viewing.current === threadId) setHistory(msgs);
    } catch (err) {
      setLoadError(errorText(err));
    }
  }, []);

  const onSettled = useCallback(
    async (threadId: string | null) => {
      if (threadId) {
        viewing.current = threadId;
        writeThreadParam(threadId);
        await Promise.all([loadHistory(threadId), loadThreads()]);
      }
      setPendingUserText(null);
      setSyncing(false);
    },
    [loadHistory, loadThreads],
  );

  const agent = useAgentStream({ onSettled });
  const { loadThread, send, resume } = agent;

  const openThread = useCallback(
    (threadId: string | null) => {
      viewing.current = threadId;
      writeThreadParam(threadId);
      setHistory([]);
      setLoadError(null);
      setOutlineOpen(true);
      setSidebarOpen(false);
      void loadThread(threadId);
      if (threadId) void loadHistory(threadId);
    },
    [loadThread, loadHistory],
  );

  useEffect(() => {
    void loadThreads();
    api<ModelOption[]>("/api/v1/agent/models")
      .then((list) => {
        setModels(list);
        setModelId((list.find((m) => m.is_default && m.available) ?? list.find((m) => m.available))?.model_id ?? "");
      })
      .catch((err) => setLoadError(errorText(err)));
    const initial = new URLSearchParams(window.location.search).get("thread");
    if (initial) openThread(initial);
  }, [loadThreads, openThread]);

  const streaming = agent.phase === "streaming";
  const busy = streaming || syncing;

  function handleSend(text: string) {
    setPendingUserText(text);
    setSyncing(true);
    setRunKey((k) => k + 1);
    void send(text, modelId);
  }

  function handleDecision(decision: ResumeDecision) {
    setSyncing(true);
    setRunKey((k) => k + 1);
    setOutlineOpen(true);
    void resume(decision);
  }

  const interrupt = agent.interrupt;
  const awaitingOutline = agent.phase === "awaiting_outline" && interrupt?.stage === "OUTLINE_APPROVAL";
  const awaitingDrafts = agent.phase === "awaiting_drafts" && interrupt?.stage === "DRAFTS_APPROVAL";

  const footer = (
    <>
      {agent.phase === "error" && agent.error && <Alert>{agent.error}</Alert>}
      {loadError && <Alert>{loadError}</Alert>}
      {awaitingOutline && !outlineOpen && !busy && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-accent/40 bg-accent-soft px-4 py-3 text-sm">
          <span>Dàn ý đang chờ bạn duyệt.</span>
          <Button variant="primary" onClick={() => setOutlineOpen(true)}>
            Mở khung duyệt
          </Button>
        </div>
      )}
      {awaitingDrafts && !syncing && <DraftsApprovalView interrupt={interrupt} busy={busy} onDecision={handleDecision} />}
    </>
  );

  const composerHint = awaitingOutline
    ? "Hãy duyệt dàn ý trước khi gửi brief mới"
    : awaitingDrafts
      ? "Hãy duyệt bản thảo trước khi gửi brief mới"
      : undefined;

  return (
    <div className="relative flex h-full">
      <aside
        className={`${sidebarOpen ? "fixed inset-y-0 left-0 z-40 flex shadow-xl" : "hidden"} w-64 shrink-0 flex-col border-r border-line bg-panel md:static md:flex md:shadow-none`}
      >
        <ThreadSidebar
          threads={threads}
          activeId={agent.threadId}
          disabled={busy}
          onSelect={openThread}
          onNew={() => openThread(null)}
        />
      </aside>
      {sidebarOpen && <div className="fixed inset-0 z-30 bg-black/30 md:hidden" onClick={() => setSidebarOpen(false)} />}

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b border-line bg-panel px-4 py-2">
          <Button variant="ghost" className="md:hidden" onClick={() => setSidebarOpen(true)}>
            ☰ Lịch sử
          </Button>
          <select
            className="max-w-[60vw] rounded-md border border-line bg-panel px-2 py-1 text-sm text-fg focus:border-accent focus:outline-none disabled:opacity-60 sm:max-w-xs"
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            disabled={busy || awaitingOutline || awaitingDrafts}
            aria-label="Model"
          >
            {models.map((m) => (
              <option key={m.model_id} value={m.model_id} disabled={!m.available}>
                {m.model_id}
                {m.is_default ? " (mặc định)" : ""}
                {m.available ? "" : " – thiếu API key"}
              </option>
            ))}
          </select>
          <div className="ml-auto">
            <CostBar cost={agent.cost} />
          </div>
        </div>

        <div className="min-h-0 flex-1">
          <ChatWindow
            history={history}
            pendingUserText={pendingUserText}
            live={
              busy ? (
                <LivePanel
                  key={runKey}
                  status={agent.status}
                  outline={agent.outline}
                  drafts={agent.drafts}
                  streaming={streaming}
                />
              ) : null
            }
            footer={footer}
            composerDisabled={busy || awaitingOutline || awaitingDrafts || !modelId}
            composerHint={!modelId && models.length > 0 ? "Chưa có model nào dùng được (thiếu API key)" : composerHint}
            onSend={handleSend}
          />
        </div>
      </main>

      {awaitingOutline && !busy && (
        <OutlineApprovalModal
          interrupt={interrupt}
          open={outlineOpen}
          busy={busy}
          onClose={() => setOutlineOpen(false)}
          onDecision={handleDecision}
        />
      )}
    </div>
  );
}
