"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui";
import { useAuth } from "@/lib/auth";

const LINKS = [
  { href: "/chat", label: "Chiến dịch" },
  { href: "/documents", label: "Tài liệu" },
];

export function TopNav() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const links = user?.role === "ADMIN" ? [...LINKS, { href: "/admin/users", label: "Admin" }] : LINKS;
  const active = (href: string) => pathname.startsWith(href.startsWith("/admin") ? "/admin" : href);

  return (
    <nav className="flex h-12 shrink-0 items-center gap-1 border-b border-line bg-panel px-4">
      <Link href="/chat" className="mr-3 text-sm font-semibold whitespace-nowrap">
        <span className="sm:hidden">MA</span>
        <span className="hidden sm:inline">Marketing Agent</span>
      </Link>
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={`rounded-md px-2.5 py-1 text-sm whitespace-nowrap ${active(l.href) ? "bg-panel-2 font-medium text-fg" : "text-muted hover:text-fg"}`}
        >
          {l.label}
        </Link>
      ))}
      <div className="ml-auto flex min-w-0 items-center gap-2">
        <span className="hidden truncate text-xs text-muted sm:inline">{user?.email}</span>
        <Button variant="ghost" className="whitespace-nowrap" onClick={logout}>
          Đăng xuất
        </Button>
      </div>
    </nav>
  );
}
