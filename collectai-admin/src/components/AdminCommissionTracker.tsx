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
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-[#0D1B2A]">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-400">{sub}</p>}
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
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-[#FF6B6B]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#0D1B2A]">Commission &amp; Payout Tracker</h2>
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
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {p.label}
            </button>
          ))}
          <button
            onClick={handleExport}
            aria-label="Export as CSV"
            className="ml-2 rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-semibold text-gray-600 transition hover:bg-gray-200"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Total Revenue" value={formatEur(summary.totalRevenue)} />
        <StatCard label="Total Commissions" value={formatEur(summary.totalCommissions)} />
        <StatCard label="Total COGS" value={formatEur(summary.totalCOGS)} />
        <StatCard label="Net Profit" value={formatEur(summary.totalNetProfit)} />
        <StatCard label="Avg Commission Rate" value={`${summary.avgCommissionRate}%`} />
        <StatCard label="Avg ROI" value={`${summary.avgROI}x`} />
      </div>

      {/* Creator table */}
      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="w-full text-left text-xs">
          <thead className="bg-gray-50 text-gray-500">
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
              <tr key={e.handle} className="border-t border-gray-100 hover:bg-gray-50">
                <td className="px-3 py-2.5 font-medium text-[#0D1B2A]">{e.creatorName}</td>
                <td className="px-3 py-2.5 text-gray-500">{e.handle}</td>
                <td className="px-3 py-2.5">
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-600">
                    {e.language}
                  </span>
                </td>
                <td className="px-3 py-2.5 font-mono text-gray-500">{e.affiliateCode}</td>
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
                <td colSpan={12} className="px-3 py-8 text-center text-gray-400">
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
