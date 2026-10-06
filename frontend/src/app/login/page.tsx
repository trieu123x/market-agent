"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Alert, Button, Field, inputClass } from "@/components/ui";
import { errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Chỉ cho phép quay lại đường dẫn nội bộ (chặn open redirect qua ?next=). */
function nextPath(): string {
  const next = new URLSearchParams(window.location.search).get("next");
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/chat";
}

export default function LoginPage() {
  const { user, loading, login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace(nextPath());
  }, [loading, user, router]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, fullName);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-lg border border-line bg-panel p-6">
        <div>
          <h1 className="text-lg font-semibold">Marketing Agent</h1>
          <p className="text-sm text-muted">
            {mode === "login" ? "Đăng nhập để lên chiến dịch." : "Tạo tài khoản mới."}
          </p>
        </div>
        {mode === "register" && (
          <Field label="Họ tên (tùy chọn)">
            <input className={inputClass} value={fullName} onChange={(e) => setFullName(e.target.value)} maxLength={100} />
          </Field>
        )}
        <Field label="Email">
          <input
            className={inputClass}
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label="Mật khẩu">
          <input
            className={inputClass}
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={mode === "register" ? 8 : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" variant="primary" busy={busy} className="w-full">
          {mode === "login" ? "Đăng nhập" : "Đăng ký"}
        </Button>
        <p className="text-center text-sm text-muted">
          {mode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"}{" "}
          <button
            type="button"
            className="text-accent hover:underline"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
          >
            {mode === "login" ? "Đăng ký" : "Đăng nhập"}
          </button>
        </p>
      </form>
    </main>
  );
}
