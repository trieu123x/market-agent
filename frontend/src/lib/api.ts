// Gọi REST backend kèm JWT (lưu localStorage) và chuẩn hóa thông báo lỗi.

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010").replace(/\/$/, "");

const TOKEN_KEY = "market_agent_token";
export const AUTH_EXPIRED_EVENT = "market-agent:auth-expired";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // private mode / storage bị chặn: phiên chỉ sống trong bộ nhớ
  }
}

/** Đã qua nửa vòng đời token (iat→exp) chưa; token hỏng/thiếu claim coi như cần làm mới. */
export function tokenNeedsRefresh(token: string, nowMs = Date.now()): boolean {
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const { iat, exp } = JSON.parse(atob(b64)) as { iat?: number; exp?: number };
    if (!exp) return true;
    const now = nowMs / 1000;
    // Token cũ (trước khi có iat): làm mới khi còn dưới 10 phút
    return iat ? now >= (iat + exp) / 2 : exp - now < 600;
  } catch {
    return true;
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/** FastAPI trả `detail` dạng chuỗi (HTTPException) hoặc mảng lỗi validation (422). */
export function detailMessage(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { msg?: string }) => (d.msg ?? "").replace(/^Value error, /, ""))
      .filter(Boolean)
      .join("; ");
  }
  return fallback;
}

/** Đọc lỗi từ response không OK; 401 kèm token → báo phiên hết hạn để AuthProvider đăng xuất. */
export async function toApiError(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    // body không phải JSON
  }
  if (res.status === 401 && getToken()) {
    setToken(null);
    window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
  }
  return new ApiError(res.status, detailMessage(body, `Lỗi ${res.status}`));
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

interface RequestOptions {
  method?: string;
  json?: unknown;
  form?: FormData;
}

export async function api<T>(path: string, { method = "GET", json, form }: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = authHeaders();
  let body: BodyInit | undefined;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body });
  } catch {
    throw new ApiError(0, `Không kết nối được backend (${API_URL})`);
  }
  if (!res.ok) throw await toApiError(res);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
