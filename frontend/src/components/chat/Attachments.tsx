"use client";

import { useState } from "react";

import { Spinner } from "@/components/ui";
import { Markdown } from "@/components/ui/Markdown";
import type { ChatAttachment } from "@/types/api";

/** Tệp trong khung soạn: đang upload / đã trích nội dung / lỗi. */
export interface ComposerFile {
  key: string;
  name: string;
  status: "uploading" | "ready" | "error";
  result?: ChatAttachment;
  error?: string;
}

const icon = (kind: ChatAttachment["kind"] | undefined) => (kind === "image" ? "🖼" : "📄");

function Chip({
  label,
  kind,
  active,
  tone = "neutral",
  busy,
  title,
  onClick,
  onRemove,
}: {
  label: string;
  kind?: ChatAttachment["kind"];
  active?: boolean;
  tone?: "neutral" | "danger";
  busy?: boolean;
  title?: string;
  onClick?: () => void;
  onRemove?: () => void;
}) {
  const color =
    tone === "danger"
      ? "border-danger/40 bg-danger-soft text-danger"
      : active
        ? "border-accent bg-accent-soft text-fg"
        : "border-line bg-panel text-fg";
  return (
    <span className={`inline-flex max-w-full items-center gap-1 rounded-md border text-xs ${color}`} title={title}>
      <button
        type="button"
        className="flex min-w-0 items-center gap-1 px-2 py-1 disabled:cursor-default"
        onClick={onClick}
        disabled={!onClick}
        aria-expanded={onClick ? active : undefined}
      >
        {busy ? <Spinner /> : <span aria-hidden>{icon(kind)}</span>}
        <span className="truncate">{label}</span>
      </button>
      {onRemove && (
        <button
          type="button"
          className="px-1.5 py-1 text-muted hover:text-fg"
          onClick={onRemove}
          aria-label={`Bỏ ${label}`}
        >
          ✕
        </button>
      )}
    </span>
  );
}

function Preview({ att }: { att: ChatAttachment }) {
  return (
    <div className="mt-2 max-h-64 overflow-y-auto rounded-md border border-line bg-panel px-3 py-2 text-left text-sm text-fg">
      <p className="mb-1 text-xs text-muted">
        {att.kind === "image" ? "Mô tả ảnh do Gemini phân tích" : "Nội dung trích từ tài liệu"}
        {att.truncated ? " · đã cắt bớt phần cuối" : ""}
      </p>
      {att.kind === "image" ? (
        <Markdown>{att.text}</Markdown>
      ) : (
        <pre className="text-xs whitespace-pre-wrap">{att.text}</pre>
      )}
    </div>
  );
}

/** Danh sách tệp đã gửi (trong bong bóng tin nhắn): bấm để xem nội dung agent nhận được. */
export function AttachmentList({ items }: { items: ChatAttachment[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!items.length) return null;
  return (
    <div className="w-full">
      <div className="flex flex-wrap justify-end gap-1.5">
        {items.map((a, i) => (
          <Chip
            key={i}
            label={a.filename}
            kind={a.kind}
            active={open === i}
            onClick={() => setOpen(open === i ? null : i)}
          />
        ))}
      </div>
      {open !== null && items[open] && <Preview att={items[open]} />}
    </div>
  );
}

/** Tệp trong khung soạn, có nút bỏ. */
export function ComposerFiles({ files, onRemove }: { files: ComposerFile[]; onRemove: (key: string) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!files.length) return null;
  const opened = files.find((f) => f.key === open)?.result;
  return (
    <div className="mb-2">
      <div className="flex flex-wrap gap-1.5">
        {files.map((f) => (
          <Chip
            key={f.key}
            label={f.status === "uploading" ? `${f.name} – đang phân tích…` : f.name}
            kind={f.result?.kind}
            busy={f.status === "uploading"}
            tone={f.status === "error" ? "danger" : "neutral"}
            title={f.error}
            active={open === f.key}
            onClick={f.result ? () => setOpen(open === f.key ? null : f.key) : undefined}
            onRemove={() => onRemove(f.key)}
          />
        ))}
      </div>
      {files
        .filter((f) => f.status === "error")
        .map((f) => (
          <p key={f.key} className="mt-1 text-xs text-danger">
            {f.name}: {f.error}
          </p>
        ))}
      {opened && <Preview att={opened} />}
    </div>
  );
}
