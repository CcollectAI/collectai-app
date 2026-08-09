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

/** Record that `source` served demo data, and return the value unchanged. */
export function noteDemo<T>(source: DemoSource, reason: string, value: T): T {
  reasons.set(source, reason);
  return value;
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
