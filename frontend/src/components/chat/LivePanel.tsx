"use client";

import { useState } from "react";

import { PlatformTabs } from "@/components/hitl/PlatformTabs";
import { Badge, Spinner } from "@/components/ui";
import { Markdown } from "@/components/ui/Markdown";
import { PLATFORMS, type Drafts, type KnowledgeNeed, type Platform, type StatusEvent } from "@/types/events";

const STEPS = [
  ["INPUT_GUARDRAIL", "An toàn"],
  ["ANALYZING_BRIEF", "Phân tích"],
  ["RAG_RETRIEVAL", "Tra cứu"],
  ["GENERATING_OUTLINE", "Dàn ý"],
  ["GENERATING_DRAFTS", "Bản thảo"],
  ["FACT_CHECKING", "Fact-check"],
  ["REFINING_DRAFTS", "Tự sửa"],
  ["FINALIZING", "Lưu"],
] as const;

interface Props {
  status: StatusEvent | null;
  needs: KnowledgeNeed[] | null;
  outline: string;
  drafts: Drafts;
  streaming: boolean;
}

/** Nội dung đang stream của lượt hiện tại: tiến trình các bước + token dàn ý / bản thảo. */
export function LivePanel({ status, needs, outline, drafts, streaming }: Props) {
  const [picked, setPicked] = useState<Platform | null>(null);
  const hasDrafts = PLATFORMS.some((p) => drafts[p]);
  // Mặc định bám theo kênh đang nhận token cuối cùng có nội dung
  const active = picked ?? PLATFORMS.findLast((p) => drafts[p]) ?? "facebook";
  const currentIdx = STEPS.findIndex(([step]) => step === status?.step);

  return (
    <div className="space-y-3">
      {streaming && (
        <div className="rounded-lg border border-line bg-panel px-4 py-3">
          <div className="flex items-center gap-2 text-sm">
            <Spinner className="text-accent" />
            <span>{status?.message ?? "Đang kết nối..."}</span>
          </div>
          <ol className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs" aria-label="Tiến trình">
            {STEPS.map(([step, label], i) => (
              <li
                key={step}
                className={i === currentIdx ? "font-medium text-accent" : i < currentIdx ? "text-fg" : "text-muted"}
              >
                {i < currentIdx ? "✓ " : ""}
                {label}
              </li>
            ))}
          </ol>
        </div>
      )}
      {needs && (
        <div className="rounded-lg border border-line bg-panel px-4 py-3">
          <div className="mb-2 text-sm font-medium">Phân tích brief</div>
          {needs.length === 0 ? (
            <p className="text-sm text-muted">Không xác định thêm kỹ năng/kiến thức nào – tra cứu theo brief gốc.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {needs.map((n, i) => (
                <li key={i}>
                  <Badge tone={n.kind === "skill" ? "accent" : "neutral"}>{n.kind === "skill" ? "Kỹ năng" : "Kiến thức"}</Badge>{" "}
                  <span className="font-medium">{n.name}</span>
                  {n.why && <span className="text-muted"> – {n.why}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {outline && (
        <div className="rounded-lg border border-line bg-panel px-4 py-3">
          <div className="mb-2 text-sm font-medium">Dàn ý chiến dịch</div>
          <Markdown streaming={streaming && !hasDrafts}>{outline}</Markdown>
        </div>
      )}
      {hasDrafts && (
        <div className="rounded-lg border border-line bg-panel px-4 py-3">
          <PlatformTabs active={active} onChange={setPicked} />
          <div className="pt-3">
            <Markdown streaming={streaming}>{drafts[active]}</Markdown>
          </div>
        </div>
      )}
    </div>
  );
}
