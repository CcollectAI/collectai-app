"use client";

import { useEffect, useState } from "react";
import {
  fetchUGCDashboardData,
  fetchBoostMetrics,
} from "@/lib/kpi";
import { AdminDemoBanner } from "@/components/AdminDemoBanner";
import type { UGCDashboardData, BoostMetrics } from "@/lib/kpi";

/* ── Helpers ─────────────────────────────────────────────────────────────── */

function formatNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatEur(n: number): string {
  return `\u20AC${n.toFixed(2)}`;
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-white dark:bg-slate-800 p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-[#0D1B2A] dark:text-white">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{sub}</p>}
    </div>
  );
}

function roasColor(roas: number): string {
  if (roas >= 3) return "bg-emerald-100 text-emerald-700";
  if (roas >= 1) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

function acosColor(acos: number): string {
  if (acos < 25) return "bg-emerald-100 text-emerald-700";
  if (acos < 50) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

function roiColor(roi: number): string {
  return roi >= 0 ? "text-emerald-600" : "text-red-600";
}

/* ── Component ───────────────────────────────────────────────────────────── */

export function AdminBoostTracker() {
  const [ugcData, setUgcData] = useState<UGCDashboardData | null>(null);
  const [metrics, setMetrics] = useState<BoostMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchUGCDashboardData(30).then(async (d) => {
      setUgcData(d);
      const m = await fetchBoostMetrics(d.videos);
      setMetrics(m);
      setLoading(false);
    });
  }, []);

  if (loading || !ugcData || !metrics) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 dark:border-slate-700 border-t-[#FF6B6B]" />
      </div>
    );
  }

  const {
    totalBoosted,
    totalSpend,
    totalBoostedViews,
    avgCPM,
    avgCPC,
    avgCPI,
    organicROI,
    boostedROI,
    boostedVideos,
  } = metrics;

  const totalBoostedRevenue = boostedVideos.reduce((s, v) => s + v.revenue, 0);
  const blendedROAS = totalSpend > 0 ? totalBoostedRevenue / totalSpend : 0;
  const blendedACOS = totalBoostedRevenue > 0 ? (totalSpend / totalBoostedRevenue) * 100 : 0;

  // Find max views for bar scaling
  const maxViews = Math.max(
    ...boostedVideos.map((v) => Math.max(v.organicViews, v.boostedViews)),
    1
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold text-[#0D1B2A] dark:text-white">Boost / Spark Ads Tracker</h2>
        <AdminDemoBanner source="boost" />
      </div>

      {/* Top stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
        <StatCard label="Boosted Videos" value={String(totalBoosted)} />
        <StatCard label="Total Spend" value={formatEur(totalSpend)} />
        <StatCard label="Boosted Views" value={formatNum(totalBoostedViews)} />
        <StatCard label="CPM" value={formatEur(avgCPM)} sub="cost per 1K views" />
        <StatCard label="CPC" value={formatEur(avgCPC)} sub="cost per click" />
        <StatCard label="CPI" value={formatEur(avgCPI)} sub="cost per install" />
        <StatCard label="ROAS" value={`${blendedROAS.toFixed(1)}x`} sub="return on ad spend" />
        <StatCard label="ACOS" value={`${blendedACOS.toFixed(1)}%`} sub="ad cost of sale" />
      </div>

      {/* Side-by-side ROI comparison */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-xl bg-white dark:bg-slate-800 p-6 shadow-sm text-center">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">Organic ROI</p>
          <p className={`mt-2 text-4xl font-extrabold tabular-nums ${roiColor(organicROI)}`}>
            {organicROI >= 0 ? "+" : ""}{(organicROI * 100).toFixed(0)}%
          </p>
          <div className="mx-auto mt-3 h-2 w-32 overflow-hidden rounded-full bg-gray-100 dark:bg-slate-700">
            <div
              className="h-full rounded-full bg-[#FF6B6B]"
              style={{ width: `${Math.min(Math.abs(organicROI) * 100, 100)}%` }}
            />
          </div>
          <p className="mt-2 text-[10px] text-gray-400 dark:text-gray-500">Revenue vs production cost (no ad spend)</p>
        </div>
        <div className="rounded-xl bg-white dark:bg-slate-800 p-6 shadow-sm text-center">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">Boosted ROI</p>
          <p className={`mt-2 text-4xl font-extrabold tabular-nums ${roiColor(boostedROI)}`}>
            {boostedROI >= 0 ? "+" : ""}{(boostedROI * 100).toFixed(0)}%
          </p>
          <div className="mx-auto mt-3 h-2 w-32 overflow-hidden rounded-full bg-gray-100 dark:bg-slate-700">
            <div
              className="h-full rounded-full bg-[#1E3A8A]"
              style={{ width: `${Math.min(Math.abs(boostedROI) * 100, 100)}%` }}
            />
          </div>
          <p className="mt-2 text-[10px] text-gray-400 dark:text-gray-500">Revenue vs (production + ad spend)</p>
        </div>
      </div>

      {/* Boosted videos table */}
      <div>
        <h3 className="mb-3 text-sm font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">Boosted Videos</h3>
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-slate-700">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 dark:bg-slate-700 text-gray-500 dark:text-gray-400">
              <tr>
                <th className="px-3 py-2">Hook</th>
                <th className="px-3 py-2 text-right">Organic Views</th>
                <th className="px-3 py-2 text-right">Boosted Views</th>
                <th className="px-3 py-2 text-right">Spend</th>
                <th className="px-3 py-2 text-right">Installs</th>
                <th className="px-3 py-2 text-right">Revenue</th>
                <th className="px-3 py-2 text-right">ROAS</th>
                <th className="px-3 py-2 text-right">ACOS</th>
              </tr>
            </thead>
            <tbody>
              {boostedVideos.map((v) => (
                <tr key={v.videoId} className="border-t border-gray-100 dark:border-slate-700">
                  <td className="max-w-[200px] truncate px-3 py-2.5 font-medium text-[#0D1B2A] dark:text-white">{v.hookText}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatNum(v.organicViews)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatNum(v.boostedViews)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatEur(v.spend)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{v.installs}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatEur(v.revenue)}</td>
                  <td className="px-3 py-2.5 text-right">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${roasColor(v.roas)}`}>
                      {v.roas.toFixed(1)}x
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${acosColor(v.revenue > 0 ? (v.spend / v.revenue) * 100 : 100)}`}>
                      {v.revenue > 0 ? ((v.spend / v.revenue) * 100).toFixed(1) : "—"}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Visual bar comparison: organic vs boosted views per video */}
      <div>
        <h3 className="mb-3 text-sm font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Organic vs Boosted Views
        </h3>
        <div className="space-y-3">
          {boostedVideos.map((v) => {
            const organicWidth = (v.organicViews / maxViews) * 100;
            const boostedWidth = (v.boostedViews / maxViews) * 100;
            return (
              <div key={v.videoId} className="rounded-xl bg-white dark:bg-slate-800 p-4 shadow-sm">
                <p className="mb-2 max-w-md truncate text-xs font-medium text-[#0D1B2A] dark:text-white">{v.hookText}</p>
                {/* Organic bar */}
                <div className="flex items-center gap-2">
                  <span className="w-16 text-right text-[10px] font-semibold text-gray-400 dark:text-gray-500">Organic</span>
                  <div className="flex-1">
                    <div className="h-5 overflow-hidden rounded-full bg-gray-100 dark:bg-slate-700">
                      <div
                        className="flex h-full items-center rounded-full bg-[#FF6B6B] px-2"
                        style={{ width: `${Math.max(organicWidth, 2)}%` }}
                      >
                        <span className="text-[10px] font-bold text-white">{formatNum(v.organicViews)}</span>
                      </div>
                    </div>
                  </div>
                </div>
                {/* Boosted bar */}
                <div className="mt-1 flex items-center gap-2">
                  <span className="w-16 text-right text-[10px] font-semibold text-gray-400 dark:text-gray-500">Boosted</span>
                  <div className="flex-1">
                    <div className="h-5 overflow-hidden rounded-full bg-gray-100 dark:bg-slate-700">
                      <div
                        className="flex h-full items-center rounded-full bg-[#1E3A8A] px-2"
                        style={{ width: `${Math.max(boostedWidth, 2)}%` }}
                      >
                        <span className="text-[10px] font-bold text-white">{formatNum(v.boostedViews)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
