"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { ChunkDrawer } from "@/components/documents/ChunkDrawer";
import { IngestPipeline, stallWarning } from "@/components/documents/IngestPipeline";
import { Alert, Badge, Button, Card, Field, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatBytes, formatDateTime } from "@/lib/format";
import type { DocumentItem, DocumentStatus } from "@/types/api";

const STATUS_TONE: Record<DocumentStatus, "neutral" | "accent" | "success" | "danger"> = {
  PENDING: "neutral",
  PROCESSING: "accent",
  READY: "success",
  FAILED: "danger",
};
const MAX_BYTES = 10 * 1024 * 1024;

export default function DocumentsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "ADMIN";
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [source, setSource] = useState<"file" | "url">("file");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [scope, setScope] = useState<"PRIVATE" | "SYSTEM">("PRIVATE");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [viewing, setViewing] = useState<DocumentItem | null>(null);
  const closeViewer = useCallback(() => setViewing(null), []);

  const load = useCallback(async () => {
    try {
      setDocs(await api<DocumentItem[]>("/api/v1/documents"));
    } catch (err) {
      setError(errorText(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Ingest chạy nền: poll tiến độ tới khi không còn tài liệu PENDING / PROCESSING;
  // `now` tick mỗi giây để thời gian chạy và cảnh báo treo cập nhật giữa các lần poll
  const inFlight = docs.some((d) => d.processing_status === "PENDING" || d.processing_status === "PROCESSING");
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!inFlight) return;
    const poll = setInterval(load, 1500);
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [inFlight, load]);

  async function upload(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    const form = new FormData();
    if (source === "file") {
      if (!file) return setError("Chọn một file PDF, DOCX, TXT hoặc MD.");
      if (file.size > MAX_BYTES) return setError("File vượt quá 10MB.");
      form.append("file", file);
    } else {
      if (!url.trim()) return setError("Nhập URL.");
      form.append("url", url.trim());
    }
    form.append("scope", scope);
    setBusy(true);
    try {
      const res = await api<{ title: string; message: string }>("/api/v1/documents/upload", { method: "POST", form });
      setNotice(`${res.title}: ${res.message}`);
      setFile(null);
      setUrl("");
      if (fileInput.current) fileInput.current.value = "";
      await load();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(doc: DocumentItem) {
    if (!window.confirm(`Xóa tài liệu "${doc.title}"? Không thể hoàn tác.`)) return;
    try {
      await api(`/api/v1/admin/documents/${doc.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-4 px-4 py-6">
        <div>
          <h1 className="text-lg font-semibold">Tài liệu RAG</h1>
          <p className="text-sm text-muted">Agent tra cứu các tài liệu này khi soạn dàn ý và đối soát số liệu.</p>
        </div>

        <Card title="Tải tài liệu lên">
          <form onSubmit={upload} className="space-y-3">
            <div className="flex gap-1" role="radiogroup" aria-label="Nguồn">
              {(["file", "url"] as const).map((s) => (
                <Button key={s} variant={source === s ? "primary" : "secondary"} onClick={() => setSource(s)} role="radio" aria-checked={source === s}>
                  {s === "file" ? "File" : "URL"}
                </Button>
              ))}
            </div>
            <div className="grid gap-3 sm:grid-cols-[1fr_180px]">
              {source === "file" ? (
                <Field label="PDF, DOCX, TXT hoặc MD (≤ 10MB)">
                  <input
                    ref={fileInput}
                    type="file"
                    accept=".pdf,.docx,.txt,.md"
                    className={inputClass}
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                </Field>
              ) : (
                <Field label="URL trang web">
                  <input
                    type="url"
                    className={inputClass}
                    placeholder="https://..."
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                  />
                </Field>
              )}
              <Field label="Phạm vi">
                <select className={inputClass} value={scope} onChange={(e) => setScope(e.target.value as "PRIVATE" | "SYSTEM")}>
                  <option value="PRIVATE">Riêng tư</option>
                  {isAdmin && <option value="SYSTEM">Hệ thống (mọi user)</option>}
                </select>
              </Field>
            </div>
            {error && <Alert>{error}</Alert>}
            {notice && <Alert tone="success">{notice}</Alert>}
            <Button type="submit" variant="primary" busy={busy}>
              Tải lên
            </Button>
          </form>
        </Card>

        <Card title={`Tài liệu (${docs.length})`}>
          {docs.length === 0 ? (
            <p className="text-sm text-muted">Chưa có tài liệu nào.</p>
          ) : (
            <ul className="-my-4 divide-y divide-line">
              {docs.map((d) => {
                const warning = stallWarning(d, now);
                return (
                  <li key={d.id} className="space-y-2.5 py-4">
                    <div className="flex flex-wrap items-start gap-x-3 gap-y-1">
                      <div className="min-w-0 flex-1">
                        {d.chunk_count > 0 ? (
                          <button
                            type="button"
                            className="block max-w-full truncate text-left text-sm font-medium hover:text-accent hover:underline"
                            title={`Xem ${d.chunk_count} chunk của ${d.title}`}
                            onClick={() => setViewing(d)}
                          >
                            {d.title}
                          </button>
                        ) : (
                          <div className="truncate text-sm font-medium" title={d.title}>
                            {d.title}
                          </div>
                        )}
                        <div className="text-xs text-muted">
                          {d.file_type} · {formatBytes(d.file_size_bytes)} · {formatDateTime(d.created_at)}
                          {d.processing_status === "READY" && ` · ${d.chunk_count} chunk`}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <Badge tone={d.scope === "SYSTEM" ? "accent" : "neutral"}>{d.scope}</Badge>
                        <Badge tone={STATUS_TONE[d.processing_status]}>{d.processing_status}</Badge>
                        {d.chunk_count > 0 && <Button onClick={() => setViewing(d)}>Xem chunk</Button>}
                        {isAdmin && (
                          <Button variant="danger" onClick={() => remove(d)}>
                            Xóa
                          </Button>
                        )}
                      </div>
                    </div>
                    <IngestPipeline doc={d} now={now} />
                    {warning && <Alert tone={warning.tone}>{warning.text}</Alert>}
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
      {viewing && <ChunkDrawer doc={viewing} onClose={closeViewer} />}
    </div>
  );
}
