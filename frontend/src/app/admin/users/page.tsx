"use client";

import { useCallback, useEffect, useState } from "react";

import { Alert, Badge, Button, Card } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import type { AdminUser } from "@/types/api";

export default function AdminUsersPage() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setUsers(await api<AdminUser[]>("/api/v1/admin/users"));
    } catch (err) {
      setError(errorText(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(u: AdminUser) {
    setBusyId(u.id);
    setError(null);
    try {
      const res = await api<{ is_active: boolean }>(`/api/v1/admin/users/${u.id}/status`, {
        method: "PATCH",
        json: { is_active: !u.is_active },
      });
      setUsers((list) => list.map((x) => (x.id === u.id ? { ...x, is_active: res.is_active } : x)));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card title={`Người dùng (${users.length})`}>
      {error && <div className="mb-3"><Alert>{error}</Alert></div>}
      <div className="-mx-4 overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th className="px-4 py-2 font-medium">Email</th>
              <th className="px-2 py-2 font-medium">Họ tên</th>
              <th className="px-2 py-2 font-medium">Vai trò</th>
              <th className="px-2 py-2 font-medium">Trạng thái</th>
              <th className="px-2 py-2 font-medium">Tạo lúc</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-line">
                <td className="px-4 py-2">{u.email}</td>
                <td className="px-2 py-2 text-muted">{u.full_name || "–"}</td>
                <td className="px-2 py-2">
                  <Badge tone={u.role === "ADMIN" ? "accent" : "neutral"}>{u.role}</Badge>
                </td>
                <td className="px-2 py-2">
                  {u.is_active ? <Badge tone="success">Hoạt động</Badge> : <Badge tone="danger">Đã khóa</Badge>}
                </td>
                <td className="px-2 py-2 whitespace-nowrap text-muted">{formatDateTime(u.created_at)}</td>
                <td className="px-4 py-2 text-right">
                  {u.id !== me?.id && (
                    <Button variant={u.is_active ? "danger" : "secondary"} busy={busyId === u.id} onClick={() => toggle(u)}>
                      {u.is_active ? "Khóa" : "Mở khóa"}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
