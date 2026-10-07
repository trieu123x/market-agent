import { Button, Spinner } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import type { Thread } from "@/types/api";

interface Props {
  threads: Thread[];
  activeId: string | null;
  disabled: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (thread: Thread) => void;
  deletingId: string | null;
}

export function ThreadSidebar({ threads, activeId, disabled, onSelect, onNew, onDelete, deletingId }: Props) {
  return (
    <div className="flex h-full flex-col">
      <div className="p-3">
        <Button variant="primary" className="w-full" onClick={onNew} disabled={disabled}>
          + Chiến dịch mới
        </Button>
      </div>
      <ul className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
        {threads.length === 0 && <li className="px-2 text-xs text-muted">Chưa có chiến dịch nào.</li>}
        {threads.map((t) => (
          <li key={t.id} className="group relative">
            <button
              type="button"
              disabled={disabled || deletingId === t.id}
              onClick={() => onSelect(t.id)}
              className={`w-full rounded-md py-1.5 pl-2 pr-8 text-left disabled:opacity-60 ${
                t.id === activeId ? "bg-panel-2" : "hover:bg-panel-2"
              }`}
            >
              <span className="block truncate text-sm">{t.title || "Chiến dịch mới"}</span>
              <span className="block text-xs text-muted">{formatDateTime(t.updated_at)}</span>
            </button>
            {/* Luôn hiện trên màn hình cảm ứng, chỉ hiện khi hover/focus trên desktop */}
            <button
              type="button"
              disabled={disabled || deletingId !== null}
              onClick={() => onDelete(t)}
              aria-label={`Xóa chiến dịch "${t.title || "Chiến dịch mới"}"`}
              title="Xóa chiến dịch"
              className={`absolute right-1 top-1/2 -translate-y-1/2 rounded p-1 text-muted hover:bg-danger-soft hover:text-danger focus:opacity-100 disabled:cursor-not-allowed group-hover:opacity-100 md:opacity-0 ${
                deletingId === t.id ? "md:opacity-100" : ""
              }`}
            >
              {deletingId === t.id ? (
                <Spinner />
              ) : (
                <svg aria-hidden viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M2.5 4h11M6.5 4V2.5h3V4M4 4l.7 9.5h6.6L12 4M6.75 6.5v5M9.25 6.5v5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
