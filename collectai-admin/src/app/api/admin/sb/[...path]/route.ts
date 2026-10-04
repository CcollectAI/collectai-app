/**
 * /api/admin/sb/rest/v1/<table> — the ONE door between the admin browser and
 * Supabase.
 *
 * Why this route exists: the dashboard used to query Supabase from the browser
 * with NEXT_PUBLIC_SUPABASE_ANON_KEY, behind a PIN compared in the browser. To
 * make those queries work, the admin tables carried `USING (true)` policies
 * for `public` — so anyone holding the anon key (it ships in the mobile app
 * too) could read and rewrite them. Found 2026-09-22 (docs/CLASS_SWEEPS.md,
 * class J).
 *
 * Now `getSupabase()` points supabase-js at this route instead of at Supabase.
 * Every call site keeps its `.from(...)` code unchanged; this handler checks
 * the signed httpOnly admin cookie, allows only the tables below and only
 * PostgREST table paths (no rpc, no auth, no storage), then forwards the
 * request with the service-role key. The tables themselves deny anon.
 */

import { NextResponse } from "next/server";
import { adminAuthConfigured, isAdminRequest } from "@/lib/adminAuth";

/** Every table the dashboard queries from the browser (grepped 2026-09-22).
 *  A table not listed here is refused, not forwarded. `kpi_events` and
 *  `orders` were removed 2026-10-04: they do not exist, and kpi.ts no longer
 *  asks for them (UNPROVISIONED_TABLES there). */
const TABLES = new Set([
  "admin_content_config",
  "admin_dev_hub",
  "content_ideas",
  "creators",
  "ugc_accounts",
  "ugc_content_pipeline",
  "ugc_pods",
  "ugc_swipe_file",
  "ugc_tiktok_metrics",
  "ugc_video_scripts",
  "ugc_videos",
  "weekly_calendars",
]);

/** Request headers PostgREST needs; everything else (apikey, Authorization,
 *  Accept-Profile/Content-Profile, cookies) is dropped, not trusted. */
const FORWARD_REQ = ["accept", "content-type", "prefer", "range", "range-unit"];
const FORWARD_RES = ["content-type", "content-range", "preference-applied"];

/** PostgREST query params that are NOT row filters. */
const NON_FILTER = new Set(["select", "order", "limit", "offset", "on_conflict", "columns"]);

const PREFIX = "/api/admin/sb/rest/v1/";

/**
 * Every refusal from this route, in PostgREST's error shape. supabase-js reads
 * `code` and `message`; with only `{ error }` the dashboard printed
 * "ugc_swipe_file unreadable (undefined: undefined)" for a refused table, and
 * would print the same for an expired session (found 2026-10-04 while
 * mutation-testing test:tabs-real). `error` stays for callers that read it.
 */
function refuse(message: string, status: number): NextResponse {
  return NextResponse.json(
    { code: `ADMIN_PROXY_${status}`, message, error: message },
    { status },
  );
}

function guard(req: Request): NextResponse | null {
  const cfg = adminAuthConfigured();
  if (!cfg.ok) {
    return refuse(`Admin auth not configured. Missing: ${cfg.missing.join(", ")}`, 503);
  }
  if (!isAdminRequest(req)) {
    return refuse("Not authenticated (session expired? log in again)", 401);
  }
  return null;
}

async function forward(req: Request): Promise<Response> {
  const blocked = guard(req);
  if (blocked) return blocked;

  const url = new URL(req.url);
  if (!url.pathname.startsWith(PREFIX)) {
    return refuse("Only table requests are proxied", 404);
  }
  const table = url.pathname.slice(PREFIX.length);
  if (!TABLES.has(table)) {
    return refuse(`Table not allowed: ${table}`, 403);
  }

  // An unfiltered PATCH or DELETE rewrites the whole table. No dashboard call
  // does that, so refuse it rather than forward it with the service-role key.
  if (req.method === "PATCH" || req.method === "DELETE") {
    const hasFilter = [...url.searchParams.keys()].some((k) => !NON_FILTER.has(k));
    if (!hasFilter) {
      return refuse(`${req.method} needs a row filter`, 400);
    }
  }

  const base = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";
  const headers = new Headers({ apikey: key, Authorization: `Bearer ${key}` });
  for (const h of FORWARD_REQ) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }

  const upstream = await fetch(`${base}/rest/v1/${table}${url.search}`, {
    method: req.method,
    headers,
    body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.text(),
    cache: "no-store",
  });

  const out = new Headers();
  for (const h of FORWARD_RES) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  return new Response(req.method === "HEAD" ? null : await upstream.text(), {
    status: upstream.status,
    headers: out,
  });
}

export const GET = forward;
export const HEAD = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
