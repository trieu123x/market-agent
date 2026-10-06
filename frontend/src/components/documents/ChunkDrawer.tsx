"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Badge, Button, inputClass, Spinner } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { formatInt } from "@/lib/format";
import type { DocumentChunk, DocumentChunkPage, DocumentItem } from "@/types/api";

const PAGE_SIZE = 50;

interface Props {
  doc: DocumentItem;
  onClose: () => void;
}

/** Panel bên phải: các chunk đã lưu của một tài liệu, đúng nội dung agent tra cứu khi RAG. */
export function ChunkDrawer({ doc, onClose }: Props) {
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const loadPage = useCallback(
    async (offset: number) => {
      setLoading(true);
      setError(null);
      try {
        const page = await api<DocumentChunkPage>(
          `/api/v1/documents/${doc.id}/chunks?offset=${offset}&limit=${PAGE_SIZE}`,
        );
        setTotal(page.total);
        setChunks((prev) => (offset === 0 ? page.items : [...prev, ...page.items]));
      } catch (err) {
        setError(errorText(err));
      } finally {
        setLoading(false);
      }
    },
    [doc.id],
  );

  useEffect(() => {
    setChunks([]);
    setTotal(null);
    setQuery("");
    void loadPage(0);
  }, [loadPage]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const q = query.trim().toLowerCase();
  const shown = useMemo(
    () =>
      q
        ? chunks.filter(
            (c) => c.content.toLowerCase().includes(q) || (c.metadata.headings ?? []).some((h) => h.toLowerCase().includes(q)),
          )
        : chunks,
    [chunks, q],
  );
  const totalTokens = chunks.reduce((s, c) => s + (c.metadata.token_count ?? 0), 0);
  const hasMore = total !== null && chunks.length < total;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="chunk-drawer-title"
        className="flex h-full w-full max-w-2xl flex-col bg-panel shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start gap-3 border-b border-line px-5 py-3">
          <div className="min-w-0 flex-1">
            <h2 id="chunk-drawer-title" className="truncate font-semibold" title={doc.title}>
              {doc.title}
            </h2>
            <p className="text-xs text-muted tabular-nums">
              {total === null ? "Đang tải…" : `${formatInt(total)} chunk`}
              {chunks.length > 0 && ` · ${formatInt(totalTokens)} token${hasMore ? " (đã tải)" : ""}`}
              {chunks[0]?.metadata.embedding_model && ` · ${chunks[0].metadata.embedding_model}`}
            </p>
          </div>
          <Button variant="ghost" onClick={onClose} aria-label="Đóng">
            ✕
          </Button>
        </header>

        <div className="border-b border-line px-5 py-2.5">
          <input
            className={inputClass}
            type="search"
            placeholder={hasMore ? "Lọc trong các chunk đã tải…" : "Lọc theo nội dung hoặc tiêu đề…"}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Lọc chunk"
          />
          {q && (
            <p className="mt-1 text-xs text-muted">
              {shown.length}/{chunks.length} chunk khớp
            </p>
          )}
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {error && <Alert>{error}</Alert>}
          {total === 0 && !loading && <p className="text-sm text-muted">Tài liệu này chưa có chunk nào.</p>}
          {shown.map((c) => (
            <article key={c.id} className="rounded-lg border border-line">
              <header className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-line bg-panel-2 px-3 py-1.5 text-xs">
                <Badge tone="accent">#{c.chunk_index}</Badge>
                {c.metadata.token_count != null && (
                  <span className="text-muted tabular-nums">{c.metadata.token_count} token</span>
                )}
                {(c.metadata.headings ?? []).length > 0 && (
                  <span className="min-w-0 truncate text-muted" title={c.metadata.headings!.join(" › ")}>
                    {c.metadata.headings!.join(" › ")}
                  </span>
                )}
              </header>
              <pre className="overflow-x-auto px-3 py-2.5 font-sans text-sm leading-relaxed whitespace-pre-wrap">
                {highlight(c.content, q)}
              </pre>
            </article>
          ))}
          {loading && (
            <div className="flex justify-center py-4 text-muted">
              <Spinner />
            </div>
          )}
          {hasMore && !loading && (
            <Button className="w-full" onClick={() => loadPage(chunks.length)}>
              Tải thêm ({formatInt(total! - chunks.length)} chunk)
            </Button>
          )}
        </div>
      </aside>
    </div>
  );
}

/** Tô đậm các đoạn khớp từ khóa lọc. */
function highlight(text: string, q: string) {
  if (!q) return text;
  const parts: (string | React.ReactElement)[] = [];
  const lower = text.toLowerCase();
  let i = 0;
  for (let at = lower.indexOf(q); at !== -1; at = lower.indexOf(q, i)) {
    parts.push(text.slice(i, at));
    parts.push(
      <mark key={at} className="rounded bg-warning-soft px-0.5 text-fg">
        {text.slice(at, at + q.length)}
      </mark>,
    );
    i = at + q.length;
  }
  parts.push(text.slice(i));
  return parts;
}
