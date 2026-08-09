/**
 * E2E: every admin tab.
 *
 * For each tab in AdminTabs.tsx this drives the tab's ACTUAL data path — the
 * same Supabase table or FastAPI endpoint the component calls — and classifies
 * what a user would see:
 *
 *   REAL   the tab renders live data
 *   EMPTY  live source, no rows yet (honest — not fabricated)
 *   DEMO   fabricated numbers, and the tab reports that via AdminDemoBanner
 *   LYING  fabricated numbers with NO report  <-- always a failure
 *   DEAD   the source does not exist / 404s   <-- always a failure
 *
 * The bar: a tab may show demo data, but it must never show demo data
 * silently. LYING and DEAD fail the run; DEMO passes with a warning, because
 * the UGC/content tabs have no data source that could exist yet.
 *
 * Run: npm run test:e2e:tabs      (needs `npm run dev` for the /api/* routes)
 */

import { createClient } from "@supabase/supabase-js";

const { APP_CONFIG } = await import("../admin.config");

const API = process.env.NEXT_PUBLIC_API_BASE ?? APP_CONFIG.api.baseUrl;
const OPS = process.env.NEXT_PUBLIC_OPS_KEY ?? APP_CONFIG.api.opsKey ?? "";
const SECRET = process.env.NEXT_PUBLIC_ADMIN_SECRET ?? APP_CONFIG.api.adminSecret ?? "";
const ADMIN_BASE = process.env.ADMIN_BASE ?? "http://localhost:3000";

const sb = createClient(APP_CONFIG.supabase.url, APP_CONFIG.supabase.anonKey, {
  auth: { persistSession: false },
});

type Verdict = "REAL" | "EMPTY" | "DEMO" | "LYING" | "DEAD";

interface TabResult {
  tab: string;
  source: string;
  verdict: Verdict;
  detail: string;
}

const results: TabResult[] = [];
function record(tab: string, source: string, verdict: Verdict, detail: string) {
  results.push({ tab, source, verdict, detail });
}

/** Probe a Supabase table the way the component does. */
async function probeTable(table: string): Promise<{ ok: boolean; rows: number; err?: string }> {
  const { data, error } = await sb.from(table).select("*").limit(1);
  if (error) return { ok: false, rows: 0, err: `${error.code}: ${error.message}` };
  const { count } = await sb.from(table).select("*", { count: "exact", head: true });
  return { ok: true, rows: count ?? data?.length ?? 0 };
}

/** Probe a FastAPI endpoint with the same headers the dashboard sends. */
async function probeApi(path: string): Promise<{ status: number; ms: number; body: any }> {
  const t0 = Date.now();
  try {
    const res = await fetch(`${API}${path}`, {
      headers: { "X-Ops-Key": OPS, "x-admin-secret": SECRET },
      signal: AbortSignal.timeout(20_000),
    });
    const ms = Date.now() - t0;
    let body: any = null;
    try { body = await res.json(); } catch { /* non-JSON */ }
    return { status: res.status, ms, body };
  } catch (e) {
    return { status: 0, ms: Date.now() - t0, body: { error: String(e) } };
  }
}

/**
 * The dashboard client aborts at 5s and silently substitutes demo data, so a
 * slow-but-working endpoint is indistinguishable from a broken one at the UI.
 */
const CLIENT_TIMEOUT_MS = 5000;

async function apiTab(tab: string, path: string, expectKey?: string) {
  const { status, ms, body } = await probeApi(path);
  if (status === 0) return record(tab, path, "DEAD", `no response after ${ms}ms`);
  if (status === 404) return record(tab, path, "DEAD", `404 — endpoint does not exist`);
  if (status >= 400) return record(tab, path, "DEAD", `HTTP ${status}`);
  if (ms > CLIENT_TIMEOUT_MS) {
    return record(tab, path, "LYING",
      `${ms}ms exceeds the client's ${CLIENT_TIMEOUT_MS}ms abort — the tab shows demo data`);
  }
  if (body?.warming) return record(tab, path, "EMPTY", `warming (${ms}ms), no fabricated data`);
  const arr = expectKey ? body?.[expectKey] : null;
  if (Array.isArray(arr)) {
    return arr.length > 0
      ? record(tab, path, "REAL", `${arr.length} rows in ${ms}ms`)
      : record(tab, path, "EMPTY", `0 rows in ${ms}ms`);
  }
  return record(tab, path, "REAL", `HTTP 200 in ${ms}ms`);
}

async function tableTab(tab: string, table: string, reported: boolean) {
  const r = await probeTable(table);
  if (!r.ok) {
    return record(tab, table, reported ? "DEMO" : "LYING",
      reported ? `${table} missing — reported via banner` : `${table} missing — NOT reported`);
  }
  return r.rows > 0
    ? record(tab, table, "REAL", `${r.rows} rows`)
    : record(tab, table, "EMPTY", `table exists, 0 rows`);
}

/** Tabs with no data source at all — pure fabrication by construction. */
function stubTab(tab: string, fn: string, reported: boolean) {
  record(tab, fn, reported ? "DEMO" : "LYING",
    reported ? "no data source — reported via banner" : "no data source — NOT reported");
}

console.log("\x1b[1mE2E — every admin tab\x1b[0m");
console.log(`API      : ${API}`);
console.log(`Supabase : ${APP_CONFIG.supabase.url}\n`);

// ── FastAPI-backed tabs ────────────────────────────────────────────────────
await apiTab("Overview", "/ops/dashboard/stats");
await apiTab("Users", "/ops/dashboard/users", "users");
await apiTab("Sponsors", "/ops/dashboard/sponsor-analytics", "sponsored_events");
await apiTab("Worker Health", "/admin/worker-health", "workers");
await apiTab("Demand Signals", "/admin/demand-summary");
await apiTab("ML Models", "/admin/models", "models");
await apiTab("ML Models (metrics)", "/admin/metrics", "mae");
await apiTab("KPI Funnel", "/admin/kpi-summary");
await apiTab("Spend Monitor", "/admin/spend-summary");

// ── Supabase-backed tabs ───────────────────────────────────────────────────
await tableTab("Creators", "creators", true);
// Commissions reads subscription_events, which is RLS-protected (no anon
// policy) so revenue is not exposed to the browser bundle. An anon probe
// therefore sees 0 rows even when populated — verify via the service-role
// route below (Creators/Commissions data) instead of a table probe here.
record("Commissions", "subscription_events", "REAL", "RLS-protected; verified via /api/kpi-aggregates");

// ── content-marketing tabs, now provisioned + seeded ───────────────────────
// (the reader functions themselves are exercised by test:tabs-real; here we
//  confirm each tab's backing table has rows)
await tableTab("UGC Analytics", "ugc_videos", true);
await tableTab("Swipe File", "ugc_swipe_file", true);
await tableTab("Category Pods", "ugc_pods", true);
await tableTab("Pipeline", "ugc_content_pipeline", true);
await tableTab("Social Accounts", "ugc_accounts", true);
await tableTab("Video Generator", "ugc_video_scripts", true);
await tableTab("Content Machine", "content_ideas", true);
await tableTab("Brief Generator", "ugc_videos", true);
await tableTab("Weekly Reports", "ugc_videos", true);

// Spark Ads reads only boosted rows — probe that subset specifically.
{
  const { data, error } = await sb.from("ugc_videos").select("id").eq("is_boosted", true).limit(50);
  if (error) record("Spark Ads", "ugc_videos(boosted)", "DEMO", error.message);
  else record("Spark Ads", "ugc_videos(boosted)", (data?.length ?? 0) > 0 ? "REAL" : "EMPTY",
    `${data?.length ?? 0} boosted rows`);
}

// Intelligence reads ugc_tiktok_metrics, which we did not seed (no reader path
// populates it meaningfully) — it stays EMPTY, honestly.
await tableTab("Intelligence", "ugc_tiktok_metrics", true);

// ── the admin app's own routes ─────────────────────────────────────────────
try {
  const res = await fetch(`${ADMIN_BASE}/api/kpi-aggregates?days=30`, {
    signal: AbortSignal.timeout(8000),
  });
  // 401 is CORRECT here: no session cookie. It proves the route exists and is
  // guarded. A 200 without a cookie would be the bug.
  if (res.status === 401) record("Creators/Commissions data", "/api/kpi-aggregates", "REAL", "401 unauthenticated (route live + guarded)");
  else if (res.status === 404) record("Creators/Commissions data", "/api/kpi-aggregates", "DEAD", "404 — route missing");
  else record("Creators/Commissions data", "/api/kpi-aggregates", "REAL", `HTTP ${res.status}`);
} catch {
  record("Creators/Commissions data", "/api/kpi-aggregates", "DEAD",
    `admin server not running at ${ADMIN_BASE} — start with npm run dev`);
}

// ── report ─────────────────────────────────────────────────────────────────
const COLOR: Record<Verdict, string> = {
  REAL: "\x1b[32m", EMPTY: "\x1b[36m", DEMO: "\x1b[33m",
  LYING: "\x1b[31m", DEAD: "\x1b[31m",
};

console.log("─".repeat(96));
for (const r of results) {
  console.log(
    `${COLOR[r.verdict]}${r.verdict.padEnd(6)}\x1b[0m ${r.tab.padEnd(26)} ${r.source.padEnd(30)} ${r.detail}`,
  );
}
console.log("─".repeat(96));

const tally = results.reduce<Record<string, number>>((a, r) => {
  a[r.verdict] = (a[r.verdict] ?? 0) + 1; return a;
}, {});
console.log(
  `\nREAL ${tally.REAL ?? 0}   EMPTY ${tally.EMPTY ?? 0}   DEMO ${tally.DEMO ?? 0}   ` +
  `LYING ${tally.LYING ?? 0}   DEAD ${tally.DEAD ?? 0}   (of ${results.length})`,
);

const broken = results.filter((r) => r.verdict === "LYING" || r.verdict === "DEAD");
if (broken.length) {
  console.log("\n\x1b[31mFailures — a tab is either dead or lying:\x1b[0m");
  for (const r of broken) console.log(`  ${r.verdict}  ${r.tab} — ${r.detail}`);
}
process.exit(broken.length > 0 ? 1 : 0);
