"use client";

/**
 * KPI Funnel — the acquisition numbers the server actually measures
 * (GET /admin/kpi-summary, admin_health_router.py).
 *
 * Rewritten 2026-09-27. The previous version rendered a template's shape —
 * funnel stages, usage, tiers, feature usage, a revenue chart, affiliate
 * partners — that the server has never returned. It could not tell: every
 * request was refused by CORS and any failure rendered "Waiting for data. KPI
 * data will appear once users start using the app", while prod had members.
 * Had the request succeeded, destructuring `funnel.quickscan_adds` would have
 * crashed the tab. Stages the server cannot measure are named from its own
 * `unavailable` list rather than drawn as zeros.
 */

import React, { useState, useEffect, useCallback } from "react";
import { MetricCard } from "@/components/ui/MetricCard";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { apiFetch } from "@/lib/collectai-api";

const sectionCls = "bg-white dark:bg-slate-800 rounded-2xl shadow-sm p-5 transition-colors";
const titleCls = "text-lg font-semibold text-gray-900 dark:text-white mb-4";

interface KPISummary {
  period_days: number;
  signups: number;
  attributed_signups: number;
  paid_events: number;
  paying_users: number;
  attributed_paid_events: number;
  revenue_eur: number;
  active_subscriptions: number;
  signup_to_paid_pct: number;
  unavailable?: string[];
}

const PERIODS = [7, 30, 90] as const;

async function fetchKPI(days: number): Promise<KPISummary> {
  const res = await apiFetch(`/admin/kpi-summary?days=${days}`);
  const text = await res.text();
  if (!res.ok) {
    let detail = text.slice(0, 300);
    try { detail = String((JSON.parse(text) as { detail?: unknown }).detail ?? detail); } catch { /* not JSON */ }
    throw new Error(`/admin/kpi-summary — HTTP ${res.status}: ${detail}`);
  }
  return JSON.parse(text) as KPISummary;
}

export function CollectAIKPIDashboard() {
  const [days, setDays] = useState<number>(30);
  const [data, setData] = useState<KPISummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await fetchKPI(days));
      setError(null);
    } catch (e) {
      setData(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 60_000);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white">KPI Funnel</h2>
        <div className="flex gap-1" role="group" aria-label="Period">
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setDays(p)}
              aria-pressed={days === p}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                days === p ? "bg-[#81D8D0] text-white" : "bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-gray-300"
              }`}
            >
              {p}d
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <strong>Could not load KPIs.</strong> {error}
        </div>
      )}

      {loading && !data && !error && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {data && (
        <>
          <section className={sectionCls}>
            <h3 className={titleCls}>Acquisition — last {data.period_days} days</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard label="Signups" value={data.signups} />
              <MetricCard
                label="Via a creator code"
                value={data.attributed_signups}
                subtitle={data.signups ? `${Math.round((data.attributed_signups / data.signups) * 100)}% of signups` : undefined}
              />
              <MetricCard label="Paying members" value={data.paying_users} subtitle={`${data.signup_to_paid_pct}% of signups`} />
              <MetricCard label="Active paid subscriptions" value={data.active_subscriptions} subtitle="all time, not just this period" />
            </div>
          </section>

          <section className={sectionCls}>
            <h3 className={titleCls}>Revenue — last {data.period_days} days</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <MetricCard label="Revenue" value={data.revenue_eur} prefix="€" formatter={(n) => n.toFixed(2)} />
              <MetricCard label="Paid events" value={data.paid_events} />
              <MetricCard label="Paid events via a creator" value={data.attributed_paid_events} />
            </div>
          </section>

          {data.unavailable && data.unavailable.length > 0 && (
            <section className={sectionCls}>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Not measured</h3>
              <ul className="list-disc pl-5 text-sm text-gray-500 dark:text-gray-400">
                {data.unavailable.map((u) => <li key={u}>{u}</li>)}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
