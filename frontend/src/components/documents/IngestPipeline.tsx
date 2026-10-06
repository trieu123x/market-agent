import type { DocumentItem, IngestStep, IngestStepName } from "@/types/api";
import { INGEST_STEPS } from "@/types/api";

const LABELS: Record<IngestStepName, string> = {
  parse: "Parse",
  chunk: "Chunk",
  embed: "Embed",
  save: "Lưu DB",
};

// Ngưỡng cảnh báo treo (giây)
const PENDING_WARN_S = 20; // chưa worker nào nhận task
const HEARTBEAT_WARN_S = 20; // worker ghi heartbeat mỗi 5s
const STALL_WARN_S = 45; // bước đang chạy không tiến triển

const seconds = (from: string | null | undefined, to: number) =>
  from ? Math.max(0, (to - new Date(from).getTime()) / 1000) : null;

export function formatDuration(s: number): string {
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0).replace(".", ",")}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s % 60)}s`;
}

function stepDuration(step: IngestStep, now: number): number | null {
  if (!step.started_at) return null;
  const end = step.finished_at ? new Date(step.finished_at).getTime() : now;
  return Math.max(0, (end - new Date(step.started_at).getTime()) / 1000);
}

function StepBar({ step }: { step: IngestStep }) {
  const pct = step.total ? Math.min(100, ((step.done ?? 0) / step.total) * 100) : null;
  const fill =
    step.status === "failed"
      ? "bg-danger w-full"
      : step.status === "done"
        ? "bg-success w-full"
        : step.status === "running"
          ? pct === null
            ? "bg-accent bar-indeterminate"
            : "bg-accent"
          : "w-0";
  return (
    <div
      className="h-1.5 overflow-hidden rounded-full bg-panel-2"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={step.total ?? undefined}
      aria-valuenow={step.total ? (step.done ?? 0) : undefined}
    >
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${fill}`}
        style={step.status === "running" && pct !== null ? { width: `${Math.max(pct, 2)}%` } : undefined}
      />
    </div>
  );
}

function stepText(step: IngestStep, now: number): string {
  const count = step.total != null ? `${step.done ?? 0}/${step.total}${step.unit ? ` ${step.unit}` : ""}` : null;
  const dur = stepDuration(step, now);
  switch (step.status) {
    case "pending":
      return "Chờ";
    case "running":
      return [step.detail ?? count ?? "Đang chạy", dur != null ? formatDuration(dur) : null].filter(Boolean).join(" · ");
    case "done":
      return [count, dur != null ? formatDuration(dur) : null].filter(Boolean).join(" · ") || "Xong";
    case "failed":
      return `Lỗi${dur != null ? ` sau ${formatDuration(dur)}` : ""}`;
  }
}

const STATUS_ICON: Record<IngestStep["status"], string> = { pending: "○", running: "●", done: "✓", failed: "✕" };
const STATUS_COLOR: Record<IngestStep["status"], string> = {
  pending: "text-muted",
  running: "text-accent",
  done: "text-success",
  failed: "text-danger",
};

/** Cảnh báo chỉ ra pipeline đang kẹt ở đâu, hoặc null nếu mọi thứ bình thường. */
export function stallWarning(doc: DocumentItem, now: number): { tone: "warning" | "danger"; text: string } | null {
  const p = doc.ingest_progress;
  const stage = p.stage ?? null;
  const step = stage && p.steps ? p.steps[stage] : null;

  if (doc.processing_status === "FAILED") {
    const failed = p.steps && INGEST_STEPS.find((s) => p.steps![s].status === "failed");
    return { tone: "danger", text: `Lỗi ở bước ${failed ? LABELS[failed] : "?"}: ${doc.error_message ?? "không rõ"}` };
  }
  if (doc.processing_status === "PENDING") {
    const waited = seconds(doc.created_at, now) ?? 0;
    return waited > PENDING_WARN_S
      ? { tone: "warning", text: `Chưa có worker nào nhận task sau ${formatDuration(waited)}. Kiểm tra taskiq worker đã chạy chưa.` }
      : null;
  }
  if (doc.processing_status !== "PROCESSING") return null;

  // Bước Lưu DB chạy trong 1 transaction, worker tạm ngừng ghi heartbeat (xem ingest())
  const heartbeatPaused = stage === "save";
  const silent = seconds(p.heartbeat_at, now);
  if (!heartbeatPaused && silent != null && silent > HEARTBEAT_WARN_S) {
    return {
      tone: "danger",
      text: `Mất tín hiệu từ worker ${formatDuration(silent)} khi đang ở bước ${stage ? LABELS[stage] : "?"}. Worker có thể đã dừng hoặc bị kill – upload lại tài liệu sau khi khởi động lại worker.`,
    };
  }
  const idle = step?.status === "running" ? seconds(step.progress_at, now) : null;
  if (stage && idle != null && idle > STALL_WARN_S) {
    const where = step?.detail ? ` (${step.detail})` : "";
    const hint =
      stage === "embed" ? " Có thể API embedding đang chậm hoặc bị giới hạn." : stage === "parse" ? " Trang có ảnh cần OCR có thể mất lâu." : "";
    return {
      tone: "warning",
      text: `Bước ${LABELS[stage]}${where} không tiến triển ${formatDuration(idle)}.${heartbeatPaused ? "" : " Worker vẫn hoạt động."}${hint}`,
    };
  }
  return null;
}

export function IngestPipeline({ doc, now }: { doc: DocumentItem; now: number }) {
  const steps = doc.ingest_progress.steps;
  if (!steps) {
    return doc.processing_status === "PENDING" ? (
      <p className="text-xs text-muted">Đang chờ worker nhận task…</p>
    ) : null;
  }

  // Tài liệu đã xong: 1 dòng thời gian từng bước
  if (doc.processing_status === "READY") {
    return (
      <p className="text-xs text-muted">
        {INGEST_STEPS.map((s, i) => {
          const d = stepDuration(steps[s], now);
          return (
            <span key={s}>
              {i > 0 && " → "}
              <span className="text-success">✓</span> {LABELS[s]}
              {d != null ? ` ${formatDuration(d)}` : ""}
            </span>
          );
        })}
      </p>
    );
  }

  return (
    <ol className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Tiến độ xử lý">
      {INGEST_STEPS.map((s) => {
        const step = steps[s];
        return (
          <li key={s} className="min-w-0 space-y-1">
            <div className="flex items-center gap-1.5 text-xs font-medium">
              <span className={STATUS_COLOR[step.status]} aria-hidden>
                {STATUS_ICON[step.status]}
              </span>
              <span className={step.status === "pending" ? "text-muted" : ""}>{LABELS[s]}</span>
            </div>
            <StepBar step={step} />
            <p className="truncate text-xs text-muted tabular-nums" title={stepText(step, now)}>
              {stepText(step, now)}
            </p>
          </li>
        );
      })}
    </ol>
  );
}
