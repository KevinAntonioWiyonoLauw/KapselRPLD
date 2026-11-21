import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

// Server-side proxy: forwards /api/proxy/<path> to the backend Management API,
// attaching the Bearer token read from the httpOnly cookie. Keeps the token out
// of client JS while preserving full backend RBAC enforcement.
export const dynamic = "force-dynamic";

const BACKEND =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "http://localhost:8000";

async function forward(req: NextRequest, path: string[]) {
  const token = (await cookies()).get("kapsel_token")?.value;
  const target = `${BACKEND}/${path.join("/")}${req.nextUrl.search}`;

  const headers: Record<string, string> = {};
  const ct = req.headers.get("content-type");
  if (ct) headers["content-type"] = ct;
  if (token) headers["authorization"] = `Bearer ${token}`;

  const method = req.method;
  const body = method === "GET" || method === "HEAD" ? undefined : await req.text();

  let res: Response;
  try {
    res = await fetch(target, { method, headers, body, cache: "no-store" });
  } catch (e: any) {
    return NextResponse.json(
      { detail: `Backend tidak terjangkau: ${String(e?.message || e)}` },
      { status: 502 }
    );
  }

  const data = await res.text();
  return new NextResponse(data, {
    status: res.status,
    headers: {
      "content-type": res.headers.get("content-type") || "application/json",
    },
  });
}

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(req, params.path);
}

export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return forward(req, params.path);
}
