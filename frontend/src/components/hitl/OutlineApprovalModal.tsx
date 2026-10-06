"use client";

import { useEffect, useState } from "react";

import { RagSourcesPanel } from "@/components/hitl/RagSourcesPanel";
import { Button, inputClass } from "@/components/ui";
import { Markdown } from "@/components/ui/Markdown";
import type { OutlineInterrupt, ResumeDecision } from "@/types/events";

type Mode = "view" | "edit" | "reject";

interface Props {
  interrupt: OutlineInterrupt;
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onDecision: (d: ResumeDecision) => void;
}

/** HITL 1: Approve / Edit inline (Markdown) / Reject kèm lý do. */
export function OutlineApprovalModal({ interrupt, open, busy, onClose, onDecision }: Props) {
  const outline = interrupt.data.outline;
  const [mode, setMode] = useState<Mode>("view");
  const [text, setText] = useState(outline);
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    setMode("view");
    setText(outline);
    setFeedback("");
  }, [outline]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  const edited = text.trim() !== outline.trim();

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="outline-modal-title"
        className="flex max-h-[92dvh] w-full max-w-3xl flex-col rounded-t-xl bg-panel shadow-xl sm:rounded-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-3">
          <div>
            <h2 id="outline-modal-title" className="font-semibold">
              Duyệt dàn ý chiến dịch
            </h2>
            <p className="text-sm text-muted">{interrupt.message}</p>
          </div>
          <Button variant="ghost" onClick={onClose} aria-label="Đóng">
            ✕
          </Button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {mode === "edit" ? (
            <textarea
              className={`${inputClass} min-h-[50dvh] font-mono`}
              value={text}
              onChange={(e) => setText(e.target.value)}
              aria-label="Sửa dàn ý (Markdown)"
              autoFocus
            />
          ) : (
            <Markdown>{outline}</Markdown>
          )}
          {interrupt.data.sources && (
            <div className="mt-4">
              <RagSourcesPanel sources={interrupt.data.sources} />
            </div>
          )}
          {mode === "reject" && (
            <div className="mt-4 space-y-1">
              <label htmlFor="reject-feedback" className="text-sm text-muted">
                Lý do từ chối – agent sẽ tra cứu lại và đề xuất hướng khác
              </label>
              <textarea
                id="reject-feedback"
                className={`${inputClass} min-h-24`}
                value={feedback}
                maxLength={4000}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="VD: Tập trung vào khách hàng SME, bỏ phần influencer..."
                autoFocus
              />
            </div>
          )}
        </div>

        <footer className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">
          {mode === "view" && (
            <>
              <Button variant="danger" onClick={() => setMode("reject")} disabled={busy}>
                Từ chối
              </Button>
              <Button onClick={() => setMode("edit")} disabled={busy}>
                Sửa trực tiếp
              </Button>
              <Button variant="primary" busy={busy} onClick={() => onDecision({ stage: "OUTLINE_APPROVAL", action: "APPROVE" })}>
                Duyệt dàn ý
              </Button>
            </>
          )}
          {mode === "edit" && (
            <>
              <Button variant="ghost" onClick={() => { setMode("view"); setText(outline); }} disabled={busy}>
                Hủy sửa
              </Button>
              <Button
                variant="primary"
                busy={busy}
                disabled={!text.trim()}
                onClick={() =>
                  onDecision(
                    edited
                      ? { stage: "OUTLINE_APPROVAL", action: "EDIT", updated_outline: text }
                      : { stage: "OUTLINE_APPROVAL", action: "APPROVE" },
                  )
                }
              >
                {edited ? "Lưu & duyệt" : "Duyệt (không đổi)"}
              </Button>
            </>
          )}
          {mode === "reject" && (
            <>
              <Button variant="ghost" onClick={() => setMode("view")} disabled={busy}>
                Quay lại
              </Button>
              <Button
                variant="primary"
                busy={busy}
                onClick={() =>
                  onDecision({ stage: "OUTLINE_APPROVAL", action: "REJECT", feedback: feedback.trim() || undefined })
                }
              >
                Gửi & tạo lại dàn ý
              </Button>
            </>
          )}
        </footer>
      </div>
    </div>
  );
}
