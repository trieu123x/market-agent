import type { ReactNode } from "react";

import { RequireAuth } from "@/components/layout/RequireAuth";
import { TopNav } from "@/components/layout/TopNav";

export default function UserLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <div className="flex h-dvh flex-col">
        <TopNav />
        <div className="min-h-0 flex-1">{children}</div>
      </div>
    </RequireAuth>
  );
}
