/**
 * demoState — per-source demo reporting.
 *
 * This pins the bug the keyed registry was built to fix: a single module-global
 * `demoReason` meant one tab's fallback made EVERY tab show "Demo Mode", and a
 * tab whose module never reported showed nothing while rendering fake numbers.
 * A banner that cries wolf gets ignored, so cross-contamination is the failure
 * that matters most here.
 *
 * Run: npm run test:demo-state
 */

import {
  noteDemo,
  noteUnprovisioned,
  clearDemo,
  getDemoReason,
  getUnprovisionedTables,
  isUsingDemoData,
  allDemoSources,
} from "../src/lib/demoState";

let passed = 0, failed = 0;
function check(name: string, ok: boolean, detail?: unknown) {
  if (ok) { passed++; console.log(`  \x1b[32mPASS\x1b[0m ${name}`); }
  else { failed++; console.log(`  \x1b[31mFAIL\x1b[0m ${name}${detail !== undefined ? `   -> ${JSON.stringify(detail)}` : ""}`); }
}

function reset() {
  for (const s of ["kpi", "pods", "ugc", "swipe", "accounts", "boost", "video", "api"] as const) {
    clearDemo(s);
  }
}

console.log("\x1b[1mdemoState — per-source isolation\x1b[0m\n");

// ── the cross-contamination bug ────────────────────────────────────────────
reset();
noteDemo("pods", "ugc_pods not provisioned", null);
check("a pods fallback does NOT mark kpi as demo", !isUsingDemoData("kpi"));
check("pods itself is marked", isUsingDemoData("pods"));
check("kpi reason stays null", getDemoReason("kpi") === null, getDemoReason("kpi"));
check("pods reason is readable", getDemoReason("pods") === "ugc_pods not provisioned", getDemoReason("pods"));

// ── the reverse direction ──────────────────────────────────────────────────
reset();
noteDemo("kpi", "no creators", null);
check("a kpi fallback does NOT mark pods as demo", !isUsingDemoData("pods"));
check("a kpi fallback does NOT mark api as demo", !isUsingDemoData("api"));

// ── clearing is scoped ─────────────────────────────────────────────────────
reset();
noteDemo("kpi", "x", null);
noteDemo("ugc", "y", null);
clearDemo("kpi");
check("clearing kpi leaves ugc reporting", isUsingDemoData("ugc"));
check("clearing kpi clears only kpi", !isUsingDemoData("kpi"));

// ── a fixed source stops reporting on the next fetch ───────────────────────
reset();
noteDemo("kpi", "creators table missing", null);
check("reports before the fix", isUsingDemoData("kpi"));
clearDemo("kpi"); // what fetchKPIDashboardData does at the top of every run
check("stops reporting once the fetch succeeds", !isUsingDemoData("kpi"));

// ── unprovisioned is NOT demo ──────────────────────────────────────────────
reset();
noteUnprovisioned("kpi", "orders", null);
check("unprovisioned does not set the demo flag", !isUsingDemoData("kpi"));
check("unprovisioned table is listed", getUnprovisionedTables("kpi").includes("orders"),
  getUnprovisionedTables("kpi"));
check("unprovisioned leaves the reason null", getDemoReason("kpi") === null, getDemoReason("kpi"));

// ── both states can coexist on one source ──────────────────────────────────
reset();
noteUnprovisioned("kpi", "orders", null);
noteDemo("kpi", "creators unreadable", null);
check("demo + unprovisioned coexist", isUsingDemoData("kpi") && getUnprovisionedTables("kpi").length === 1);

// ── values pass through untouched ──────────────────────────────────────────
reset();
const sentinel = { a: 1 };
check("noteDemo returns its value by reference", noteDemo("kpi", "r", sentinel) === sentinel);
check("noteUnprovisioned returns its value by reference",
  noteUnprovisioned("ugc", "t", sentinel) === sentinel);

// ── last write wins per source ─────────────────────────────────────────────
reset();
noteDemo("kpi", "first", null);
noteDemo("kpi", "second", null);
check("latest reason for a source wins", getDemoReason("kpi") === "second", getDemoReason("kpi"));

// ── overview listing ───────────────────────────────────────────────────────
reset();
noteDemo("pods", "p", null);
noteDemo("boost", "b", null);
const all = allDemoSources().map((d) => d.source).sort();
check("allDemoSources lists exactly the reporting sources",
  JSON.stringify(all) === JSON.stringify(["boost", "pods"]), all);

reset();
console.log(`\n\x1b[1mSummary\x1b[0m  ${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
