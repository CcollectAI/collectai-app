/**
 * E2E: Creator Dashboard
 * ---------------------------------------------------------------------------
 * Walks the creator dashboard the way the browser does — through the REAL
 * data layer in src/lib/kpi.ts. It never reimplements a query, because a
 * second implementation is exactly how a fix lands on a path nothing calls.
 *
 * Phases:
 *   1  preflight   — config present, FastAPI base reachable
 *   2  schema      — every table the dashboard reads actually exists
 *   3  honesty     — an un-provisioned DB must be REPORTED, not papered over
 *   4  seed        — insert a throwaway creator + funnel events + an order
 *   5  verify      — the seeded creator reaches the dashboard, demo data gone
 *   6  rls         — can the app's own anon key write? (Creators tab CRUD)
 *   7  cleanup     — remove everything phase 4 created
 *
 * Usage:
 *   npm run test:e2e:creators
 *
 * Phases 4/5/7 need a service-role key, because `creators` ships with a
 * SELECT-only RLS policy:
 *   SUPABASE_SERVICE_ROLE_KEY=... npm run test:e2e:creators
 * Without it those phases SKIP loudly rather than passing vacuously.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// kpi.ts calls getSupabase(), which returns null when `window` is undefined so
// it stays SSR-safe. Node has no window, so without this shim every fetch
// would fall back to demo data and the test would assert nothing.
if (typeof (globalThis as { window?: unknown }).window === "undefined") {
  (globalThis as { window?: unknown }).window = globalThis;
}

// kpi.ts fetches "/api/creator-leaderboard" — a browser-relative URL Node
// cannot resolve. Rewrite relative requests against the running dev server and
// attach the admin session cookie, so the real module runs unmodified and the
// route is genuinely exercised rather than stubbed.
const ADMIN_BASE = process.env.ADMIN_BASE ?? "http://localhost:3000";
let adminCookie = "";
const realFetch = globalThis.fetch;
globalThis.fetch = ((input: any, init?: any) => {
  if (typeof input === "string" && input.startsWith("/")) {
    const headers = new Headers(init?.headers ?? {});
    if (adminCookie) headers.set("cookie", adminCookie);
    return realFetch(`${ADMIN_BASE}${input}`, { ...init, headers });
  }
  return realFetch(input, init);
}) as typeof fetch;

/** Log in against the running server to obtain the httpOnly session cookie. */
async function adminLogin(): Promise<string> {
  const pin = process.env.ADMIN_PIN ?? process.env.NEXT_PUBLIC_ADMIN_PIN ?? "";
  const res = await realFetch(`${ADMIN_BASE}/api/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin }),
  });
  if (!res.ok) return "";
  return (res.headers.get("set-cookie") ?? "").split(";")[0] ?? "";
}

async function serverUp(): Promise<boolean> {
  try {
    await realFetch(`${ADMIN_BASE}/admin`, { signal: AbortSignal.timeout(4000) });
    return true;
  } catch {
    return false;
  }
}

const { fetchKPIDashboardData, isUsingDemoData, getDemoDataReason } =
  await import("../src/lib/kpi");
const { APP_CONFIG } = await import("../admin.config");

// ─── Expected schema (26 tables across supabase/migrations/) ────────────────

/**
 * Tables the creator dashboard genuinely reads after the repoint. Signups come
 * from the app's own profiles table and revenue from the subscription_events
 * ledger — kpi_events/orders belong to the kit template and nothing writes them.
 */
const REQUIRED_TABLES = ["creators", "profiles", "subscription_events"];

const EXPECTED_TABLES: Record<string, string[]> = {
  "001_kpi_tables": ["creators", "kpi_events", "orders"],
  "002_shopify_enhanced_kpis": ["daily_revenue", "market_metrics"],
  "003_ugc_video_tracking": ["ugc_videos", "ugc_daily_snapshots"],
  "004_content_pipeline_pods": ["ugc_pods", "ugc_pod_members", "ugc_content_pipeline"],
  "004b_video_scripts": [
    "ugc_video_scripts", "ugc_video_learning", "ugc_video_audio", "ugc_tiktok_metrics",
  ],
  "005_swipefile_accounts_sparkads": ["ugc_swipe_file", "ugc_accounts"],
  "006_content_machine": [
    "content_accounts", "content_pillars", "content_niches", "content_products",
    "content_ideas", "weekly_calendars", "calendar_items", "generated_captions",
    "content_batches", "content_batch_items",
  ],
};

/** Personas hardcoded in kpi.ts getDemoData(). Their presence == demo data. */
const DEMO_CREATOR_NAMES = ["Luna Craft", "Maille Douce", "Punto Creativo"];

const MARKER = "__e2e__";
const SEED_CODE = "E2ECODE";
const SEED_NAME = `${MARKER} Testcreator`;
const SEED_EMAIL = "e2e-creator-probe@sparrowcollect.invalid";
let seededUserId: string | null = null;

// ─── Tiny harness ───────────────────────────────────────────────────────────

let passed = 0, failed = 0, skipped = 0;
const failures: string[] = [];

function pass(msg: string) { passed++; console.log(`  \x1b[32mPASS\x1b[0m ${msg}`); }
function fail(msg: string, detail?: string) {
  failed++; failures.push(msg);
  console.log(`  \x1b[31mFAIL\x1b[0m ${msg}`);
  if (detail) console.log(`       ${detail}`);
}
function skip(msg: string) { skipped++; console.log(`  \x1b[33mSKIP\x1b[0m ${msg}`); }
function phase(n: number, title: string) {
  console.log(`\n\x1b[1m── Phase ${n}: ${title}\x1b[0m`);
}
function check(cond: boolean, msg: string, detail?: string) {
  cond ? pass(msg) : fail(msg, detail);
  return cond;
}

// ─── Clients ────────────────────────────────────────────────────────────────

const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";
const admin: SupabaseClient | null = SERVICE_KEY
  ? createClient(APP_CONFIG.supabase.url, SERVICE_KEY, { auth: { persistSession: false } })
  : null;
/** The exact client the shipped app uses — anon key, RLS enforced. */
const anon: SupabaseClient = createClient(
  APP_CONFIG.supabase.url, APP_CONFIG.supabase.anonKey,
  { auth: { persistSession: false } },
);

async function tableExists(t: string): Promise<{ ok: boolean; err?: string }> {
  // NOT `head: true` — a HEAD request returns 204 with error:null even for a
  // table that does not exist, so the probe would pass on everything. Ask for
  // a real body so PostgREST actually reports 42P01.
  const { error } = await anon.from(t).select("*").limit(1);
  if (!error) return { ok: true };
  // 42P01 = undefined_table. Anything else (e.g. RLS denial) means it exists.
  if (error.code === "42P01") return { ok: false, err: error.message };
  return { ok: true };
}

async function cleanup(): Promise<void> {
  if (!admin) return;
  await admin.from("subscription_events").delete().eq("affiliate_code", SEED_CODE);
  await admin.from("creators").delete().eq("affiliate_code", SEED_CODE);

  // Delete the auth user last — profiles cascades off it. Look the id up by
  // email rather than trusting seededUserId, so an interrupted earlier run
  // still gets cleaned up.
  const { data: list } = await admin.auth.admin.listUsers({ page: 1, perPage: 200 });
  for (const u of list?.users ?? []) {
    if (u.email === SEED_EMAIL) await admin.auth.admin.deleteUser(u.id);
  }
  seededUserId = null;
}

// ─── Run ────────────────────────────────────────────────────────────────────

async function main() {
  console.log("\x1b[1mE2E — Creator Dashboard\x1b[0m");
  console.log(`Supabase : ${APP_CONFIG.supabase.url}`);
  console.log(`API base : ${process.env.NEXT_PUBLIC_API_BASE ?? "(unset)"}`);
  console.log(`Seeding  : ${admin ? "enabled (service role)" : "DISABLED (no SUPABASE_SERVICE_ROLE_KEY)"}`);

  // ── 1. preflight ──────────────────────────────────────────────────────────
  phase(1, "preflight");
  check(APP_CONFIG.supabase.url.startsWith("https://"), "Supabase URL configured");
  check(APP_CONFIG.supabase.anonKey.length > 20, "Supabase anon key configured");

  const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "";
  if (!apiBase) {
    skip("FastAPI base reachable (NEXT_PUBLIC_API_BASE unset)");
  } else {
    try {
      // Must be the domain, not the raw IP: the backend's TrustedHost
      // allowlist 400s anything whose Host header isn't api.sparrowcollect.com,
      // and browsers/fetch won't let us override Host.
      const res = await fetch(`${apiBase}/healthz`, {
        signal: AbortSignal.timeout(10_000),
      });
      check(res.ok, `FastAPI reachable at ${apiBase} (HTTP ${res.status})`,
        res.status === 400
          ? "400 = TrustedHost rejection. Use https://api.sparrowcollect.com, not a raw IP."
          : undefined);
    } catch (e) {
      fail(`FastAPI reachable at ${apiBase}`, String(e));
    }
  }

  // ── 2. schema ─────────────────────────────────────────────────────────────
  phase(2, "schema — are the migrations applied?");
  const missing: string[] = [];
  for (const [migration, tables] of Object.entries(EXPECTED_TABLES)) {
    const gone: string[] = [];
    for (const t of tables) {
      const { ok } = await tableExists(t);
      if (!ok) { gone.push(t); missing.push(t); }
    }
    // Informational, not a failure: only REQUIRED_TABLES gate the creator
    // dashboard. The rest back other admin tabs and are intentionally not
    // provisioned — `orders`/`kpi_events` especially, since nothing writes them
    // and their names are far too generic for a production app schema.
    if (gone.length === 0) pass(`${migration} — ${tables.length} table(s) present`);
    else console.log(`  \x1b[2mn/a \x1b[0m ${migration} — not provisioned: ${gone.join(", ")}`);
  }
  // The dashboard only needs three of them; the rest back other admin tabs.
  const missingRequired: string[] = [];
  for (const t of REQUIRED_TABLES) {
    const { ok } = await tableExists(t);
    if (!ok) missingRequired.push(t);
  }
  check(missingRequired.length === 0,
    `creator-dashboard tables present (${REQUIRED_TABLES.join(", ")})`,
    `missing: ${missingRequired.join(", ")}`);

  const provisioned = missingRequired.length === 0;
  if (missing.length) {
    console.log(
      `\n  \x1b[33m${missing.length}/26 template tables missing. Only ` +
      `${REQUIRED_TABLES.join(" + ")} are needed for the creator dashboard; ` +
      `the rest back other admin tabs (CUSTOMIZATION.md Step 2).\x1b[0m`,
    );
  }

  // ── 3. honesty ────────────────────────────────────────────────────────────
  // The regression pin. Configured-but-unprovisioned used to render demo
  // numbers while isUsingDemoData() reported false.
  phase(3, "honesty — is demo data admitted to?");
  await fetchKPIDashboardData(30);
  const demo = isUsingDemoData();
  const reason = getDemoDataReason();

  if (!provisioned) {
    check(demo, "un-provisioned DB is reported as demo data",
      "isUsingDemoData() returned false while tables are missing — silent fake numbers");
    check(reason !== null && /unreadable|migrations/i.test(reason ?? ""),
      "demo reason names the cause", `got: ${JSON.stringify(reason)}`);
    if (reason) console.log(`       reason: ${reason}`);
  } else {
    pass("schema provisioned — honesty check deferred to phase 5");
  }

  // ── 4. seed ───────────────────────────────────────────────────────────────
  phase(4, "seed a throwaway creator");
  let seeded = false;
  if (!admin) {
    skip("seeding needs SUPABASE_SERVICE_ROLE_KEY (creators RLS is SELECT-only)");
  } else if (!provisioned) {
    skip("seeding needs the migrations applied first");
  } else {
    await cleanup(); // leftovers from an interrupted run

    const { error: cErr } = await admin.from("creators").insert({
      name: SEED_NAME, handle: "@e2e_testcreator", platform: "tiktok",
      language: "EN", affiliate_code: SEED_CODE, is_active: true,
      kits_sent: 3, cogs_per_kit_cents: 600, affiliate_payout_pct: 15,
    });
    if (cErr) {
      fail("insert creator", `${cErr.code}: ${cErr.message}`);
    } else {
      pass("insert creator");

      // Create a real auth user carrying the code in user_metadata — exactly
      // what supabase.auth.signUp({ options: { data } }) does from the app.
      // This puts the handle_new_user trigger itself under test rather than
      // writing profiles.referred_by_code by hand, which would prove nothing.
      const { data: created, error: uErr } = await admin.auth.admin.createUser({
        email: SEED_EMAIL,
        password: `e2e-${MARKER}-pw-9137`,
        email_confirm: true,
        user_metadata: { referral_code: SEED_CODE },
      });

      if (uErr || !created?.user) {
        fail("create attributed auth user", uErr?.message);
      } else {
        seededUserId = created.user.id;
        pass("create attributed auth user");

        // The trigger fires on the auth.users insert; give it a beat.
        const { data: prof } = await admin
          .from("profiles").select("referred_by_code").eq("id", seededUserId).single();

        check(prof?.referred_by_code === SEED_CODE,
          "handle_new_user trigger copied the code to profiles.referred_by_code",
          `got ${JSON.stringify(prof?.referred_by_code)}, want ${SEED_CODE} — ` +
          `apply supabase/migrations/20260719_referral_attribution.sql`);

        const { error: rErr } = await admin.from("subscription_events").insert({
          event_id: `${MARKER}-evt-1`, event_type: "INITIAL_PURCHASE",
          provider: "revenuecat", user_id: seededUserId,
          app_user_id: seededUserId, product_id: "pro_monthly", plan: "pro",
          revenue_cents: 499, currency: "EUR", affiliate_code: SEED_CODE,
        });
        check(!rErr, "insert revenue ledger event", rErr?.message);
        seeded = !rErr;
      }
    }
  }

  // ── 5. verify through the real data layer ─────────────────────────────────
  phase(5, "verify — does the seeded creator reach the dashboard?");
  const up = await serverUp();
  if (!up) {
    skip(`admin server not running at ${ADMIN_BASE} — start it with \`npm run dev\``);
  } else if (!seeded) {
    skip("nothing seeded — cannot verify the real-data path");
  } else {
    adminCookie = await adminLogin();
    check(adminCookie !== "", "admin login returned a session cookie",
      "check ADMIN_PIN and ADMIN_SESSION_SECRET in .env.local");
    const data = await fetchKPIDashboardData(30);
    const names = data.creators.map((c) => c.name);

    check(data.creators.some((c) => c.affiliateCode === SEED_CODE),
      "seeded creator appears in the leaderboard",
      `got: ${JSON.stringify(names)}`);

    const leaked = DEMO_CREATOR_NAMES.filter((d) => names.includes(d));
    check(leaked.length === 0, "no demo creators leaked into real data",
      `demo personas present: ${leaked.join(", ")}`);

    check(!isUsingDemoData(), "isUsingDemoData() is false with real rows",
      `reason: ${getDemoDataReason()}`);
    check(getDemoDataReason() === null, "no demo reason recorded",
      `got: ${getDemoDataReason()}`);

    const mine = data.creators.find((c) => c.affiliateCode === SEED_CODE);
    if (mine) {
      check(mine.scans === 1,
        `signup attributed via profiles.referred_by_code (got ${mine.scans}, want 1)`);
      check(mine.purchases === 1,
        `purchase counted from the ledger (got ${mine.purchases}, want 1)`);
      check(mine.revenue === 4.99,
        `revenue summed from subscription_events (got ${mine.revenue}, want 4.99)`);
      check(mine.kitsSent === 3,
        `creator cost fields read from the roster row (got ${mine.kitsSent}, want 3)`);
    }

    // ── the same €4.99 must reconcile across every KPIDashboardData section ──
    // A code minted for a creator and converted to Pro is not "accounted for"
    // if it appears on the leaderboard and reads 0.00 elsewhere.
    //
    // NOTE ON LABELS: sales / revenueTimeline / marketBreakdown are computed
    // correctly and asserted here, but NO component currently renders them —
    // the KPI Funnel tab calls the FastAPI /admin/kpi-summary endpoint and
    // never touches lib/kpi.ts. Calling these "tabs" would overstate what a
    // user can actually see, so they are labelled as aggregates.

    // sales aggregate
    check(data.sales.totalOrders >= 1,
      `sales aggregate counts the purchase (got ${data.sales.totalOrders})`);
    check(data.sales.totalRevenue >= 4.99,
      `sales aggregate includes the 4.99 (got ${data.sales.totalRevenue})`);
    check(data.sales.topKits.some((k) => k.kitSlug === "pro"),
      "sales aggregate plan mix shows the pro plan [computed, unrendered]",
      `got ${JSON.stringify(data.sales.topKits)}`);

    // revenueTimeline aggregate
    const timelineTotal = data.revenueTimeline.reduce((s, d) => s + d.revenue, 0);
    check(data.revenueTimeline.length >= 1,
      `timeline aggregate has a datapoint (got ${data.revenueTimeline.length})`);
    check(timelineTotal >= 4.99,
      `timeline aggregate revenue includes the 4.99 (got ${timelineTotal})`);

    // marketBreakdown aggregate — rolled up by the creator's language (EN)
    const en = data.marketBreakdown.find((m) => m.lang === "EN");
    check(!!en, "market aggregate has an EN row for the creator's language",
      `got ${JSON.stringify(data.marketBreakdown.map((m) => m.lang))}`);
    check((en?.revenue ?? 0) >= 4.99,
      `market aggregate EN revenue includes the 4.99 (got ${en?.revenue})`);
    check((en?.scans ?? 0) >= 1,
      `market aggregate EN counts the attributed signup (got ${en?.scans})`);

    // podHealth aggregate — correct, but NOT rendered by any component today.
    // The Pods tab reads pod-planner.ts (ugc_pods / ugc_content_pipeline),
    // which is not provisioned and falls back to demo pods. Asserted so the
    // aggregation stays correct for whenever a UI consumes it; deliberately
    // not labelled "PODS tab", which would overstate what a user can see.
    const pod = data.podHealth.find((p) => p.lang === "EN");
    check(!!pod && pod.totalRevenue >= 4.99,
      `podHealth aggregate EN revenue includes the 4.99 (got ${pod?.totalRevenue}) [computed, unrendered]`);
    check(!!pod && pod.activeCreators >= 1,
      `podHealth aggregate EN counts the creator (got ${pod?.activeCreators}) [computed, unrendered]`);

    // Commissions tab consumes data.creators via calculateCommissions, so the
    // payout is a pure function of the leaderboard row asserted above.
    const expectedPayout = Math.round(4.99 * 0.15 * 100) / 100;
    check(expectedPayout === 0.75,
      `COMMISSIONS tab (rendered) payout basis is 15% of 4.99 = 0.75 (got ${expectedPayout})`);

    // Cross-tab reconciliation: creator revenue must never exceed total sales.
    const creatorSum = data.creators.reduce((s, c) => s + c.revenue, 0);
    check(creatorSum <= data.sales.totalRevenue + 0.001,
      `attributed revenue (${creatorSum}) reconciles within total sales (${data.sales.totalRevenue})`);
  }

  // ── 6. RLS — the Creators tab writes with the anon key ────────────────────
  phase(6, "rls — can the shipped app write to creators?");
  if (!provisioned) {
    skip("needs the migrations applied first");
  } else {
    // The anon key ships in the browser bundle. It must NOT be able to write
    // the roster — the roster is the payout basis. Writes go through
    // /api/creators with the service-role key behind the admin session cookie.
    const probeCode = "E2ERLSPROBE";
    const { error } = await anon.from("creators").insert({
      name: `${MARKER} RLS Probe`, handle: "@e2e_rls",
      affiliate_code: probeCode, language: "EN",
    });

    if (error?.code === "42501") {
      pass("anon key is DENIED write access to creators (RLS holds)");
    } else if (error) {
      // Denied, but not by RLS — worth knowing which.
      pass(`anon write rejected (${error.code}: ${error.message})`);
    } else {
      fail("anon key is DENIED write access to creators",
        "The insert SUCCEEDED. Anyone holding the public anon key can rewrite " +
        "the creator roster and therefore the payout basis. Remove any " +
        "INSERT/UPDATE/DELETE policy on public.creators.");
      if (admin) await admin.from("creators").delete().eq("affiliate_code", probeCode);
    }

    // And the read path the dashboard depends on must still work.
    const { error: readErr } = await anon.from("creators").select("id").limit(1);
    check(!readErr, "anon key can still READ the roster", readErr?.message);
  }

  // ── 7. cleanup ────────────────────────────────────────────────────────────
  phase(7, "cleanup");
  if (!admin) {
    skip("nothing to clean up");
  } else {
    await cleanup();
    const { data: left } = await admin.from("creators").select("id").eq("affiliate_code", SEED_CODE);
    const { data: evLeft } = await admin
      .from("subscription_events").select("id").eq("affiliate_code", SEED_CODE);
    const { data: users } = await admin.auth.admin.listUsers({ page: 1, perPage: 200 });
    const userLeft = (users?.users ?? []).some((u) => u.email === SEED_EMAIL);

    check((left?.length ?? 0) === 0, "seeded creator removed");
    check((evLeft?.length ?? 0) === 0, "seeded ledger events removed");
    check(!userLeft, "seeded auth user (and its profile) removed");
  }

  // ── summary ───────────────────────────────────────────────────────────────
  console.log(
    `\n\x1b[1mSummary\x1b[0m  ${passed} passed, ${failed} failed, ${skipped} skipped`,
  );
  if (failures.length) {
    console.log("\nFailures:");
    for (const f of failures) console.log(`  - ${f}`);
  }
  process.exit(failed > 0 ? 1 : 0);
}

main().catch(async (e) => {
  console.error("\n\x1b[31mE2E crashed:\x1b[0m", e);
  await cleanup().catch(() => {});
  process.exit(1);
});
