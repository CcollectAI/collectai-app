/**
 * E2E: do the content tabs render REAL data now?
 *
 * Drives the ACTUAL reader functions (kpi.ts, pod-planner.ts, video-generator.ts)
 * against the seeded prod tables and asserts, per source, that:
 *   - the function returned real rows, AND
 *   - isUsingDemoData(source) === false  (the demo banner would NOT show)
 *
 * This is the real display-seam check for the fabricated tabs. The earlier
 * all-tabs test only probed table existence; it hardcoded DEMO for the stub
 * tabs and never exercised the wiring.
 *
 * Run: npm run test:tabs-real   (no dev server needed — reads Supabase directly)
 */

// getSupabase() returns null when window is undefined (SSR guard). Shim it so
// the real reader code runs and actually queries.
if (typeof (globalThis as { window?: unknown }).window === "undefined") {
  (globalThis as { window?: unknown }).window = globalThis;
}

const kpi = await import("../src/lib/kpi");
const pods = await import("../src/lib/pod-planner");
const video = await import("../src/lib/video-generator");
const { isUsingDemoData, getDemoReason } = await import("../src/lib/demoState");

let pass = 0, fail = 0;
const fails: string[] = [];
function check(name: string, ok: boolean, detail?: unknown) {
  if (ok) { pass++; console.log(`  \x1b[32mREAL\x1b[0m ${name}`); }
  else { fail++; fails.push(name); console.log(`  \x1b[31mDEMO/FAIL\x1b[0m ${name}${detail !== undefined ? `  -> ${JSON.stringify(detail)}` : ""}`); }
}

console.log("\x1b[1mE2E — content tabs render REAL data\x1b[0m\n");

// ── UGC Analytics (ugc_videos) ──────────────────────────────────────────────
const ugc = await kpi.fetchUGCDashboardData(60);
check("UGC Analytics — videos loaded", ugc.videos.length > 0, ugc.videos.length);
check("UGC Analytics — not demo", !isUsingDemoData("ugc"), getDemoReason("ugc"));

// ── Social Accounts (fetchAccountAnalytics, now reads ugc_accounts) ─────────
const accounts = await kpi.fetchAccountAnalytics(ugc.videos);
check("Social Accounts — accounts loaded", accounts.totalAccounts > 0, accounts.totalAccounts);
check("Social Accounts — not demo (was unconditional stub)", !isUsingDemoData("accounts"), getDemoReason("accounts"));
check("Social Accounts — real follower counts from ugc_accounts",
  accounts.totalFollowers > 0, accounts.totalFollowers);

// ── Spark Ads (fetchBoostMetrics, now reads boost_* columns) ────────────────
const boost = await kpi.fetchBoostMetrics(ugc.videos);
check("Spark Ads — boosted videos loaded", boost.totalBoosted > 0, boost.totalBoosted);
check("Spark Ads — not demo (was unconditional stub)", !isUsingDemoData("boost"), getDemoReason("boost"));

// ── Swipe File (ugc_swipe_file) ─────────────────────────────────────────────
const swipe = await kpi.fetchSwipeFileData();
check("Swipe File — entries loaded", swipe.totalEntries > 0, swipe.totalEntries);
check("Swipe File — not demo", !isUsingDemoData("swipe"), getDemoReason("swipe"));

// ── Category Pods + Pipeline (ugc_pods, ugc_content_pipeline) ───────────────
const pod = await pods.fetchPodPlannerData();
check("Category Pods — pods loaded", pod.pods.length > 0, pod.pods.length);
check("Pipeline — items loaded", pod.pipeline.length > 0, pod.pipeline.length);
check("Pods/Pipeline — not demo", !isUsingDemoData("pods"), getDemoReason("pods"));

// ── Video Generator (ugc_video_scripts, via the async fetch) ────────────────
const scripts = await video.fetchVideoScriptsAsync();
check("Video Generator — scripts loaded", scripts.length > 0, scripts.length);
check("Video Generator — not demo (was sync stub)", !isUsingDemoData("video"), getDemoReason("video"));

// ── Content Machine (content_ideas) ─────────────────────────────────────────
// persistence.ts reads content_ideas; check it directly via the same client.
const { getSupabase } = await import("../src/lib/supabase");
const sb = getSupabase();
if (sb) {
  const { data: ideas } = await sb.from("content_ideas").select("id").limit(50);
  check("Content Machine — ideas in content_ideas", (ideas?.length ?? 0) > 0, ideas?.length);
}

console.log(`\n\x1b[1mSummary\x1b[0m  ${pass} real, ${fail} still demo/failed`);
if (fails.length) { console.log("\nStill not real:"); for (const f of fails) console.log("  - " + f); }
process.exit(fail > 0 ? 1 : 0);
