"use client";

import { useEffect, useState, useCallback } from "react";
import {
  fetchKPIDashboardData,
} from "@/lib/kpi";
import { AdminDemoBanner } from "@/components/AdminDemoBanner";
import type { KPIDashboardData } from "@/lib/kpi";
import {
  calculateCommissions,
  exportCommissionsCSV,
} from "@/lib/commissions";
import type { CommissionSummary } from "@/lib/commissions";

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "All", days: 365 },
];

function formatEur(n: number): string {
  return `\u20AC${n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
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

function roiColor(roi: number): string {
  if (roi >= 3) return "text-emerald-600";
  if (roi >= 1) return "text-amber-600";
  return "text-red-600";
}

function roiBadgeColor(roi: number): string {
  if (roi >= 3) return "bg-emerald-100 text-emerald-700";
  if (roi >= 1) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-500",
  approved: "bg-amber-100 text-amber-700",
  paid: "bg-emerald-100 text-emerald-700",
};

export function AdminCommissionTracker() {
  const [data, setData] = useState<KPIDashboardData | null>(null);
  const [summary, setSummary] = useState<CommissionSummary | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchKPIDashboardData(days).then((d) => {
      setData(d);
      const periodLabel = days === 365 ? "All time" : `Last ${days} days`;
      const commissions = calculateCommissions(d.creators, periodLabel);
      setSummary(commissions);
      setLoading(false);
    });
  }, [days]);

  const handleExport = useCallback(() => {
    if (!summary) return;
    const csv = exportCommissionsCSV(summary);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `commissions-${summary.periodLabel.replace(/\s+/g, "-")}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [summary]);

  if (loading || !data || !summary) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 dark:border-slate-700 border-t-[#FF6B6B]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#0D1B2A] dark:text-white">Commission &amp; Payout Tracker</h2>
          <AdminDemoBanner />
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
                  : "bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-slate-600"
              }`}
            >
              {p.label}
            </button>
          ))}
          <button
            onClick={handleExport}
            aria-label="Export as CSV"
            className="ml-2 rounded-lg bg-gray-100 dark:bg-slate-700 px-3 py-1.5 text-xs font-semibold text-gray-600 dark:text-gray-300 transition hover:bg-gray-200 dark:hover:bg-slate-600"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
        <StatCard label="Total Revenue" value={formatEur(summary.totalRevenue)} />
        <StatCard label="Total Commissions" value={formatEur(summary.totalCommissions)} />
        <StatCard label="Total COGS" value={formatEur(summary.totalCOGS)} />
        <StatCard label="Net Profit" value={formatEur(summary.totalNetProfit)} />
        <StatCard label="Avg Commission Rate" value={`${summary.avgCommissionRate}%`} />
        <StatCard label="Avg ROI" value={`${summary.avgROI}x`} />
        <StatCard label="Blended ROAS" value={`${summary.totalCommissions > 0 ? (summary.totalRevenue / summary.totalCommissions).toFixed(1) : "0.0"}x`} sub="return per commission dollar" />
        <StatCard label="ACOS" value={`${summary.totalRevenue > 0 ? ((summary.totalCommissions / summary.totalRevenue) * 100).toFixed(1) : "0.0"}%`} sub="affiliate cost of sale" />
      </div>

      {/* Creator table */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-slate-700">
        <table className="w-full text-left text-xs">
          <thead className="bg-gray-50 dark:bg-slate-700 text-gray-500 dark:text-gray-400">
            <tr>
              <th className="px-3 py-2">Creator</th>
              <th className="px-3 py-2">Handle</th>
              <th className="px-3 py-2">Lang</th>
              <th className="px-3 py-2">Code</th>
              <th className="px-3 py-2 text-right">Orders</th>
              <th className="px-3 py-2 text-right">Revenue</th>
              <th className="px-3 py-2 text-right">Comm. %</th>
              <th className="px-3 py-2 text-right">Commission</th>
              <th className="px-3 py-2 text-right">Kits COGS</th>
              <th className="px-3 py-2 text-right">Net to Co.</th>
              <th className="px-3 py-2 text-right">ROI</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {summary.entries.map((e) => (
              <tr key={e.handle} className="border-t border-gray-100 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700">
                <td className="px-3 py-2.5 font-medium text-[#0D1B2A] dark:text-white">{e.creatorName}</td>
                <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{e.handle}</td>
                <td className="px-3 py-2.5">
                  <span className="rounded-full bg-gray-100 dark:bg-slate-700 px-2 py-0.5 text-[10px] font-semibold text-gray-600 dark:text-gray-300">
                    {e.language}
                  </span>
                </td>
                <td className="px-3 py-2.5 font-mono text-gray-500 dark:text-gray-400">{e.affiliateCode}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{e.orders}</td>
                <td className="px-3 py-2.5 text-right tabular-nums font-semibold">{formatEur(e.grossRevenue)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{e.commissionRate}%</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatEur(e.commissionAmount)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{formatEur(e.kitsSentCost)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums font-semibold">{formatEur(e.netToCompany)}</td>
                <td className="px-3 py-2.5 text-right">
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${roiBadgeColor(e.roi)}`}>
                    {e.roi}x
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${STATUS_COLORS[e.status] ?? STATUS_COLORS.pending}`}>
                    {e.status}
                  </span>
                </td>
              </tr>
            ))}
            {summary.entries.length === 0 && (
              <tr>
                <td colSpan={12} className="px-3 py-8 text-center text-gray-400 dark:text-gray-500">
                  No creator data for this period.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Totals row */}
      {summary.entries.length > 0 && (
        <div className="rounded-xl bg-[#0D1B2A] px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-4 text-xs text-white/70">
            <span>
              <span className="font-bold text-white">{summary.entries.length}</span> creators
            </span>
            <span>
              Revenue <span className="font-bold text-white">{formatEur(summary.totalRevenue)}</span>
            </span>
            <span>
              Commissions <span className="font-bold text-white">{formatEur(summary.totalCommissions)}</span>
            </span>
            <span>
              COGS <span className="font-bold text-white">{formatEur(summary.totalCOGS)}</span>
            </span>
            <span>
              Net Profit{" "}
              <span className={`font-bold ${summary.totalNetProfit >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {formatEur(summary.totalNetProfit)}
              </span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
