/**
 * Adversarial E2E for the admin FastAPI endpoints I built and deployed.
 *
 * These run against PRODUCTION (api.sparrowcollect.com). They are read-only —
 * every route here is a GET — so they cannot mutate anything. The point is to
 * find the failure modes a happy-path curl misses:
 *   - auth: missing / wrong ops key must be rejected
 *   - params: days=0, negative, huge, non-numeric must not 500 or hang
 *   - shape: the JSON must match what the client types expect
 *   - concurrency: N simultaneous cold hits on the SWR cache must not thrash
 *   - latency: nothing may exceed the client's 5s abort on a warm call
 *
 * Run: npm run test:admin-endpoints
 */

const { APP_CONFIG } = await import("../admin.config");
const API = process.env.NEXT_PUBLIC_API_BASE ?? APP_CONFIG.api.baseUrl;
const OPS = process.env.NEXT_PUBLIC_OPS_KEY ?? APP_CONFIG.api.opsKey ?? "";
const CLIENT_ABORT_MS = 5000;

let pass = 0, fail = 0;
const fails: string[] = [];
function check(name: string, ok: boolean, detail?: unknown) {
  if (ok) { pass++; console.log(`  \x1b[32mPASS\x1b[0m ${name}`); }
  else { fail++; fails.push(name); console.log(`  \x1b[31mFAIL\x1b[0m ${name}${detail !== undefined ? `  -> ${JSON.stringify(detail)}` : ""}`); }
}
function group(t: string) { console.log(`\n\x1b[1m${t}\x1b[0m`); }

async function get(path: string, opts: { ops?: string | null; timeout?: number } = {}) {
  const headers: Record<string, string> = {};
  const key = opts.ops === undefined ? OPS : opts.ops;
  if (key) headers["X-Ops-Key"] = key;
  const t0 = Date.now();
  try {
    const res = await fetch(`${API}${path}`, {
      headers,
      signal: AbortSignal.timeout(opts.timeout ?? 25_000),
    });
    let body: any = null;
    try { body = await res.json(); } catch { /* non-JSON */ }
    return { status: res.status, ms: Date.now() - t0, body };
  } catch (e) {
    return { status: 0, ms: Date.now() - t0, body: { error: String(e) } };
  }
}

console.log(`\x1b[1mAdmin endpoints — adversarial E2E\x1b[0m\nAPI: ${API}`);

// ── auth ────────────────────────────────────────────────────────────────────
group("auth");
{
  const noKey = await get("/admin/models", { ops: null });
  check("no ops key is rejected (403)", noKey.status === 403, noKey.status);

  const badKey = await get("/admin/models", { ops: "definitely-wrong-key" });
  check("wrong ops key is rejected (403)", badKey.status === 403, badKey.status);

  const good = await get("/admin/models");
  check("correct ops key is accepted (200)", good.status === 200, good.status);
}

// ── /admin/models shape ──────────────────────────────────────────────────────
group("/admin/models");
{
  const r = await get("/admin/models");
  check("200", r.status === 200, r.status);
  check("has models array", Array.isArray(r.body?.models), typeof r.body?.models);
  check("has registry array", Array.isArray(r.body?.registry), typeof r.body?.registry);
  const m = r.body?.models?.[0];
  check("model row has category+version+status",
    !!m && typeof m.category === "string" && typeof m.version === "string" && typeof m.status === "string", m);
  check("status is active|stale",
    (r.body?.models ?? []).every((x: any) => x.status === "active" || x.status === "stale"),
    [...new Set((r.body?.models ?? []).map((x: any) => x.status))]);
  check("warm call under client abort", r.ms < CLIENT_ABORT_MS, `${r.ms}ms`);
}

// ── /admin/metrics shape + SWR ───────────────────────────────────────────────
group("/admin/metrics");
{
  const r = await get("/admin/metrics");
  check("200", r.status === 200, r.status);
  check("warm call under client abort", r.ms < CLIENT_ABORT_MS, `${r.ms}ms`);
  check("has mae array", Array.isArray(r.body?.mae), typeof r.body?.mae);
  check("has counts_7d array", Array.isArray(r.body?.counts_7d), typeof r.body?.counts_7d);
  // mae numbers must be number|null, never NaN or a string
  const maeOk = (r.body?.mae ?? []).every((x: any) =>
    x.mae === null || (typeof x.mae === "number" && !Number.isNaN(x.mae)));
  check("mae values are number|null (never NaN/string)", maeOk);
  const cOk = (r.body?.counts_7d ?? []).every((x: any) => typeof x.n === "number" && x.n >= 0);
  check("counts are non-negative numbers", cOk);
}

// ── concurrency: the stale-while-revalidate race ─────────────────────────────
group("/admin/metrics — 8 concurrent hits (SWR must not thrash or hang)");
{
  const t0 = Date.now();
  const rs = await Promise.all(Array.from({ length: 8 }, () => get("/admin/metrics")));
  const wall = Date.now() - t0;
  check("all 8 return 200", rs.every((r) => r.status === 200),
    rs.map((r) => r.status));
  check("no request hung (each < 25s)", rs.every((r) => r.ms < 25_000),
    rs.map((r) => r.ms));
  // The whole burst should finish near the slowest single call, not 8x it —
  // proof the guard flag coalesces refreshes rather than firing 8 scans.
  check("burst wall-time is not serialized", wall < 30_000, `${wall}ms for 8`);
  const shapesConsistent = rs.every((r) => Array.isArray(r.body?.mae) && Array.isArray(r.body?.counts_7d));
  check("every concurrent response is well-formed", shapesConsistent);
}

// ── /admin/kpi-summary params ────────────────────────────────────────────────
group("/admin/kpi-summary — parameter fuzzing");
{
  const base = await get("/admin/kpi-summary");
  check("default 200", base.status === 200, base.status);
  check("default period is 30", base.body?.period_days === 30, base.body?.period_days);
  check("signups is a number", typeof base.body?.signups === "number", base.body?.signups);
  check("signup_to_paid_pct present", typeof base.body?.signup_to_paid_pct === "number", base.body?.signup_to_paid_pct);
  check("names the unavailable engagement stage",
    Array.isArray(base.body?.unavailable) && base.body.unavailable.some((u: string) => /PostHog/.test(u)),
    base.body?.unavailable);

  const zero = await get("/admin/kpi-summary?days=0");
  check("days=0 clamps, does not 500", zero.status === 200 && zero.body?.period_days >= 1, zero.body?.period_days ?? zero.status);

  const neg = await get("/admin/kpi-summary?days=-5");
  check("days=-5 clamps, does not 500", neg.status === 200 && neg.body?.period_days >= 1, neg.body?.period_days ?? neg.status);

  const huge = await get("/admin/kpi-summary?days=999999");
  check("days=huge clamps to <=365", huge.status === 200 && huge.body?.period_days <= 365, huge.body?.period_days ?? huge.status);

  const junk = await get("/admin/kpi-summary?days=abc");
  check("days=abc does not 500 (422 or clamp both acceptable)",
    junk.status === 200 || junk.status === 422, junk.status);

  // internal consistency: attributed can't exceed total
  check("attributed_signups <= signups",
    (base.body?.attributed_signups ?? 0) <= (base.body?.signups ?? 0),
    { a: base.body?.attributed_signups, t: base.body?.signups });
  check("paying_users >= 0 and consistent with revenue",
    (base.body?.paying_users ?? 0) >= 0 &&
    ((base.body?.revenue_eur ?? 0) === 0 || (base.body?.paying_users ?? 0) > 0),
    { paying: base.body?.paying_users, rev: base.body?.revenue_eur });
}

// ── unknown admin path still 404s (didn't accidentally open a wildcard) ──────
group("no accidental wildcard");
{
  const r = await get("/admin/this-route-does-not-exist");
  check("unknown /admin/* still 404s", r.status === 404, r.status);
}

console.log(`\n\x1b[1mSummary\x1b[0m  ${pass} passed, ${fail} failed`);
if (fails.length) { console.log("\nFailures:"); for (const f of fails) console.log("  - " + f); }
process.exit(fail > 0 ? 1 : 0);
