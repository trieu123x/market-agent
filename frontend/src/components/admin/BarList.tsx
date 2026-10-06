import { formatInt, formatUsd } from "@/lib/format";

export interface BarItem {
  key: string;
  label: string;
  tokens: number;
  costUsd: number;
}

/** Breakdown chi phí: mỗi dòng 1 thanh ngang (1 series, 1 màu) tỉ lệ theo USD; số liệu ghi bằng chữ ở cuối thanh. */
export function BarList({ items, empty = "Chưa có dữ liệu." }: { items: BarItem[]; empty?: string }) {
  if (items.length === 0) return <p className="text-sm text-muted">{empty}</p>;
  const sorted = [...items].sort((a, b) => b.costUsd - a.costUsd || b.tokens - a.tokens);
  const max = Math.max(...sorted.map((i) => i.costUsd)) || 1;

  return (
    <ul className="space-y-2.5">
      {sorted.map((i) => (
        <li key={i.key} className="group" title={`${i.label}: ${formatUsd(i.costUsd)} · ${formatInt(i.tokens)} token`}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate">{i.label}</span>
            <span className="shrink-0 tabular-nums">
              <span className="font-medium">{formatUsd(i.costUsd)}</span>
              <span className="ml-2 text-xs text-muted">{formatInt(i.tokens)} token</span>
            </span>
          </div>
          <div className="h-2.5 rounded-r bg-panel-2">
            <div
              className="h-full rounded-r bg-series-1 transition-[width] group-hover:opacity-80"
              style={{ width: `${Math.max((i.costUsd / max) * 100, i.costUsd > 0 ? 1 : 0)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
