"use client";

import { useEffect, useState, useCallback } from "react";
import {
  fetchDashboardStats,
  type DashboardStats,
  fetchWorkerHealth,
  type WorkerStatus,
} from "@/lib/collectai-api";
import { MetricCard } from "@/components/ui/MetricCard";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TIFFANY = "#81D8D0";
const PIE_COLORS = ["#94A3B8", "#3B82F6", "#F59E0B"]; // free, pro, premium

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
      ok ? "bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400"
         : "bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400"
    }`}>
      <span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`} />
      {label}
    </span>
  );
}

function WorkerSummary({ workers }: { workers: WorkerStatus[] }) {
  const ok = workers.filter((w) => w.status === "ok").length;
  const overdue = workers.filter((w) => w.status === "overdue").length;
  const neverRun = workers.filter((w) => w.status === "never_run").length;
  const onDemand = workers.filter((w) => w.status === "on_demand").length;

  return (
    <div className="rounded-2xl bg-white dark:bg-slate-800 p-5 shadow-sm transition-colors">
      <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Worker Summary</p>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <span className="inline-flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />{ok} ok
        </span>
        {overdue > 0 && (
          <span className="inline-flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
            <span className="h-2.5 w-2.5 rounded-full bg-red-500 animate-pulse" />{overdue} overdue
          </span>
        )}
        {neverRun > 0 && (
          <span className="inline-flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />{neverRun} never run
          </span>
        )}
        {onDemand > 0 && (
          <span className="inline-flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
            <span className="h-2.5 w-2.5 rounded-full bg-blue-400" />{onDemand} on-demand
          </span>
        )}
        <span className="text-xs text-gray-400 dark:text-gray-500">({workers.length} total)</span>
      </div>
    </div>
  );
}

function SubscriptionChart({ subscriptions }: { subscriptions: Record<string, number> }) {
  const data = Object.entries(subscriptions).map(([plan, count]) => ({
    name: plan.charAt(0).toUpperCase() + plan.slice(1),
    value: count,
  }));
  if (data.length === 0) return null;

  return (
    <div className="rounded-2xl bg-white dark:bg-slate-800 p-5 shadow-sm transition-colors">
      <p className="mb-3 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Subscription Distribution</p>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={3} dataKey="value" stroke="none">
              {data.map((_, i) => (
                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Legend verticalAlign="bottom" height={30} formatter={(v: string) => <span className="text-xs text-gray-600 dark:text-gray-400">{v}</span>} />
            <Tooltip contentStyle={{ borderRadius: 8, border: "none", boxShadow: "0 2px 8px rgba(0,0,0,.12)", fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function CatalogBarChart({ pending, mapped }: { pending: number; mapped: number }) {
  const data = [
    { name: "Pending", value: pending, fill: "#F59E0B" },
    { name: "Mapped (7d)", value: mapped, fill: "#10B981" },
  ];
  return (
    <div className="h-32">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 0, right: 0, top: 0, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 11, fill: "#9CA3AF" }} axisLine={false} tickLine={false} />
          <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={20}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Bar>
          <Tooltip contentStyle={{ borderRadius: 8, border: "none", boxShadow: "0 2px 8px rgba(0,0,0,.12)", fontSize: 12 }} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CollectAIOverview() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [workers, setWorkers] = useState<WorkerStatus[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, w] = await Promise.all([fetchDashboardStats(), fetchWorkerHealth()]);
      setStats(s);
      setWorkers(w);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    }
  }, []);

  const { isRefreshing, lastRefresh, enabled, toggleEnabled } = useAutoRefresh({
    callback: load,
    interval: 60_000,
    enabled: true,
  });

  const loading = !stats && !error;

  // ── Loading state ──────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-7 w-48 animate-pulse rounded-lg bg-gray-200 dark:bg-slate-700" />
          <div className="h-8 w-20 animate-pulse rounded-lg bg-gray-200 dark:bg-slate-700" />
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      {/* ── Error banner ─────────────────────────────────────────────────── */}
      {error && (
        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-700 dark:text-red-400">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* ── Header row ───────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">CollectAI Overview</h2>
        <div className="flex items-center gap-3">
          {/* Auto-refresh indicator */}
          <button
            onClick={toggleEnabled}
            title={enabled ? "Auto-refresh ON (60s)" : "Auto-refresh OFF"}
            className={`flex items-center gap-1.5 rounded-lg px-2 py-1 text-[10px] font-medium transition ${
              enabled ? "bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400" : "bg-gray-100 dark:bg-slate-700 text-gray-400"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${enabled ? "bg-emerald-500 animate-pulse" : "bg-gray-300"}`} />
            {enabled ? "LIVE" : "PAUSED"}
          </button>
          {lastRefresh && (
            <span className="text-[10px] text-gray-400 dark:text-gray-500">{lastRefresh.toLocaleTimeString()}</span>
          )}
          <button
            onClick={load}
            disabled={isRefreshing}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#81D8D0] px-3 py-1.5 text-xs font-medium text-white shadow-sm transition hover:bg-[#5FBFB6] disabled:opacity-50"
          >
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {stats && (
        <>
          {/* ── Stats Grid (4 cols) ─────────────────────────────────────── */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <MetricCard
              label="Total Users"
              value={stats.total_users}
              subtitle={`+${stats.recent_signups} last 7 days`}
              trend={stats.recent_signups > 0 ? (stats.recent_signups / Math.max(stats.total_users - stats.recent_signups, 1)) * 100 : 0}
            />
            <MetricCard label="Total Items" value={stats.total_items} />
            <MetricCard label="Total Events" value={stats.total_events} />
            <MetricCard label="Beta Signups" value={stats.beta_signups} />
          </div>

          {/* ── Subscription + System Health row ──────────────────────────── */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SubscriptionChart subscriptions={stats.subscriptions} />

            <div className="rounded-2xl bg-white dark:bg-slate-800 p-5 shadow-sm transition-colors">
              <p className="mb-3 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">System Health</p>
              <div className="flex flex-wrap items-center gap-3">
                <StatusBadge label={`DB: ${stats.db_status}`} ok={stats.db_status === "connected"} />
                <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-50 dark:bg-slate-700 px-3 py-1 text-xs font-medium text-gray-700 dark:text-gray-300">
                  {stats.active_mandates} active mandates
                </span>
                <span className="inline-flex items-center rounded-full px-3 py-1 text-xs font-medium" style={{ background: `${TIFFANY}15`, color: TIFFANY }}>
                  v{stats.version}
                </span>
                <StatusBadge label={stats.dev_mode ? "Dev Mode" : "Production"} ok={!stats.dev_mode} />
              </div>
            </div>
          </div>

          {/* ── Catalog Intelligence ────────────────────────────────────── */}
          <div>
            <p className="mb-3 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Catalog Intelligence</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-2xl bg-white dark:bg-slate-800 p-5 shadow-sm transition-colors">
                <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Catalog Queue</p>
                <CatalogBarChart pending={stats.catalog_suggestions_pending} mapped={stats.catalog_suggestions_mapped_week} />
              </div>
              <div className="rounded-2xl bg-white dark:bg-slate-800 p-5 shadow-sm transition-colors">
                <MetricCard
                  label="Category Candidates"
                  value={stats.category_candidates_watching + stats.category_candidates_candidate}
                  subtitle={`${stats.category_candidates_watching} watching · ${stats.category_candidates_candidate} candidates`}
                />
              </div>
            </div>
          </div>

          {/* ── Worker Summary ──────────────────────────────────────────── */}
          {workers.length > 0 && <WorkerSummary workers={workers} />}
        </>
      )}
    </div>
  );
}
