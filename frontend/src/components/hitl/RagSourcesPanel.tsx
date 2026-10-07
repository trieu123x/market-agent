"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui";
import type { RagSource } from "@/types/events";

const OPEN_KEY = "market_agent_rag_sources_open";
const RANK_LABELS = { vector: "Ngữ nghĩa", fts: "Từ khóa" } as const;

function readOpen(): boolean {
  try {
    return localStorage.getItem(OPEN_KEY) === "1";
  } catch {
    return false;
  }
}

/** Danh sách chunk agent đã tra cứu khi soạn dàn ý; bật/tắt được, nhớ lựa chọn theo trình duyệt. */
export function RagSourcesPanel({ sources }: { sources: RagSource[] }) {
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(readOpen()), []);

  function toggle() {
    const next = !open;
    setOpen(next);
    try {
      localStorage.setItem(OPEN_KEY, next ? "1" : "0");
    } catch {
      // storage bị chặn: chỉ nhớ trong phiên
    }
  }

  return (
    <section className="rounded-lg border border-line">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium hover:bg-panel-2"
      >
        <span aria-hidden className={`text-xs text-muted transition-transform ${open ? "rotate-90" : ""}`}>
          ▶
        </span>
        <span className="flex-1">Tài liệu đã tra cứu</span>
        <Badge tone={sources.length ? "accent" : "neutral"}>{sources.length} chunk</Badge>
      </button>
      {open && (
        <div className="space-y-2 border-t border-line px-3 py-3">
          {sources.length === 0 ? (
            <p className="text-sm text-muted">
              Không tìm thấy chunk nào liên quan – dàn ý được soạn chỉ dựa trên brief.
            </p>
          ) : (
            sources.map((s) => <SourceItem key={s.chunk_id} source={s} />)
          )}
        </div>
      )}
    </section>
  );
}

function SourceItem({ source: s }: { source: RagSource }) {
  const [expanded, setExpanded] = useState(false);
  const path = s.headings.join(" › ");
  return (
    <article className="rounded-md border border-line">
      <header className="space-y-1 border-b border-line bg-panel-2 px-3 py-1.5 text-xs">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Badge tone="accent">[{s.ref}]</Badge>
          <span className="min-w-0 flex-1 truncate font-medium text-fg" title={s.document_title}>
            {s.document_title}
          </span>
          <span className="text-muted tabular-nums">đoạn #{s.chunk_index}</span>
        </div>
        {!!s.needs?.length && (
          <div className="flex flex-wrap items-center gap-1">
            <span className="text-muted">Phục vụ:</span>
            {s.needs.map((n) => (
              <Badge key={n} tone="neutral">
                {n}
              </Badge>
            ))}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-muted">
          {(Object.keys(RANK_LABELS) as (keyof typeof RANK_LABELS)[]).map(
            (k) =>
              s.ranks[k] != null && (
                <span key={k} className="tabular-nums">
                  {RANK_LABELS[k]} #{s.ranks[k]}
                </span>
              ),
          )}
          <span className="tabular-nums" title="Điểm RRF (gộp ngữ nghĩa + từ khóa)">
            RRF {s.score.toFixed(4)}
          </span>
          {path && (
            <span className="min-w-0 truncate" title={path}>
              · {path}
            </span>
          )}
        </div>
      </header>
      <pre
        className={`px-3 py-2 font-sans text-sm leading-relaxed whitespace-pre-wrap ${expanded ? "" : "line-clamp-4"}`}
      >
        {s.content}
      </pre>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="w-full border-t border-line px-3 py-1 text-xs text-muted hover:bg-panel-2 hover:text-fg"
      >
        {expanded ? "Thu gọn" : "Xem đầy đủ"}
      </button>
    </article>
  );
}
