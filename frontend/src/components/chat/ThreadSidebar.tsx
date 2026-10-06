import { Button } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import type { Thread } from "@/types/api";

interface Props {
  threads: Thread[];
  activeId: string | null;
  disabled: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
}

export function ThreadSidebar({ threads, activeId, disabled, onSelect, onNew }: Props) {
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
          <li key={t.id}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSelect(t.id)}
              className={`w-full rounded-md px-2 py-1.5 text-left disabled:opacity-60 ${
                t.id === activeId ? "bg-panel-2" : "hover:bg-panel-2"
              }`}
            >
              <span className="block truncate text-sm">{t.title || "Chiến dịch mới"}</span>
              <span className="block text-xs text-muted">{formatDateTime(t.updated_at)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
