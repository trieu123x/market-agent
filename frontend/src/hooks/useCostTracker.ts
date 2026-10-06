"use client";

import { useCallback, useMemo, useState } from "react";

import type { CostUpdateEvent } from "@/types/events";

interface Totals {
  tokens: number;
  costUsd: number;
}

/** Cộng dồn token + chi phí USD của thread hiện tại từ các event cost_update.
 *  `baseline` = tổng đã có trên server (khi mở lại thread hoặc khi nhận complete). */
export function useCostTracker() {
  const [baseline, setBaseline] = useState<Totals>({ tokens: 0, costUsd: 0 });
  const [entries, setEntries] = useState<CostUpdateEvent[]>([]);

  const add = useCallback((e: CostUpdateEvent) => setEntries((prev) => [...prev, e]), []);

  const reset = useCallback((tokens = 0, costUsd = 0) => {
    setBaseline({ tokens, costUsd });
    setEntries([]);
  }, []);

  return useMemo(() => {
    const tokens = baseline.tokens + entries.reduce((s, e) => s + e.tokens, 0);
    const costUsd = baseline.costUsd + entries.reduce((s, e) => s + e.cost_usd, 0);
    return {
      tokens,
      costUsd,
      lastCall: entries.at(-1) ?? null,
      pricingMissing: entries.some((e) => e.pricing_missing),
      add,
      reset,
    };
  }, [baseline, entries, add, reset]);
}

export type CostTracker = ReturnType<typeof useCostTracker>;
