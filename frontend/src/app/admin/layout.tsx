"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { RequireAuth } from "@/components/layout/RequireAuth";
import { TopNav } from "@/components/layout/TopNav";

const TABS = [
  { href: "/admin/users", label: "Người dùng" },
  { href: "/admin/pricing", label: "Bảng giá model" },
  { href: "/admin/costs", label: "Chi phí" },
];

export default function AdminLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <RequireAuth admin>
      <div className="flex h-dvh flex-col">
        <TopNav />
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-6xl space-y-4 px-4 py-6">
            <nav className="flex gap-1 overflow-x-auto border-b border-line">
              {TABS.map((t) => (
                <Link
                  key={t.href}
                  href={t.href}
                  className={`-mb-px border-b-2 px-3 py-2 text-sm whitespace-nowrap ${
                    pathname === t.href ? "border-accent font-medium" : "border-transparent text-muted hover:text-fg"
                  }`}
                >
                  {t.label}
                </Link>
              ))}
            </nav>
            {children}
          </div>
        </div>
      </div>
    </RequireAuth>
  );
}
