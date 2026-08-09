/**
 * /api/creators — service-role CRUD for the creator roster.
 *
 * Why this route exists: `creators` ships with a SELECT-only RLS policy
 * (001_kpi_tables.sql defines creators_read and no INSERT/UPDATE/DELETE), so
 * AdminCreatorManager's writes with the public anon key are rejected. The
 * tempting fix — adding permissive anon write policies — would let anyone
 * holding NEXT_PUBLIC_SUPABASE_ANON_KEY (i.e. anyone who loads the page)
 * rewrite the roster. Instead writes happen here, server-side, with the
 * service-role key, behind the signed admin session cookie.
 */

import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { adminAuthConfigured, isAdminRequest } from "@/lib/adminAuth";

/** Columns a client is allowed to set. Anything else is dropped, not trusted. */
const WRITABLE = [
  "name", "handle", "platform", "language", "affiliate_code",
  "is_active", "kits_sent", "cogs_per_kit_cents", "affiliate_payout_pct",
] as const;

function serviceClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
    process.env.SUPABASE_SERVICE_ROLE_KEY ?? "",
    { auth: { persistSession: false } },
  );
}

function pick(body: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of WRITABLE) if (k in body) out[k] = body[k];
  return out;
}

/**
 * Map a Postgres write error to an HTTP status the client can act on, instead
 * of leaking every constraint violation as a 500.
 *   23505 unique_violation   -> 409 (duplicate affiliate_code)
 *   23502 not_null_violation -> 400 (a required column was blank)
 *   23514 check_violation    -> 400 (e.g. payout % out of range)
 */
function writeError(error: { code?: string; message: string }): NextResponse {
  const status =
    error.code === "23505" ? 409 :
    error.code === "23502" || error.code === "23514" ? 400 :
    500;
  return NextResponse.json({ error: `${error.code}: ${error.message}` }, { status });
}

/** Shared gate: config present + valid session. */
function guard(req: Request): NextResponse | null {
  const cfg = adminAuthConfigured();
  if (!cfg.ok) {
    return NextResponse.json(
      { error: `Admin auth not configured. Missing: ${cfg.missing.join(", ")}` },
      { status: 503 },
    );
  }
  if (!isAdminRequest(req)) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }
  return null;
}

export async function GET(req: Request) {
  const blocked = guard(req);
  if (blocked) return blocked;

  const { data, error } = await serviceClient()
    .from("creators").select("*").order("name");

  if (error) {
    return NextResponse.json(
      { error: `${error.code}: ${error.message}` },
      { status: error.code === "42P01" ? 503 : 500 },
    );
  }
  return NextResponse.json({ creators: data ?? [] });
}

export async function POST(req: Request) {
  const blocked = guard(req);
  if (blocked) return blocked;

  let body: Record<string, unknown>;
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Malformed body" }, { status: 400 });
  }

  const row = pick(body);
  if (!row.name || !row.affiliate_code) {
    return NextResponse.json({ error: "name and affiliate_code are required" }, { status: 400 });
  }
  // Codes are compared upper-case throughout (signup normalises, the trigger
  // uppercases). Normalise on write so the roster cannot drift from the data.
  row.affiliate_code = String(row.affiliate_code).trim().toUpperCase();

  // `handle`, `platform` and `language` are NOT NULL in the schema. Default any
  // that were omitted rather than letting Postgres reject the insert with a
  // 23502 that would surface to the user as an opaque 500.
  if (row.handle === undefined || row.handle === null) row.handle = "";
  if (!row.platform) row.platform = "tiktok";
  if (!row.language) row.language = "en";

  const { data, error } = await serviceClient()
    .from("creators").insert(row).select().single();

  if (error) return writeError(error);
  return NextResponse.json({ creator: data }, { status: 201 });
}

export async function PATCH(req: Request) {
  const blocked = guard(req);
  if (blocked) return blocked;

  let body: Record<string, unknown>;
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Malformed body" }, { status: 400 });
  }

  const id = String(body.id ?? "");
  if (!id) return NextResponse.json({ error: "id is required" }, { status: 400 });

  const patch = pick(body);
  if (patch.affiliate_code) {
    patch.affiliate_code = String(patch.affiliate_code).trim().toUpperCase();
  }
  if (Object.keys(patch).length === 0) {
    return NextResponse.json({ error: "no writable fields supplied" }, { status: 400 });
  }

  const { data, error } = await serviceClient()
    .from("creators").update(patch).eq("id", id).select().single();

  if (error) return writeError(error);
  return NextResponse.json({ creator: data });
}

export async function DELETE(req: Request) {
  const blocked = guard(req);
  if (blocked) return blocked;

  const id = new URL(req.url).searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id is required" }, { status: 400 });

  const { error } = await serviceClient().from("creators").delete().eq("id", id);
  if (error) {
    return NextResponse.json({ error: `${error.code}: ${error.message}` }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
