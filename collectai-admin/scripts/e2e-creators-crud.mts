/**
 * E2E: the /api/creators write path — the actual "Add / Edit / Delete Creator"
 * flow, exercised through the Next.js route with a real admin session cookie.
 *
 * Previously only two things were checked: that the route 401s without a cookie
 * and that the anon Supabase key is denied by RLS. Neither proves a logged-in
 * admin can actually manage the roster — this does, then cleans up after itself.
 *
 * Writes to the PROD creators table under a marker code and deletes everything
 * it created (even on failure). Needs `npm run dev` for the routes and a
 * SUPABASE_SERVICE_ROLE_KEY for guaranteed cleanup.
 *
 * Run: npm run test:creators-crud
 */

import { createClient } from "@supabase/supabase-js";

const { APP_CONFIG } = await import("../admin.config");
const ADMIN_BASE = process.env.ADMIN_BASE ?? "http://localhost:3000";
const PIN = process.env.ADMIN_PIN ?? process.env.NEXT_PUBLIC_ADMIN_PIN ?? "";
const MARKER = "E2ECRUD";

const svc = process.env.SUPABASE_SERVICE_ROLE_KEY
  ? createClient(APP_CONFIG.supabase.url, process.env.SUPABASE_SERVICE_ROLE_KEY, {
      auth: { persistSession: false },
    })
  : null;

let pass = 0, fail = 0;
const fails: string[] = [];
function check(name: string, ok: boolean, detail?: unknown) {
  if (ok) { pass++; console.log(`  \x1b[32mPASS\x1b[0m ${name}`); }
  else { fail++; fails.push(name); console.log(`  \x1b[31mFAIL\x1b[0m ${name}${detail !== undefined ? `  -> ${JSON.stringify(detail)}` : ""}`); }
}

let cookie = "";
async function api(method: string, path: string, body?: unknown) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (cookie) headers.cookie = cookie;
  const res = await fetch(`${ADMIN_BASE}${path}`, {
    method, headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(15_000),
  });
  let json: any = null;
  try { json = await res.json(); } catch { /* empty */ }
  return { status: res.status, json };
}

async function cleanup() {
  if (!svc) return;
  await svc.from("creators").delete().like("affiliate_code", `${MARKER}%`);
}

async function main() {
  console.log("\x1b[1mE2E — /api/creators CRUD\x1b[0m");
  console.log(`Admin: ${ADMIN_BASE}\nCleanup: ${svc ? "service role" : "DISABLED (set SUPABASE_SERVICE_ROLE_KEY)"}\n`);

  // reachability
  try {
    await fetch(`${ADMIN_BASE}/admin`, { signal: AbortSignal.timeout(4000) });
  } catch {
    console.log(`\x1b[31mAdmin server not running at ${ADMIN_BASE} — start with npm run dev\x1b[0m`);
    process.exit(1);
  }

  await cleanup(); // clear any leftovers from an interrupted run

  console.log("\x1b[1mauth gate\x1b[0m");
  const unauth = await api("POST", "/api/creators", { name: "x", affiliate_code: `${MARKER}NO` });
  check("write without a session cookie is 401", unauth.status === 401, unauth.status);

  // log in for a real cookie
  const login = await fetch(`${ADMIN_BASE}/api/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: PIN }),
  });
  cookie = (login.headers.get("set-cookie") ?? "").split(";")[0] ?? "";
  check("admin login issues a session cookie", cookie !== "", { status: login.status });

  console.log("\n\x1b[1mcreate\x1b[0m");
  const code = `${MARKER}1`;
  const created = await api("POST", "/api/creators", {
    name: "E2E Crud Creator", handle: "@e2e_crud", platform: "tiktok",
    language: "EN", affiliate_code: code.toLowerCase(), is_active: true,
    kits_sent: 4, cogs_per_kit_cents: 700, affiliate_payout_pct: 20,
  });
  check("POST returns 201", created.status === 201, created.status);
  const id = created.json?.creator?.id;
  check("created row has an id", !!id, created.json);
  check("affiliate_code was upper-cased server-side", created.json?.creator?.affiliate_code === code,
    created.json?.creator?.affiliate_code);

  console.log("\n\x1b[1mvalidation\x1b[0m");
  const noName = await api("POST", "/api/creators", { affiliate_code: `${MARKER}X` });
  check("POST without name is 400", noName.status === 400, noName.status);

  const dup = await api("POST", "/api/creators", { name: "dup", affiliate_code: code });
  check("duplicate affiliate_code is 409, not a silent second row", dup.status === 409, dup.status);

  const injected = await api("POST", "/api/creators", {
    name: "hax", affiliate_code: `${MARKER}2`, id: "spoofed", secret_admin: true,
  });
  check("unknown fields (id/secret_admin) are ignored, not trusted",
    injected.status === 201 && injected.json?.creator?.id !== "spoofed", injected.json?.creator?.id);

  console.log("\n\x1b[1mupdate\x1b[0m");
  const patched = await api("PATCH", "/api/creators", { id, affiliate_payout_pct: 25, is_active: false });
  check("PATCH returns 200", patched.status === 200, patched.status);
  check("PATCH persisted the new payout %", patched.json?.creator?.affiliate_payout_pct == 25,
    patched.json?.creator?.affiliate_payout_pct);
  check("PATCH persisted is_active=false", patched.json?.creator?.is_active === false,
    patched.json?.creator?.is_active);

  const patchNoId = await api("PATCH", "/api/creators", { affiliate_payout_pct: 9 });
  check("PATCH without id is 400", patchNoId.status === 400, patchNoId.status);

  console.log("\n\x1b[1mread-back through the service layer\x1b[0m");
  if (svc) {
    const { data } = await svc.from("creators").select("*").eq("id", id).single();
    check("row is readable and reflects the update", data?.affiliate_payout_pct == 25, data?.affiliate_payout_pct);
  }

  console.log("\n\x1b[1mdelete\x1b[0m");
  const del = await api("DELETE", `/api/creators?id=${encodeURIComponent(id)}`);
  check("DELETE returns 200", del.status === 200, del.status);
  if (svc) {
    const { data } = await svc.from("creators").select("id").eq("id", id);
    check("row is gone after delete", (data?.length ?? 0) === 0, data);
  }
  const delNoId = await api("DELETE", "/api/creators");
  check("DELETE without id is 400", delNoId.status === 400, delNoId.status);

  console.log("\n\x1b[1mcleanup\x1b[0m");
  await cleanup();
  if (svc) {
    const { data } = await svc.from("creators").select("id").like("affiliate_code", `${MARKER}%`);
    check("no marker rows remain", (data?.length ?? 0) === 0, data?.length);
  }

  console.log(`\n\x1b[1mSummary\x1b[0m  ${pass} passed, ${fail} failed`);
  if (fails.length) { console.log("\nFailures:"); for (const f of fails) console.log("  - " + f); }
  process.exit(fail > 0 ? 1 : 0);
}

main().catch(async (e) => {
  console.error("\n\x1b[31mCRUD E2E crashed:\x1b[0m", e);
  await cleanup().catch(() => {});
  process.exit(1);
});
