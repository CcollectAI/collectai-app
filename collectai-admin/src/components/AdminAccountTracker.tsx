"use client";

import { useEffect, useState } from "react";
import {
  fetchUGCDashboardData,
  fetchAccountAnalytics,
} from "@/lib/kpi";
import { AdminDemoBanner } from "@/components/AdminDemoBanner";
import type { UGCDashboardData, AccountAnalytics, TikTokAccount } from "@/lib/kpi";

/* ── Helpers ─────────────────────────────────────────────────────────────── */

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "All", days: 365 },
];

function formatPct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

function formatNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-[#0D1B2A]">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

function hitRateColor(rate: number): string {
  if (rate >= 0.25) return "bg-emerald-100 text-emerald-700";
  if (rate >= 0.10) return "bg-amber-100 text-amber-700";
  return "bg-gray-100 text-gray-500";
}

const LANG_BADGE: Record<string, string> = {
  DE: "bg-yellow-100 text-yellow-700",
  FR: "bg-blue-100 text-blue-700",
  IT: "bg-green-100 text-green-700",
  NL: "bg-orange-100 text-orange-700",
  EN: "bg-purple-100 text-purple-700",
  ES: "bg-red-100 text-red-700",
};

/* ── Component ───────────────────────────────────────────────────────────── */

export function AdminAccountTracker() {
  const [ugcData, setUgcData] = useState<UGCDashboardData | null>(null);
  const [analytics, setAnalytics] = useState<AccountAnalytics | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchUGCDashboardData(days).then(async (d) => {
      setUgcData(d);
      const a = await fetchAccountAnalytics(d.videos);
      setAnalytics(a);
      setLoading(false);
    });
  }, [days]);

  if (loading || !ugcData || !analytics) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-[#FF6B6B]" />
      </div>
    );
  }

  const { accounts, totalAccounts, totalFollowers, bestPerformingAccount, formatComparison } = analytics;

  // Collect all unique formats for heatmap columns
  const allFormats = Array.from(
    new Set(
      Object.values(formatComparison).flatMap((fmts) => Object.keys(fmts))
    )
  ).sort();

  // Find max avg views across all cells for color intensity
  let maxAvgViews = 1;
  for (const acctFormats of Object.values(formatComparison)) {
    for (const cell of Object.values(acctFormats)) {
      if (cell.avgViews > maxAvgViews) maxAvgViews = cell.avgViews;
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#0D1B2A]">Account Tracker</h2>
          <AdminDemoBanner source="accounts" />
        </div>
        <div className="flex items-center gap-2">
          {PERIODS.map((p) => (
            <button
              key={p.days}
              onClick={() => setDays(p.days)}
              aria-label={`Filter by ${p.label}`}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                days === p.days
                  ? "bg-[#0D1B2A] text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard label="Total Accounts" value={String(totalAccounts)} />
        <StatCard label="Total Followers" value={formatNum(totalFollowers)} />
        <StatCard label="Best Performing" value={bestPerformingAccount} sub="by avg views" />
      </div>

      {/* Account cards */}
      <div>
        <h3 className="mb-3 text-sm font-bold uppercase tracking-wider text-gray-500">Per-Account Performance</h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {accounts.map((acct) => (
            <AccountCard key={acct.id} account={acct} />
          ))}
        </div>
      </div>

      {/* Format heatmap */}
      <div>
        <h3 className="mb-3 text-sm font-bold uppercase tracking-wider text-gray-500">Format Heatmap (Avg Views)</h3>
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="px-3 py-2">Account</th>
                {allFormats.map((fmt) => (
                  <th key={fmt} className="px-3 py-2 text-center">{fmt}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {accounts.map((acct) => (
                <tr key={acct.id} className="border-t border-gray-100">
                  <td className="whitespace-nowrap px-3 py-2 font-medium text-[#0D1B2A]">@{acct.handle}</td>
                  {allFormats.map((fmt) => {
                    const cell = formatComparison[acct.handle]?.[fmt];
                    if (!cell || cell.videos === 0) {
                      return <td key={fmt} className="px-3 py-2 text-center text-gray-300">-</td>;
                    }
                    const intensity = Math.round((cell.avgViews / maxAvgViews) * 100);
                    const bg =
                      intensity >= 75
                        ? "bg-emerald-200 text-emerald-800"
                        : intensity >= 50
                          ? "bg-emerald-100 text-emerald-700"
                          : intensity >= 25
                            ? "bg-amber-100 text-amber-700"
                            : "bg-gray-100 text-gray-600";
                    return (
                      <td key={fmt} className="px-3 py-2 text-center">
                        <span className={`inline-block rounded-lg px-2 py-0.5 text-[10px] font-bold tabular-nums ${bg}`}>
                          {formatNum(cell.avgViews)}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ── Account Card ────────────────────────────────────────────────────────── */

function AccountCard({ account }: { account: TikTokAccount }) {
  const langBg = LANG_BADGE[account.language] || "bg-gray-100 text-gray-600";

  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      {/* Handle + language + followers */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-[#0D1B2A]">@{account.handle}</span>
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${langBg}`}>
            {account.language}
          </span>
        </div>
        <span className="text-xs tabular-nums text-gray-400">{formatNum(account.followers)} followers</span>
      </div>

      {/* Stats grid */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase text-gray-400">Videos</p>
          <p className="text-sm font-bold tabular-nums text-[#0D1B2A]">{account.totalVideos}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase text-gray-400">Total Views</p>
          <p className="text-sm font-bold tabular-nums text-[#0D1B2A]">{formatNum(account.totalViews)}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase text-gray-400">Avg Views</p>
          <p className="text-sm font-bold tabular-nums text-[#0D1B2A]">{formatNum(account.avgViews)}</p>
        </div>
      </div>

      {/* Hit rate */}
      <div className="mt-3 flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase text-gray-400">Hit Rate</span>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${hitRateColor(account.hitRate)}`}>
          {formatPct(account.hitRate)}
        </span>
      </div>

      {/* Best format + hook type */}
      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-600">
          Best format: {account.bestFormat}
        </span>
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-600">
          Best hook: {account.bestHookType}
        </span>
      </div>

      {/* Engagement rate */}
      <div className="mt-2 flex items-center gap-2">
        <span className="text-[10px] font-semibold uppercase text-gray-400">Engagement</span>
        <span className="text-xs font-bold tabular-nums text-[#0D1B2A]">{formatPct(account.engagementRate)}</span>
      </div>
    </div>
  );
}
