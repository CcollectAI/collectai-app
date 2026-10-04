/**
 * E2E: do the content tabs render REAL data?
 *
 * Drives the ACTUAL reader functions (kpi.ts, pod-planner.ts, video-generator.ts)
 * through the running dashboard's own /api/admin/sb proxy, logged in with
 * ADMIN_PIN exactly as the browser is, and asserts per source that:
 *   - the function returned real rows, AND
 *   - no zero-reason was recorded (getZeroReason(source) === null) and no demo
 *     data was served (isUsingDemoData(source) === false).
 *
 * Plus the KPI funnel: `kpi_events`/`orders` were never created, so they must
 * show as unprovisioned zeros WITHOUT a request being sent (2026-10-04).
 *
 * Run: npm run dev            (in another terminal; or set ADMIN_BASE)
 *      npm run test:tabs-real
 *
 * ⚠️ Rewritten 2026-10-04. Since the 09-27 proxy change (getSupabase() points
 * supabase-js at `${window.location.origin}/api/admin/sb`) the old version
 * crashed on its first reader: it shimmed `window = globalThis`, which has no
 * `location`. And its "not demo" checks could not fail. Since 09-27,
 * noteDemo() only marks a source as demo under NEXT_PUBLIC_ADMIN_DEMO=true;
 * otherwise it records a ZERO-REASON and zeroes the value. getZeroReason() is
 * the signal that a source failed or came back empty.
 */

const ADMIN_BASE = (process.env.ADMIN_BASE ?? "http://localhost:3000").replace(/\/$/, "");
const PIN = process.env.ADMIN_PIN ?? "";

function die(msg: string): never {
  console.error(`\x1b[31m${msg}\x1b[0m`);
  process.exit(2);
}

if (!PIN) die("ADMIN_PIN is not set (run via `npm run test:tabs-real`, which loads .env.local)");

// ── Log in exactly as the browser does; keep the httpOnly session cookie ────
let login: Response;
try {
  login = await fetch(`${ADMIN_BASE}/api/admin/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ pin: PIN }),
  });
} catch {
  die(`dashboard not reachable at ${ADMIN_BASE} — start it with \`npm run dev\` (or set ADMIN_BASE)`);
}
const cookie = (login.headers.get("set-cookie") ?? "").split(";")[0];
if (login.status !== 200 || !cookie) die(`login failed: HTTP ${login.status}${cookie ? "" : ", no session cookie"}`);

// ── Browser shim ────────────────────────────────────────────────────────────
// getSupabase() needs window.location.origin. Every request is resolved and
// sent the way a same-origin browser request would be (relative paths against
// the origin, the session cookie attached) and recorded, so the test can say
// what the dashboard ASKED for, not only what it rendered.
(globalThis as { window?: unknown }).window = { location: { origin: ADMIN_BASE } };

const requests: { url: string; status: number }[] = [];
const realFetch = globalThis.fetch;
globalThis.fetch = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
  let url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  if (url.startsWith("/")) url = ADMIN_BASE + url;
  const headers = new Headers(
    init.headers ?? (typeof input === "object" && !(input instanceof URL) ? input.headers : undefined),
  );
  if (url.startsWith(ADMIN_BASE)) headers.set("cookie", cookie);
  try {
    const res = await realFetch(url, { ...init, headers });
    requests.push({ url: url.replace(ADMIN_BASE, ""), status: res.status });
    return res;
  } catch (e) {
    requests.push({ url: url.replace(ADMIN_BASE, ""), status: -1 });
    throw e;
  }
}) as typeof fetch;

const kpi = await import("../src/lib/kpi");
const pods = await import("../src/lib/pod-planner");
const video = await import("../src/lib/video-generator");
const { isUsingDemoData, getDemoReason, getZeroReason } = await import("../src/lib/demoState");
type Source = Parameters<typeof isUsingDemoData>[0];

let pass = 0, fail = 0;
const fails: string[] = [];
function check(name: string, ok: boolean, detail?: unknown) {
  if (ok) { pass++; console.log(`  \x1b[32mREAL\x1b[0m ${name}`); }
  else { fail++; fails.push(name); console.log(`  \x1b[31mDEMO/FAIL\x1b[0m ${name}${detail !== undefined ? `  -> ${JSON.stringify(detail)}` : ""}`); }
}
/** A source is real only if it neither served demo data nor fell back to zeros. */
function checkLive(label: string, source: Source) {
  check(`${label} — no zeros fallback`, getZeroReason(source) === null, getZeroReason(source));
  check(`${label} — not demo`, !isUsingDemoData(source), getDemoReason(source));
}
const asked = (table: string) => requests.some((r) => r.url.includes(`/rest/v1/${table}`));

console.log(`\x1b[1mE2E — content tabs render REAL data\x1b[0m  (${ADMIN_BASE})\n`);

// ── UGC Analytics (ugc_videos) ──────────────────────────────────────────────
// ugc_videos holds 15 SEED rows (date_posted 2026-06-26..07-19, loaded 07-20,
// the day this test was written), and nothing has been posted since. A fixed
// 60-day window therefore went empty on ~09-17 and failed this test for a
// reason that is not a bug. Two separate questions now:
//   1. the 60-day view's empty state must carry the HONEST reason, not an error;
//   2. the wiring must return real rows over a window that contains data.
await kpi.fetchUGCDashboardData(60);
const ugc60Reason = getZeroReason("ugc");
check("UGC Analytics (60d) — empty or live, never an error",
  ugc60Reason === null || ugc60Reason.startsWith("no videos posted"), ugc60Reason);

const UGC_WIRING_DAYS = 365;
const ugc = await kpi.fetchUGCDashboardData(UGC_WIRING_DAYS);
check(`UGC Analytics (${UGC_WIRING_DAYS}d) — videos loaded`, ugc.videos.length > 0, ugc.videos.length);
checkLive(`UGC Analytics (${UGC_WIRING_DAYS}d)`, "ugc");

// ── Social Accounts (fetchAccountAnalytics, reads ugc_accounts) ─────────────
const accounts = await kpi.fetchAccountAnalytics(ugc.videos);
check("Social Accounts — accounts loaded", accounts.totalAccounts > 0, accounts.totalAccounts);
check("Social Accounts — real follower counts from ugc_accounts",
  accounts.totalFollowers > 0, accounts.totalFollowers);
checkLive("Social Accounts", "accounts");

// ── Spark Ads (fetchBoostMetrics, reads boost_* columns) ────────────────────
const boost = await kpi.fetchBoostMetrics(ugc.videos);
check("Spark Ads — boosted videos loaded", boost.totalBoosted > 0, boost.totalBoosted);
checkLive("Spark Ads", "boost");

// ── Swipe File (ugc_swipe_file) ─────────────────────────────────────────────
const swipe = await kpi.fetchSwipeFileData();
check("Swipe File — entries loaded", swipe.totalEntries > 0, swipe.totalEntries);
checkLive("Swipe File", "swipe");

// ── Category Pods + Pipeline (ugc_pods, ugc_content_pipeline) ───────────────
const pod = await pods.fetchPodPlannerData();
check("Category Pods — pods loaded", pod.pods.length > 0, pod.pods.length);
check("Pipeline — items loaded", pod.pipeline.length > 0, pod.pipeline.length);
checkLive("Pods/Pipeline", "pods");

// ── Video Generator (ugc_video_scripts, via the async fetch) ────────────────
const scripts = await video.fetchVideoScriptsAsync();
check("Video Generator — scripts loaded", scripts.length > 0, scripts.length);
checkLive("Video Generator", "video");

// ── Content Machine (content_ideas) ─────────────────────────────────────────
// persistence.ts reads content_ideas; check it directly via the same client.
// A null client is a FAILURE: it used to skip silently, which read as a pass.
const { getSupabase } = await import("../src/lib/supabase");
const sb = getSupabase();
check("Content Machine — Supabase client available", sb !== null);
if (sb) {
  const { data: ideas, error } = await sb.from("content_ideas").select("id").limit(50);
  check("Content Machine — ideas in content_ideas", (ideas?.length ?? 0) > 0, error?.message ?? ideas?.length);
}

// ── KPI funnel: unprovisioned tables are zeros and are NEVER requested ──────
const dash = await kpi.fetchKPIDashboardData(30);
check("KPI — kpi_events never requested", !asked("kpi_events"));
check("KPI — orders never requested", !asked("orders"));
check("KPI — funnel is zeros", Object.values(dash.funnel).every((v) => v === 0), dash.funnel);
check("KPI — kpi_events shown as unprovisioned",
  kpi.getUnprovisionedSections().includes("kpi_events"), kpi.getUnprovisionedSections());
check("KPI — aggregates load (200)",
  requests.some((r) => r.url.startsWith("/api/kpi-aggregates") && r.status === 200));
check("KPI — creator rows are real", dash.creators.length > 0, dash.creators.length);

// ── Controls: the instrument itself ─────────────────────────────────────────
// Without these, "never requested" passes vacuously when nothing ran at all,
// which is exactly what the first draft of this check did on 2026-10-04.
check("CONTROL — requests were recorded", requests.length > 0, requests.length);
check("CONTROL — the sb proxy answered 2xx at least once",
  requests.some((r) => r.url.startsWith("/api/admin/sb/") && r.status >= 200 && r.status < 300));
check("no request failed", requests.every((r) => r.status >= 200 && r.status < 400),
  requests.filter((r) => r.status < 200 || r.status >= 400));

console.log(`\n\x1b[1mSummary\x1b[0m  ${pass} real, ${fail} still demo/failed  (${requests.length} requests)`);
if (fails.length) { console.log("\nStill not real:"); for (const f of fails) console.log("  - " + f); }
process.exit(fail > 0 ? 1 : 0);
