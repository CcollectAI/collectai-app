/**
 * Per-source demo-data reporting.
 *
 * Why keyed rather than one global flag: `demoReason` used to be a single
 * module-level string in kpi.ts, set by whichever fetch ran last and reset only
 * by fetchKPIDashboardData. The result was a banner that lied in both
 * directions — the Creators tab, reading live rows, would show "Demo Mode"
 * merely because you had visited Pods first; and a tab whose own module never
 * reported would render fake numbers under a hidden banner.
 *
 * A truth signal that cries wolf is worse than no signal, because a reader
 * learns to ignore it. Each data source now reports independently and the
 * banner asks about the source it actually renders.
 *
 * Three distinct states, and only the second is "these numbers are fake":
 *   - real       — live rows
 *   - demo       — fabricated values standing in for data
 *   - unprovisioned — no backing table; rendered as zeros, which is honest
 */

export type DemoSource =
  | "kpi"       // creators / sales / timeline / market  (kpi.ts aggregates)
  | "pods"      // ugc_pods, ugc_content_pipeline        (pod-planner.ts)
  | "ugc"       // ugc_videos                            (kpi.ts UGC dashboard)
  | "swipe"     // ugc_swipe_file
  | "accounts"  // social accounts (no data source at all)
  | "boost"     // spark ads (no data source at all)
  | "video"     // video generator (no data source at all)
  | "api";      // FastAPI-backed tabs                   (collectai-api.ts)

const reasons = new Map<DemoSource, string>();
const unprovisioned = new Map<DemoSource, Set<string>>();
const zeroReasons = new Map<DemoSource, string>();

/**
 * Sample data is OPT-IN (2026-09-27). Every fallback in kpi.ts / pod-planner.ts
 * calls noteDemo with a sample value — for a failed read AND for an honest empty
 * one ("no videos in the last 30 days"). Without NEXT_PUBLIC_ADMIN_DEMO=true
 * the caller now gets the same SHAPE with every number zeroed and every list
 * emptied, and the banner says "Showing zeros — <reason>". One chokepoint
 * instead of ~20 call sites, and no component changes: they already render
 * whatever shape they are handed.
 */
export const DEMO_MODE = process.env.NEXT_PUBLIC_ADMIN_DEMO === "true";

/** Period labels survive zeroing so "last 30 days" still reads correctly. */
const KEEP_KEYS = new Set(["from", "to", "days"]);

export function zeroed<T>(value: T, key?: string): T {
  if (key && KEEP_KEYS.has(key)) return value;
  if (Array.isArray(value)) return [] as unknown as T;
  if (typeof value === "number") return 0 as unknown as T;
  if (typeof value === "boolean") return false as unknown as T;
  if (typeof value === "string") return "" as unknown as T;
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) out[k] = zeroed(v, k);
    return out as T;
  }
  return value;
}

/**
 * A section could not show real data. In demo mode: record it and return the
 * sample. Otherwise: return zeros of the same shape and record WHY.
 */
export function noteDemo<T>(source: DemoSource, reason: string, value: T): T {
  if (DEMO_MODE) {
    reasons.set(source, reason);
    return value;
  }
  zeroReasons.set(source, reason.replace(/\s*[—-]\s*showing sample (data|entries)\.?$/i, ""));
  return zeroed(value);
}

/** Why this source is showing zeros instead of rows (real mode only). */
export function getZeroReason(source: DemoSource): string | null {
  return zeroReasons.get(source) ?? null;
}

/**
 * Record that a section has no backing table. Deliberately NOT a demo reason:
 * rendering zeros because a table does not exist is honest, whereas rendering
 * invented numbers is not. Kept separate so the banner does not conflate them.
 */
export function noteUnprovisioned<T>(source: DemoSource, table: string, zeroValue: T): T {
  const set = unprovisioned.get(source) ?? new Set<string>();
  set.add(table);
  unprovisioned.set(source, set);
  return zeroValue;
}

/** Clear a source's state at the start of its fetch, so stale reasons cannot persist. */
export function clearDemo(source: DemoSource): void {
  reasons.delete(source);
  unprovisioned.delete(source);
  zeroReasons.delete(source);
}

/** Why this source is showing demo data, or null when its numbers are real. */
export function getDemoReason(source: DemoSource): string | null {
  return reasons.get(source) ?? null;
}

/** Tables this source needed but which do not exist. */
export function getUnprovisionedTables(source: DemoSource): string[] {
  return [...(unprovisioned.get(source) ?? [])];
}

/** True when this source's numbers are fabricated. */
export function isUsingDemoData(source: DemoSource): boolean {
  return reasons.has(source);
}

/** Every source currently serving demo data — for an at-a-glance overview. */
export function allDemoSources(): Array<{ source: DemoSource; reason: string }> {
  return [...reasons.entries()].map(([source, reason]) => ({ source, reason }));
}
