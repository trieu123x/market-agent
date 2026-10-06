"use client";

import { useState } from "react";

import { FactCheckPanel } from "@/components/hitl/FactCheckPanel";
import { PlatformTabs } from "@/components/hitl/PlatformTabs";
import { RagSourcesPanel } from "@/components/hitl/RagSourcesPanel";
import { Badge } from "@/components/ui";
import { Markdown } from "@/components/ui/Markdown";
import type { ThreadMessage } from "@/types/api";
import type { Drafts, FactCheckReport, Platform, RagSource } from "@/types/events";

const DECISION_LABELS: Record<string, string> = {
  APPROVE: "Đã duyệt",
  EDIT: "Đã sửa & duyệt",
  REJECT: "Đã từ chối",
};
const STAGE_LABELS: Record<string, string> = {
  OUTLINE_APPROVAL: "dàn ý",
  DRAFTS_APPROVAL: "bản thảo",
};

function parseJson<T>(s: string): T | null {
  try {
    return JSON.parse(s) as T;
  } catch {
    return null;
  }
}

export function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-lg bg-accent px-3 py-2 text-sm whitespace-pre-wrap text-accent-fg">{text}</div>
    </div>
  );
}

function AssistantCard({ title, badge, children }: { title: string; badge?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-panel">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2 text-sm font-medium">
        {title}
        {badge}
      </div>
      <div className="px-4 py-3">{children}</div>
    </div>
  );
}

export function DraftsCard({ drafts, title, badge }: { drafts: Drafts; title: string; badge?: React.ReactNode }) {
  const [active, setActive] = useState<Platform>("linkedin");
  return (
    <AssistantCard title={title} badge={badge}>
      <PlatformTabs active={active} onChange={setActive} />
      <div className="pt-3">
        <Markdown>{drafts[active] ?? ""}</Markdown>
      </div>
    </AssistantCard>
  );
}

export function HistoryMessage({ msg }: { msg: ThreadMessage }) {
  if (msg.sender_role === "USER") return <UserBubble text={msg.content} />;

  if (msg.sender_role === "HUMAN_INTERRUPT") {
    const meta = msg.metadata as { stage?: string; feedback?: string; updated_outline?: string };
    return (
      <div className="text-center text-xs text-muted">
        <p>
          {DECISION_LABELS[msg.content] ?? msg.content} {STAGE_LABELS[meta.stage ?? ""] ?? ""}
          {meta.feedback ? ` – “${meta.feedback}”` : ""}
        </p>
        {meta.updated_outline && (
          <details className="mt-2 text-left">
            <summary className="cursor-pointer text-center">Xem dàn ý đã sửa</summary>
            <div className="mt-2 rounded-lg border border-line bg-panel px-4 py-3 text-fg">
              <Markdown>{meta.updated_outline}</Markdown>
            </div>
          </details>
        )}
      </div>
    );
  }

  if (msg.sender_role === "SYSTEM") {
    return <div className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger">{msg.content}</div>;
  }

  switch (msg.content_type) {
    case "OUTLINE_CARD": {
      // Tin nhắn cũ (trước khi lưu sources) không có field này → ẩn hẳn panel
      const sources = msg.metadata.sources as RagSource[] | undefined;
      return (
        <AssistantCard title="Dàn ý chiến dịch">
          <Markdown>{msg.content}</Markdown>
          {sources && (
            <div className="mt-3">
              <RagSourcesPanel sources={sources} />
            </div>
          )}
        </AssistantCard>
      );
    }
    case "DRAFTS_CARD": {
      const drafts = parseJson<Drafts>(msg.content);
      if (!drafts) return null;
      const final = Boolean(msg.metadata.final);
      return (
        <DraftsCard
          drafts={drafts}
          title={final ? "Bản thảo cuối" : "Bản thảo chờ duyệt"}
          badge={final ? <Badge tone="success">✓ Đã chốt</Badge> : undefined}
        />
      );
    }
    case "FACT_CHECK_REPORT": {
      const report = parseJson<FactCheckReport>(msg.content);
      return (
        <AssistantCard title="Báo cáo fact-check">
          <FactCheckPanel report={report} />
        </AssistantCard>
      );
    }
    default:
      return (
        <AssistantCard title="Agent">
          <Markdown>{msg.content}</Markdown>
        </AssistantCard>
      );
  }
}
