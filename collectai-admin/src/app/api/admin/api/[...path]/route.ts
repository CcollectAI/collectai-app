/**
 * /api/admin/api/<backend path> — the ONE door between the admin browser and
 * the FastAPI backend. Same shape as ../sb/[...path]/route.ts (the Supabase
 * door, 2026-09-22).
 *
 * Why this route exists (2026-09-27 walk): the dashboard called
 * https://api.sparrowcollect.com straight from the browser with the ops key in
 * NEXT_PUBLIC_OPS_KEY. Two defects, one cause:
 *   - The API's CORS allowlist is the sparrowcollect.com sites, so EVERY call
 *     from the dashboard's origin was refused — and collectai-api.ts answered
 *     each refusal with invented numbers (Overview: 2,847 users, 187,432 items,
 *     "LIVE", "DB: connected"; prod had 10 users and 21 items).
 *   - A NEXT_PUBLIC_ variable is inlined into the client bundle, so anyone who
 *     loaded the page could read the ops key.
 * Server-side, the call is same-origin for the browser (no CORS) and the key
 * never leaves the server.
 *
 * Only the paths below are forwarded — each one exists in scripts/api.lock.json
 * (checked 2026-09-27). A path not listed is refused, not forwarded.
 */
import { NextResponse } from "next/server";
import { adminAuthConfigured, isAdminRequest } from "@/lib/adminAuth";

const GET_PATHS = new Set([
  "/ops/dashboard/stats",
  "/ops/dashboard/users",
  "/ops/dashboard/sponsor-analytics",
  "/ops/dashboard/intel-summary",
  "/admin/worker-health",
  "/admin/demand-summary",
  "/admin/models",
  "/admin/metrics",
  "/admin/kpi-summary",
  "/admin/spend-summary",
]);

// The spend controls change what the server may spend. Allowed because they
// are admin functions, but nothing else that writes.
const POST_PATHS = new Set([
  "/admin/spend-budget",
  "/admin/spend-pause",
  "/admin/spend-reset",
]);

const PREFIX = "/api/admin/api";

function apiBase(): string {
  return (process.env.COLLECTAI_API_BASE || process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");
}

function guard(req: Request): NextResponse | null {
  const cfg = adminAuthConfigured();
  const missing = [...cfg.missing];
  if (!process.env.OPS_API_KEY) missing.push("OPS_API_KEY");
  if (!apiBase()) missing.push("COLLECTAI_API_BASE");
  if (missing.length) {
    return NextResponse.json(
      { detail: `Admin API proxy not configured. Missing: ${missing.join(", ")}` },
      { status: 503 },
    );
  }
  if (!isAdminRequest(req)) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }
  return null;
}

async function forward(req: Request, allowed: Set<string>): Promise<Response> {
  const blocked = guard(req);
  if (blocked) return blocked;

  const url = new URL(req.url);
  const path = url.pathname.slice(PREFIX.length) || "/";
  if (!allowed.has(path)) {
    return NextResponse.json(
      { detail: `Not an allowed ${req.method} path: ${path}` },
      { status: 403 },
    );
  }

  const headers: Record<string, string> = {
    "X-Ops-Key": process.env.OPS_API_KEY as string,
    Accept: "application/json",
  };
  const init: RequestInit = { method: req.method, headers, cache: "no-store" };
  if (req.method === "POST") {
    headers["Content-Type"] = "application/json";
    init.body = await req.text();
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${apiBase()}${path}${url.search}`, {
      ...init,
      signal: AbortSignal.timeout(20000),
    });
  } catch (err) {
    // Say which leg failed: this is the proxy failing to reach the API, not
    // the API answering with an error.
    const why = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { detail: `API unreachable from the dashboard server: ${why}` },
      { status: 502 },
    );
  }

  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
  });
}

export async function GET(req: Request) {
  return forward(req, GET_PATHS);
}

export async function POST(req: Request) {
  return forward(req, POST_PATHS);
}
