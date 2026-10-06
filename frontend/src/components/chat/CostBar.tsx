import type { CostTracker } from "@/hooks/useCostTracker";
import { formatInt, formatUsd } from "@/lib/format";

/** Tổng token + chi phí USD ước tính của thread, cộng dồn realtime theo event cost_update. */
export function CostBar({ cost }: { cost: CostTracker }) {
  const last = cost.lastCall;
  return (
    <div
      className="flex items-center gap-3 rounded-md border border-line bg-panel px-3 py-1 text-xs tabular-nums"
      title={last ? `Lần gọi gần nhất: ${last.node} · ${last.model_id} · ${last.tokens} token` : undefined}
      aria-live="polite"
    >
      <span>
        <span className="text-muted">Token </span>
        <span className="font-medium">{formatInt(cost.tokens)}</span>
      </span>
      <span>
        <span className="text-muted">Chi phí </span>
        <span className="font-medium">{formatUsd(cost.costUsd)}</span>
      </span>
      {cost.pricingMissing && <span className="text-warning">⚠ thiếu bảng giá</span>}
    </div>
  );
}
