"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Alert, Badge, Button, Card, Field, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { Pricing, Provider } from "@/types/api";

interface RowDraft {
  input: string;
  output: string;
}

export default function AdminPricingPage() {
  const [rows, setRows] = useState<Pricing[]>([]);
  const [drafts, setDrafts] = useState<Record<string, RowDraft>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newModel, setNewModel] = useState({ provider: "google" as Provider, model_id: "", input: "", output: "" });

  const load = useCallback(async () => {
    try {
      const list = await api<Pricing[]>("/api/v1/admin/pricing");
      setRows(list);
      setDrafts(
        Object.fromEntries(
          list.map((r) => [r.model_id, { input: String(r.input_price_per_1k), output: String(r.output_price_per_1k) }]),
        ),
      );
    } catch (err) {
      setError(errorText(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function put(modelId: string, body: Record<string, unknown>) {
    setBusy(modelId);
    setError(null);
    try {
      await api(`/api/v1/admin/pricing/${encodeURIComponent(modelId)}`, { method: "PUT", json: body });
      await load();
      return true;
    } catch (err) {
      setError(errorText(err));
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function create(e: FormEvent) {
    e.preventDefault();
    const ok = await put(newModel.model_id.trim(), {
      provider: newModel.provider,
      input_price_per_1k: newModel.input,
      output_price_per_1k: newModel.output,
    });
    if (ok) setNewModel({ ...newModel, model_id: "", input: "", output: "" });
  }

  const dirty = (r: Pricing) => {
    const d = drafts[r.model_id];
    return d && (Number(d.input) !== r.input_price_per_1k || Number(d.output) !== r.output_price_per_1k);
  };

  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}
      <Card title="Bảng giá model (USD / 1K token)">
        <div className="-mx-4 overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                <th className="px-4 py-2 font-medium">Model</th>
                <th className="px-2 py-2 font-medium">Input</th>
                <th className="px-2 py-2 font-medium">Output</th>
                <th className="px-2 py-2 font-medium">Trạng thái</th>
                <th className="px-2 py-2 font-medium">Cập nhật</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const d = drafts[r.model_id] ?? { input: "", output: "" };
                const setD = (patch: Partial<RowDraft>) => setDrafts({ ...drafts, [r.model_id]: { ...d, ...patch } });
                return (
                  <tr key={r.model_id} className="border-t border-line align-middle">
                    <td className="px-4 py-2">
                      <div className="font-medium">{r.model_id}</div>
                      <div className="text-xs text-muted">{r.provider}</div>
                    </td>
                    <td className="px-2 py-2">
                      <input
                        className={`${inputClass} w-28 tabular-nums`}
                        type="number"
                        step="0.000001"
                        min="0"
                        value={d.input}
                        onChange={(e) => setD({ input: e.target.value })}
                        aria-label={`Giá input ${r.model_id}`}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <input
                        className={`${inputClass} w-28 tabular-nums`}
                        type="number"
                        step="0.000001"
                        min="0"
                        value={d.output}
                        onChange={(e) => setD({ output: e.target.value })}
                        aria-label={`Giá output ${r.model_id}`}
                      />
                    </td>
                    <td className="px-2 py-2">
                      <div className="flex flex-wrap gap-1">
                        {r.is_default && <Badge tone="accent">Mặc định</Badge>}
                        {r.is_system_active ? <Badge tone="success">Bật</Badge> : <Badge>Tắt</Badge>}
                      </div>
                    </td>
                    <td className="px-2 py-2 whitespace-nowrap text-muted">{formatDateTime(r.updated_at)}</td>
                    <td className="px-4 py-2">
                      <div className="flex justify-end gap-1">
                        {dirty(r) && (
                          <Button
                            variant="primary"
                            busy={busy === r.model_id}
                            onClick={() => put(r.model_id, { input_price_per_1k: d.input, output_price_per_1k: d.output })}
                          >
                            Lưu giá
                          </Button>
                        )}
                        {!r.is_default && r.is_system_active && (
                          <Button variant="ghost" disabled={busy !== null} onClick={() => put(r.model_id, { is_default: true })}>
                            Đặt mặc định
                          </Button>
                        )}
                        {!r.is_default && (
                          <Button
                            variant="ghost"
                            disabled={busy !== null}
                            onClick={() => put(r.model_id, { is_system_active: !r.is_system_active })}
                          >
                            {r.is_system_active ? "Tắt" : "Bật"}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Thêm model">
        <form onSubmit={create} className="grid gap-3 sm:grid-cols-[140px_1fr_120px_120px_auto] sm:items-end">
          <Field label="Provider">
            <select
              className={inputClass}
              value={newModel.provider}
              onChange={(e) => setNewModel({ ...newModel, provider: e.target.value as Provider })}
            >
              <option value="google">google</option>
              <option value="openai">openai</option>
              <option value="anthropic">anthropic</option>
            </select>
          </Field>
          <Field label="Model ID">
            <input
              className={inputClass}
              required
              placeholder="vd. gemini-2.5-flash"
              value={newModel.model_id}
              onChange={(e) => setNewModel({ ...newModel, model_id: e.target.value })}
            />
          </Field>
          <Field label="Input / 1K">
            <input
              className={inputClass}
              required
              type="number"
              step="0.000001"
              min="0"
              value={newModel.input}
              onChange={(e) => setNewModel({ ...newModel, input: e.target.value })}
            />
          </Field>
          <Field label="Output / 1K">
            <input
              className={inputClass}
              required
              type="number"
              step="0.000001"
              min="0"
              value={newModel.output}
              onChange={(e) => setNewModel({ ...newModel, output: e.target.value })}
            />
          </Field>
          <Button type="submit" variant="primary" busy={busy === newModel.model_id.trim()}>
            Thêm
          </Button>
        </form>
      </Card>
    </div>
  );
}
