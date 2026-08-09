"use client";

import {
  getDemoReason,
  getUnprovisionedTables,
  isUsingDemoData,
  type DemoSource,
} from "@/lib/demoState";

/**
 * Tells the reader when the numbers above are fabricated.
 *
 * `source` is required on purpose. The previous version read one module-global
 * flag, so it fired on tabs showing live data merely because another tab had
 * fallen back, and stayed silent on tabs whose module never reported. Making
 * the caller name its source is what keeps the signal trustworthy.
 */
export function AdminDemoBanner({ source }: { source: DemoSource }) {
  const demo = isUsingDemoData(source);
  const missing = getUnprovisionedTables(source);

  // Nothing fabricated and nothing missing — say nothing.
  if (!demo && missing.length === 0) return null;

  const reason = getDemoReason(source);

  // Unprovisioned-only is a weaker, honest state: zeros because no table
  // exists, not invented numbers. Styled distinctly so the two don't blur.
  if (!demo) {
    return (
      <div
        role="status"
        className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-800/60"
      >
        <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">
          Showing zeros — no data source
        </p>
        <p className="mt-0.5 font-mono text-[10px] leading-relaxed text-slate-500 dark:text-slate-400">
          not provisioned: {missing.join(", ")}
        </p>
      </div>
    );
  }

  return (
    <div
      role="alert"
      className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-500/40 dark:bg-amber-500/10"
    >
      <div className="flex items-start gap-2.5">
        <svg
          className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
        <div>
          <p className="text-xs font-semibold text-amber-800 dark:text-amber-200">
            Demo Mode
          </p>
          <p className="mt-0.5 text-[11px] leading-relaxed text-amber-700 dark:text-amber-300/90">
            These numbers are sample data, not your metrics.
          </p>
          {reason && (
            <p className="mt-1 font-mono text-[10px] leading-relaxed text-amber-600 dark:text-amber-400/80">
              {reason}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
