"use client";

/**
 * ML Models — the pricing models the API is actually SERVING.
 *
 * Source (2026-09-27): GET /admin/models reads each category's
 * artifacts/<category>/active/model.json on the API server (what
 * app/ml/model_loader.py loads) plus its latest model_promotion_log decision;
 * GET /admin/metrics gives 7-day prediction volume per category.
 *
 * Before: the tab listed model_metrics / model_registry — clip-v1.0.0 rows last
 * written 2026-04-24, "Demo" and "TestCat" test rows — as if they were the
 * models, and offered Train / Activate buttons for endpoints that do not exist.
 */

import { useCallback, useEffect, useState } from "react";
import { fetchMetrics, fetchModelSummary } from "@/lib/collectai-api";
import type { CountsRow, ModelSummary } from "@/lib/collectai-api";

const STALE_DAYS = 90; // the watchdog's "stale model" line (docs/WATCHDOG.md)

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toISOString().slice(0, 16).replace("T", " ");
}

export function AdminMLModels() {
  const [summary, setSummary] = useState<ModelSummary | null>(null);
  const [counts, setCounts] = useState<CountsRow[]>([]);
  const [countsNote, setCountsNote] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, met] = await Promise.all([fetchModelSummary(), fetchMetrics()]);
      setSummary(m);
      setCounts(met.counts_7d ?? []);
      setCountsNote(met.warming ? (met.detail ?? "prediction counts are being computed") : met.stale ? "prediction counts are from the last cached refresh" : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !summary) {
    return <p className="py-20 text-center text-sm text-gray-500">Loading models…</p>;
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-6">
        <p className="text-red-800 font-medium">Could not load the models</p>
        <p className="text-red-600 text-sm mt-1">{error}</p>
        <button onClick={load} className="mt-3 rounded-lg px-3 py-1.5 bg-red-600 text-white text-sm hover:bg-red-700">
          Retry
        </button>
      </div>
    );
  }

  const models = summary?.models ?? [];
  const countFor = (cat: string) => counts.filter((c) => c.category === cat).reduce((s, c) => s + c.n, 0);
  const stale = models.filter((m) => m.age_days > STALE_DAYS);
  const reverted = models.filter((m) => m.last_decision && m.last_decision.promoted === false);
  const unevaluated = models.filter((m) => m.last_decision && (m.last_decision.holdout_n ?? 0) === 0);
  const newest = models.reduce<string | null>((a, m) => (!a || m.fitted_at > a ? m.fitted_at : a), null);
  const versionsOnDisk = models.reduce((s, m) => s + m.versions_on_disk, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white">ML Models — what is being served</h2>
        <button onClick={load} className="rounded-lg px-3 py-1.5 bg-gray-200 text-gray-700 text-sm hover:bg-gray-300">
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Categories served" value={String(models.length)} />
        <Stat label={`Older than ${STALE_DAYS} days`} value={String(stale.length)} warn={stale.length > 0} />
        <Stat label="Last retrain reverted" value={String(reverted.length)} warn={reverted.length > 0} />
        <Stat label="Newest fit" value={fmtDate(newest)} />
      </div>

      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm p-4 space-y-1 text-sm text-gray-600 dark:text-gray-300">
        <p>
          Models retrain once a week on the server (<code>model_retrain_worker</code>), which also decides promotion.
          There is nothing to trigger from here.
        </p>
        {unevaluated.length > 0 && (
          <p>
            {unevaluated.length} of {models.length} were promoted <strong>without a holdout</strong> (0 verified sales to
            test against — a launch dependency, docs/WATCHDOG.md). Until members mark items sold, the promotion gate
            cannot compare a new model with the old one.
          </p>
        )}
        <p>
          CV MAE is the cross-validated error at training time
          {models.some((m) => m.log_scale) ? " — in log-price units for log-scale models, not euros" : ""}.
        </p>
        <p className="text-xs text-gray-400">
          {versionsOnDisk} model versions on disk under <code>{summary?.root}</code>
          {summary?.unresolved?.length ? ` · no active model: ${summary.unresolved.join(", ")}` : ""}
          {summary?.promotion_error ? ` · ${summary.promotion_error}` : ""}
          {countsNote ? ` · ${countsNote}` : ""}
        </p>
      </div>

      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 dark:bg-slate-700 text-left text-gray-600 dark:text-gray-300">
                <th className="px-4 py-2">Category</th>
                <th className="px-4 py-2">Active version</th>
                <th className="px-4 py-2">Fitted (UTC)</th>
                <th className="px-4 py-2 text-right">Age</th>
                <th className="px-4 py-2 text-right">Train rows</th>
                <th className="px-4 py-2 text-right">CV MAE</th>
                <th className="px-4 py-2 text-right">Predictions 7d</th>
                <th className="px-4 py-2">Last retrain</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => {
                const d = m.last_decision;
                return (
                  <tr key={m.category} className="border-t border-gray-100 dark:border-slate-700">
                    <td className="px-4 py-2 font-medium text-gray-900 dark:text-white">{m.category}</td>
                    <td className="px-4 py-2">
                      <code className="text-xs bg-gray-100 dark:bg-slate-700 px-1.5 py-0.5 rounded">{m.version}</code>
                    </td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-300">{fmtDate(m.fitted_at)}</td>
                    <td className={`px-4 py-2 text-right ${m.age_days > STALE_DAYS ? "text-red-600 font-semibold" : "text-gray-700 dark:text-gray-300"}`}>
                      {m.age_days}d
                    </td>
                    <td className="px-4 py-2 text-right text-gray-700 dark:text-gray-300">{m.train_size?.toLocaleString() ?? "—"}</td>
                    <td className="px-4 py-2 text-right text-gray-700 dark:text-gray-300">
                      {m.cv_mae != null ? `${m.cv_mae.toFixed(2)}${m.log_scale ? " log" : " €"}` : "—"}
                    </td>
                    <td className="px-4 py-2 text-right text-gray-700 dark:text-gray-300">{countFor(m.category).toLocaleString()}</td>
                    <td className="px-4 py-2 text-xs" title={d?.reason ?? ""}>
                      {!d ? (
                        <span className="text-gray-400">no decision logged</span>
                      ) : d.promoted ? (
                        <span className="text-emerald-700">promoted {fmtDate(d.at)} · holdout {d.holdout_n ?? 0}</span>
                      ) : (
                        <span className="text-amber-700">
                          reverted {fmtDate(d.at)} · holdout {d.holdout_n ?? 0}
                          {d.old_mae != null && d.new_mae != null ? ` · ${d.new_mae.toFixed(2)} vs ${d.old_mae.toFixed(2)}` : ""}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {models.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-6 text-center text-gray-400">
                    No active model.json found under {summary?.root ?? "the artifacts root"}.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm p-4">
      <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${warn ? "text-amber-600" : "text-gray-900 dark:text-white"}`}>{value}</p>
    </div>
  );
}
