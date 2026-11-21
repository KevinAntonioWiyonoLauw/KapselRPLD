import { NextResponse } from "next/server";

// Clears the auth cookie.
export const dynamic = "force-dynamic";

export async function POST() {
  const out = NextResponse.json({ ok: true });
  out.cookies.set({
    name: "kapsel_token",
    value: "",
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return out;
}
