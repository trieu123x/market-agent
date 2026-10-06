"use client";

import { useEffect, useState } from "react";

import { Badge, Button, inputClass } from "@/components/ui";
import { Markdown } from "@/components/ui/Markdown";
import { PLATFORMS, type Drafts, type DraftsInterrupt, type Platform, type ResumeDecision } from "@/types/events";
import { FactCheckPanel, issuesByPlatform } from "./FactCheckPanel";
import { overlongThreadPosts, PlatformTabs } from "./PlatformTabs";

interface Props {
  interrupt: DraftsInterrupt;
  busy: boolean;
  onDecision: (d: ResumeDecision) => void;
}

/** HITL 2: 3 tab bản thảo (sửa trực tiếp được) + báo cáo fact-check để đối chiếu trước khi chốt. */
export function DraftsApprovalView({ interrupt, busy, onDecision }: Props) {
  const original = interrupt.data.drafts;
  const report = interrupt.data.fact_check_report;
  const [active, setActive] = useState<Platform>("facebook");
  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState<Drafts>(original);

  useEffect(() => {
    setDrafts(original);
    setEditing(false);
  }, [original]);

  const changed = PLATFORMS.filter((p) => drafts[p] !== original[p]);
  const counts = issuesByPlatform(report);
  const notes = Object.fromEntries(
    PLATFORMS.map((p) => [p, changed.includes(p) ? "• đã sửa" : counts[p] ? `(${counts[p]})` : ""]),
  );
  const tooLong = active === "threads" ? overlongThreadPosts(drafts.threads) : 0;

  function approve() {
    if (changed.length === 0) {
      onDecision({ stage: "DRAFTS_APPROVAL", action: "APPROVE" });
    } else {
      const updated = Object.fromEntries(changed.map((p) => [p, drafts[p]]));
      onDecision({ stage: "DRAFTS_APPROVAL", action: "EDIT", updated_drafts: updated });
    }
  }

  return (
    <section className="rounded-lg border border-accent/40 bg-panel" aria-label="Duyệt bản thảo">
      <header className="border-b border-line px-4 py-3">
        <h2 className="font-semibold">Duyệt bản thảo đa kênh</h2>
        <p className="text-sm text-muted">{interrupt.message}</p>
      </header>

      <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 border-line lg:border-r">
          <div className="px-4 pt-2">
            <PlatformTabs active={active} onChange={setActive} notes={notes} />
          </div>
          <div className="p-4">
            {editing ? (
              <textarea
                className={`${inputClass} min-h-72 font-mono`}
                value={drafts[active]}
                onChange={(e) => setDrafts({ ...drafts, [active]: e.target.value })}
                aria-label={`Sửa bản thảo ${active}`}
              />
            ) : (
              <Markdown>{drafts[active]}</Markdown>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
              <span>{[...drafts[active]].length} ký tự</span>
              {tooLong > 0 && <Badge tone="warning">{tooLong} bài vượt 500 ký tự</Badge>}
              {changed.includes(active) && (
                <button
                  type="button"
                  className="text-accent hover:underline"
                  onClick={() => setDrafts({ ...drafts, [active]: original[active] })}
                >
                  Hoàn tác kênh này
                </button>
              )}
            </div>
          </div>
        </div>
        <aside className="border-t border-line p-4 lg:border-t-0">
          <h3 className="mb-2 text-sm font-semibold">Fact-check</h3>
          <FactCheckPanel report={report} focus={active} />
        </aside>
      </div>

      <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-line px-4 py-3">
        {changed.length > 0 && <span className="mr-auto text-xs text-muted">Đã sửa {changed.length} kênh</span>}
        <Button onClick={() => setEditing(!editing)} disabled={busy}>
          {editing ? "Xem trước" : "Sửa trực tiếp"}
        </Button>
        <Button variant="primary" busy={busy} onClick={approve}>
          {changed.length ? "Lưu chỉnh sửa & chốt" : "Duyệt & chốt bản thảo"}
        </Button>
      </footer>
    </section>
  );
}
