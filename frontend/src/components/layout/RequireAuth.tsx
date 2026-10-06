"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export function RequireAuth({ admin = false, children }: { admin?: boolean; children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, router, pathname]);

  if (loading || !user) {
    return (
      <div className="flex h-dvh items-center justify-center text-muted">
        <Spinner />
      </div>
    );
  }
  if (admin && user.role !== "ADMIN") {
    return <div className="p-8 text-center text-muted">Trang này chỉ dành cho ADMIN.</div>;
  }
  return <>{children}</>;
}
