import { NextResponse } from "next/server";
import { cookies } from "next/headers";

// Returns the current session role (from the cookie -> backend /auth/me), or 401.
export const dynamic = "force-dynamic";

const BACKEND =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "http://localhost:8000";

export async function GET() {
  const token = (await cookies()).get("kapsel_token")?.value;
  if (!token) return NextResponse.json({ role: null }, { status: 401 });
  try {
    const res = await fetch(`${BACKEND}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return NextResponse.json({ role: null }, { status: 401 });
    const data = await res.json().catch(() => ({} as any));
    return NextResponse.json({ role: data.role || null });
  } catch {
    return NextResponse.json({ role: null }, { status: 401 });
  }
}
