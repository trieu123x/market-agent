"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import type { User } from "@/types/api";
import { api, AUTH_EXPIRED_EVENT, getToken, setToken, tokenNeedsRefresh } from "./api";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, fullName?: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const expired = () => setUser(null);
    window.addEventListener(AUTH_EXPIRED_EVENT, expired);
    if (getToken()) {
      api<User>("/api/v1/auth/me")
        .then(setUser)
        .catch(() => setUser(null))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expired);
  }, []);

  // Sliding session: JWT sống JWT_EXPIRE_MINUTES, nên đổi token mới trước khi hết hạn
  // (kiểm tra định kỳ + khi tab hiện lại sau khi máy ngủ / tab bị throttle).
  useEffect(() => {
    if (!user) return;
    let inFlight = false;
    const tick = () => {
      const token = getToken();
      if (inFlight || !token || !tokenNeedsRefresh(token)) return;
      inFlight = true;
      api<{ access_token: string }>("/api/v1/auth/refresh", { method: "POST" })
        .then(({ access_token }) => setToken(access_token))
        .catch(() => {}) // 401 đã được toApiError xử lý (đăng xuất); lỗi mạng thì thử lại lượt sau
        .finally(() => {
          inFlight = false;
        });
    };
    tick();
    const id = window.setInterval(tick, 60_000);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [user]);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api<{ access_token: string }>("/api/v1/auth/login", {
      method: "POST",
      json: { email, password },
    });
    setToken(access_token);
    const me = await api<User>("/api/v1/auth/me");
    setUser(me);
    return me;
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName?: string) => {
      await api<User>("/api/v1/auth/register", {
        method: "POST",
        json: { email, password, full_name: fullName || null },
      });
      return login(email, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth phải nằm trong <AuthProvider>");
  return ctx;
}
