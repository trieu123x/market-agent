"use client";

import { useCallback, useEffect, useState } from "react";

import { BarList } from "@/components/admin/BarList";
import { Alert, Button, Card, Field, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { formatInt, formatUsd } from "@/lib/format";
import type { AdminUser, CostReport, Pricing } from "@/types/api";

interface Filters {
  start_date: string;
  end_date: string;
  user_id: string;
  model_id: string;
}

// Ngày theo giờ địa phương (toISOString là UTC → lệch ngày ở UTC+7)
const isoDay = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function defaultFilters(): Filters {
  const end = new Date();
  const start = new Date(end);
  start.setDate(end.getDate() - 29);
  return { start_date: isoDay(start), end_date: isoDay(end), user_id: "", model_id: "" };
}

export default function AdminCostsPage() {
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [report, setReport] = useState<CostReport | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [models, setModels] = useState<Pricing[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (f: Filters) => {
    setLoading(true);
    setError(null);
    const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v));
    try {
      setReport(await api<CostReport>(`/api/v1/admin/analytics/costs?${qs}`));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(defaultFilters());
    api<AdminUser[]>("/api/v1/admin/users").then(setUsers).catch(() => {});
    api<Pricing[]>("/api/v1/admin/pricing").then(setModels).catch(() => {});
  }, [load]);

  const set = (patch: Partial<Filters>) => {
    const next = { ...filters, ...patch };
    setFilters(next);
    void load(next);
  };
  const emailOf = (id: string) => users.find((u) => u.id === id)?.email ?? id;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[160px_160px_1fr_1fr_auto] lg:items-end">
        <Field label="Từ ngày">
          <input type="date" className={inputClass} value={filters.start_date} onChange={(e) => set({ start_date: e.target.value })} />
        </Field>
        <Field label="Đến ngày">
          <input type="date" className={inputClass} value={filters.end_date} onChange={(e) => set({ end_date: e.target.value })} />
        </Field>
        <Field label="Người dùng">
          <select className={inputClass} value={filters.user_id} onChange={(e) => set({ user_id: e.target.value })}>
            <option value="">Tất cả</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.email}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Model">
          <select className={inputClass} value={filters.model_id} onChange={(e) => set({ model_id: e.target.value })}>
            <option value="">Tất cả</option>
            {models.map((m) => (
              <option key={m.model_id} value={m.model_id}>
                {m.model_id}
              </option>
            ))}
          </select>
        </Field>
        <Button onClick={() => set(defaultFilters())} disabled={loading}>
          30 ngày qua
        </Button>
      </div>

      {error && <Alert>{error}</Alert>}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-line bg-panel px-4 py-3">
          <div className="text-xs text-muted">Tổng chi phí</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">{report ? formatUsd(report.total_cost_usd) : "–"}</div>
        </div>
        <div className="rounded-lg border border-line bg-panel px-4 py-3">
          <div className="text-xs text-muted">Tổng token</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">{report ? formatInt(report.total_tokens_consumed) : "–"}</div>
        </div>
      </div>

      <div className={`grid gap-4 lg:grid-cols-2 ${loading ? "opacity-60" : ""}`}>
        <Card title="Theo model">
          <BarList
            items={(report?.breakdown_by_model ?? []).map((r) => ({ key: r.model_id, label: r.model_id, tokens: r.tokens, costUsd: r.cost_usd }))}
          />
        </Card>
        <Card title="Theo node">
          <BarList
            items={(report?.breakdown_by_node ?? []).map((r) => ({ key: r.node_name, label: r.node_name, tokens: r.tokens, costUsd: r.cost_usd }))}
          />
        </Card>
        <div className="lg:col-span-2">
          <Card title="Theo người dùng">
            <BarList
              items={(report?.breakdown_by_user ?? []).map((r) => ({
                key: r.user_id,
                label: emailOf(r.user_id),
                tokens: r.tokens,
                costUsd: r.cost_usd,
              }))}
            />
          </Card>
        </div>
      </div>
    </div>
  );
}
