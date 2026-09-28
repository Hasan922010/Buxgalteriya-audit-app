// Bearer-token storage and authenticated fetch helpers.

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

const TOKEN_KEY = "access_token";
export const UNAUTHORIZED_EVENT = "auth:unauthorized";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // storage unavailable (private mode); the session will simply not persist
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

export function authHeaders(custom: Record<string, string> = {}): Record<string, string> {
  const token = getToken();
  return token ? { ...custom, Authorization: `Bearer ${token}` } : { ...custom };
}

/** fetch() that attaches the bearer token and signals a logout on 401. */
export async function authFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = { ...(init.headers as Record<string, string> | undefined), ...authHeaders() };
  const res = await fetch(input, { ...init, headers });
  if (res.status === 401 && typeof window !== "undefined") {
    clearToken();
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }
  return res;
}

function filenameFromResponse(res: Response, fallback: string): string {
  const disposition = res.headers.get("Content-Disposition") || "";
  const utf8 = disposition.match(/filename\*=utf-8''([^;]+)/i);
  if (utf8) return decodeURIComponent(utf8[1]);
  const plain = disposition.match(/filename="?([^";]+)"?/i);
  return plain ? plain[1] : fallback;
}

/** Downloads a protected file (plain <a href> cannot send the Authorization header). */
export async function downloadWithAuth(url: string, fallbackName = "download"): Promise<void> {
  const res = await authFetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Faylni yuklab bo'lmadi");
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filenameFromResponse(res, fallbackName);
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
