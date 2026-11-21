// Browser-side API client. All management API calls go through the same-origin
// proxy (/api/proxy/*) so the auth token stays in an httpOnly cookie and is never
// exposed to client JS. RBAC is still enforced by the backend on every request.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const PROXY = "/api/proxy";

async function handle(res: Response) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `${res.status} ${res.statusText}`);
  return data;
}

export async function apiGet(path: string) {
  const res = await fetch(`${PROXY}${path}`, { cache: "no-store" });
  return handle(res);
}

export async function apiPost(path: string, body?: any) {
  const res = await fetch(`${PROXY}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return handle(res);
}

// --- Auth (login form) — token disimpan sebagai cookie httpOnly oleh route handler ---

export async function login(username: string, password: string, remember: boolean) {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, remember }),
  });
  return handle(res); // { ok: true, role }
}

export async function logout() {
  await fetch("/api/logout", { method: "POST" });
}

export async function getSession(): Promise<{ role: string } | null> {
  const res = await fetch("/api/session", { cache: "no-store" });
  if (!res.ok) return null;
  return res.json().catch(() => null);
}
