import { NextRequest, NextResponse } from "next/server";

// Login route handler: exchanges username+password with the backend, then stores
// the returned role API token in an httpOnly cookie (session cookie, or 7-day if
// "ingat saya"). The token is never exposed to client JS.
export const dynamic = "force-dynamic";

const BACKEND =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "http://localhost:8000";

export async function POST(req: NextRequest) {
  const { username, password, remember } = await req.json().catch(() => ({} as any));

  let res: Response;
  try {
    res = await fetch(`${BACKEND}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch (e: any) {
    return NextResponse.json(
      { detail: `Backend tidak terjangkau: ${String(e?.message || e)}` },
      { status: 502 }
    );
  }

  const data = await res.json().catch(() => ({} as any));
  if (!res.ok || !data?.token) {
    return NextResponse.json(
      { detail: data?.detail || "Login gagal" },
      { status: res.status && res.status >= 400 ? res.status : 401 }
    );
  }

  const out = NextResponse.json({ ok: true, role: data.role });
  const base = {
    name: "kapsel_token",
    value: data.token as string,
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
  };
  if (remember) {
    out.cookies.set({ ...base, maxAge: 60 * 60 * 24 * 7 });
  } else {
    out.cookies.set(base);
  }
  return out;
}
