"use client";

import { useEffect, useState, useCallback } from "react";
import {
  fetchKPIDashboardData,
  isUsingDemoData,
  exportCreatorsCSV,
  type KPIDashboardData,
  type DailyRevenue,
  type MarketMetrics,
  type PodHealth,
} from "@/lib/kpi";

// ─── Period Selector ────────────────────────────────────────────────────────

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "All", days: 365 },
] as const;

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatEUR(amount: number): string {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function pct(a: number, b: number): string {
  if (b === 0) return "0%";
  return `${Math.round((a / b) * 100)}%`;
}

function kitDisplayName(slug: string): string {
  return slug
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function downloadCSV(csv: string, filename: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Stat Card ──────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="border border-gray-200 rounded-lg p-4 bg-white">
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-2xl font-bold ${color || "text-[#0D1B2A]"}`}>
        {value}
      </p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

// ─── Funnel Bar ─────────────────────────────────────────────────────────────

function FunnelBar({
  label,
  value,
  maxValue,
  color,
  prevValue,
}: {
  label: string;
  value: number;
  maxValue: number;
  color: string;
  prevValue?: number;
}) {
  const widthPct = maxValue > 0 ? Math.max((value / maxValue) * 100, 2) : 0;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-700 font-medium">{label}</span>
        <div className="flex items-center gap-2">
          <span className="font-bold text-gray-900">
            {value.toLocaleString()}
          </span>
          {prevValue !== undefined && prevValue > 0 && (
            <span className="text-xs text-gray-400">
              {pct(value, prevValue)} of prev
            </span>
          )}
        </div>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-6 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${widthPct}%` }}
        />
      </div>
    </div>
  );
}

// ─── Funnel Overview ────────────────────────────────────────────────────────

function FunnelOverview({ funnel }: { funnel: KPIDashboardData["funnel"] }) {
  const max = Math.max(funnel.kitOpens, funnel.qrScans, 1);

  return (
    <div>
      <h3 className="text-lg font-bold text-[#0D1B2A] mb-4">
        Conversion Funnel
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
        <StatCard label="Kit Opens" value={funnel.kitOpens.toLocaleString()} sub="all sources" />
        <StatCard
          label="QR Scans"
          value={funnel.qrScans.toLocaleString()}
          sub={pct(funnel.qrScans, funnel.kitOpens) + " of opens"}
        />
        <StatCard
          label="Video 90%"
          value={funnel.videoWatch90.toLocaleString()}
          sub={pct(funnel.videoWatch90, funnel.videoPlays) + " watch-through"}
        />
        <StatCard
          label="Kit Completes"
          value={funnel.kitCompletes.toLocaleString()}
          sub={pct(funnel.kitCompletes, funnel.stepStarts)}
        />
        <StatCard
          label="Orders"
          value={funnel.orders.toLocaleString()}
          sub={pct(funnel.orders, funnel.kitOpens) + " overall"}
        />
      </div>

      <div className="space-y-3 bg-white border border-gray-200 rounded-lg p-4">
        <FunnelBar
          label="Kit Opens"
          value={funnel.kitOpens}
          maxValue={max}
          color="bg-[#0D1B2A]"
        />
        <FunnelBar
          label="Drop Landing Views"
          value={funnel.dropLandingViews}
          maxValue={max}
          color="bg-indigo-400"
          prevValue={funnel.kitOpens}
        />
        <FunnelBar
          label="QR Scans"
          value={funnel.qrScans}
          maxValue={max}
          color="bg-blue-600"
          prevValue={funnel.kitOpens}
        />
        <FunnelBar
          label="Step Starts"
          value={funnel.stepStarts}
          maxValue={max}
          color="bg-blue-500"
          prevValue={funnel.kitOpens}
        />
        <FunnelBar
          label="Video Plays"
          value={funnel.videoPlays}
          maxValue={max}
          color="bg-blue-400"
          prevValue={funnel.stepStarts}
        />
        <FunnelBar
          label="Video 90%+"
          value={funnel.videoWatch90}
          maxValue={max}
          color="bg-sky-400"
          prevValue={funnel.videoPlays}
        />
        <FunnelBar
          label="Step Completes"
          value={funnel.stepCompletes}
          maxValue={max}
          color="bg-cyan-500"
          prevValue={funnel.videoWatch90}
        />
        <FunnelBar
          label="Kit Completes"
          value={funnel.kitCompletes}
          maxValue={max}
          color="bg-teal-500"
          prevValue={funnel.stepCompletes}
        />
        <FunnelBar
          label="Buy Clicks"
          value={funnel.buyClicks}
          maxValue={max}
          color="bg-emerald-500"
          prevValue={funnel.kitCompletes}
        />
        <FunnelBar
          label="Orders"
          value={funnel.orders}
          maxValue={max}
          color="bg-emerald-600"
          prevValue={funnel.buyClicks}
        />
      </div>
    </div>
  );
}

// ─── Revenue Timeline (Sparkline) ───────────────────────────────────────────

function RevenueTimeline({ data }: { data: DailyRevenue[] }) {
  if (data.length === 0) return null;

  const maxRev = Math.max(...data.map((d) => d.revenue), 1);
  const totalRev = data.reduce((s, d) => s + d.revenue, 0);
  const totalOrders = data.reduce((s, d) => s + d.orders, 0);
  const chartHeight = 120;

  return (
    <div>
      <h3 className="text-lg font-bold text-[#0D1B2A] mb-4">
        Revenue Trend
      </h3>
      <div className="flex gap-3 mb-4">
        <StatCard
          label="Period Revenue"
          value={formatEUR(totalRev)}
        />
        <StatCard
          label="Period Orders"
          value={totalOrders}
        />
        <StatCard
          label="Avg Daily Revenue"
          value={formatEUR(Math.round(totalRev / data.length))}
        />
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <div
          className="flex items-end gap-[2px]"
          style={{ height: `${chartHeight}px` }}
        >
          {data.map((d, i) => {
            const barH = Math.max((d.revenue / maxRev) * chartHeight, 2);
            return (
              <div
                key={d.date}
                className="flex-1 group relative"
                style={{ height: `${chartHeight}px` }}
              >
                <div
                  className="absolute bottom-0 w-full bg-[#0D1B2A] rounded-t-sm opacity-80 hover:opacity-100 transition-opacity"
                  style={{ height: `${barH}px` }}
                />
                <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 hidden group-hover:block bg-gray-800 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                  {d.date}: {formatEUR(d.revenue)} ({d.orders} orders)
                </div>
                {/* Show date labels for first, middle, last */}
                {(i === 0 ||
                  i === data.length - 1 ||
                  i === Math.floor(data.length / 2)) && (
                  <div className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[10px] text-gray-400 whitespace-nowrap">
                    {d.date.slice(5)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <div className="h-5" /> {/* spacer for labels */}
      </div>
    </div>
  );
}

// ─── Creator Leaderboard ────────────────────────────────────────────────────

function CreatorLeaderboard({
  creators,
}: {
  creators: KPIDashboardData["creators"];
}) {
  const handleExport = () => {
    const csv = exportCreatorsCSV(creators);
    const date = new Date().toISOString().slice(0, 10);
    downloadCSV(csv, `sammysam-creators-${date}.csv`);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-[#0D1B2A]">
          Creator Leaderboard
        </h3>
        <button
          type="button"
          onClick={handleExport}
          className="px-3 py-1.5 text-xs font-medium bg-gray-100 text-gray-600 hover:bg-gray-200 rounded-md transition-colors"
        >
          Export CSV
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse border border-gray-300 text-sm">
          <thead>
            <tr className="bg-gray-50">
              <th className="border border-gray-300 px-3 py-2 text-center font-semibold text-gray-700 w-8">
                #
              </th>
              <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">
                Creator
              </th>
              <th className="border border-gray-300 px-3 py-2 text-center font-semibold text-gray-700">
                Lang
              </th>
              <th className="border border-gray-300 px-3 py-2 text-center font-semibold text-gray-700">
                Code
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Scans
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Activations
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Completes
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Orders
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Revenue
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Conv %
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Net ROI
              </th>
            </tr>
          </thead>
          <tbody>
            {creators.map((c, i) => (
              <tr
                key={c.affiliateCode}
                className={`hover:bg-gray-50 ${i < 3 ? "bg-blue-50/40" : ""}`}
              >
                <td className="border border-gray-300 px-3 py-2 text-center text-gray-500 font-medium">
                  {i + 1}
                </td>
                <td className="border border-gray-300 px-3 py-2">
                  <div className="font-medium text-gray-900">{c.name}</div>
                  <div className="text-xs text-gray-400">{c.handle}</div>
                </td>
                <td className="border border-gray-300 px-3 py-2 text-center">
                  <span className="inline-block px-1.5 py-0.5 bg-blue-50 text-[#0D1B2A] rounded text-xs font-medium">
                    {c.language}
                  </span>
                </td>
                <td className="border border-gray-300 px-3 py-2 text-center">
                  <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">
                    {c.affiliateCode}
                  </code>
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right text-gray-900">
                  {c.scans.toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right text-gray-900">
                  {c.activations.toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right text-gray-900">
                  {c.completions.toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right text-gray-900">
                  {c.purchases.toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right font-medium text-emerald-700">
                  {formatEUR(c.revenue)}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  <span
                    className={`font-medium ${c.conversionRate >= 4 ? "text-emerald-600" : c.conversionRate >= 3 ? "text-yellow-600" : "text-red-500"}`}
                  >
                    {c.conversionRate}%
                  </span>
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  <span
                    className={`font-medium ${c.netROI >= 0 ? "text-emerald-600" : "text-red-500"}`}
                  >
                    {formatEUR(c.netROI)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
          {creators.length > 0 && (
            <tfoot>
              <tr className="bg-gray-50 font-semibold">
                <td
                  className="border border-gray-300 px-3 py-2 text-right"
                  colSpan={4}
                >
                  Totals
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  {creators.reduce((s, c) => s + c.scans, 0).toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  {creators
                    .reduce((s, c) => s + c.activations, 0)
                    .toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  {creators
                    .reduce((s, c) => s + c.completions, 0)
                    .toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  {creators
                    .reduce((s, c) => s + c.purchases, 0)
                    .toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right text-emerald-700">
                  {formatEUR(creators.reduce((s, c) => s + c.revenue, 0))}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  {(() => {
                    const ts = creators.reduce((s, c) => s + c.scans, 0);
                    const tp = creators.reduce((s, c) => s + c.purchases, 0);
                    return ts > 0
                      ? `${Math.round((tp / ts) * 1000) / 10}%`
                      : "—";
                  })()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right text-emerald-700">
                  {formatEUR(creators.reduce((s, c) => s + c.netROI, 0))}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}

// ─── Sales Overview ─────────────────────────────────────────────────────────

function SalesOverviewSection({
  sales,
}: {
  sales: KPIDashboardData["sales"];
}) {
  return (
    <div>
      <h3 className="text-lg font-bold text-[#0D1B2A] mb-4">Sales Overview</h3>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-6">
        <StatCard label="Total Revenue" value={formatEUR(sales.totalRevenue)} />
        <StatCard label="Total Orders" value={sales.totalOrders} />
        <StatCard label="Avg Order Value" value={formatEUR(sales.avgOrderValue)} />
        <StatCard
          label="Cart Abandon Rate"
          value={`${sales.abandonedCartRate}%`}
          color={sales.abandonedCartRate > 70 ? "text-red-500" : "text-[#0D1B2A]"}
        />
        <StatCard
          label="Repeat Purchase"
          value={`${sales.repeatPurchaseRate}%`}
          sub="returning buyers"
          color={sales.repeatPurchaseRate >= 15 ? "text-emerald-600" : "text-[#0D1B2A]"}
        />
      </div>

      {sales.topKits.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-700 mb-2">
            Top Kits by Orders
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse border border-gray-300 text-sm max-w-lg">
              <thead>
                <tr className="bg-gray-50">
                  <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-700">
                    Kit
                  </th>
                  <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                    Orders
                  </th>
                  <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                    Revenue
                  </th>
                </tr>
              </thead>
              <tbody>
                {sales.topKits.map((kit) => (
                  <tr key={kit.kitSlug} className="hover:bg-gray-50">
                    <td className="border border-gray-300 px-3 py-2 font-medium text-gray-900">
                      {kitDisplayName(kit.kitSlug)}
                    </td>
                    <td className="border border-gray-300 px-3 py-2 text-right text-gray-900">
                      {kit.orders}
                    </td>
                    <td className="border border-gray-300 px-3 py-2 text-right text-emerald-700 font-medium">
                      {formatEUR(kit.revenue)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Market Breakdown ───────────────────────────────────────────────────────

function MarketBreakdownSection({ data }: { data: MarketMetrics[] }) {
  if (data.length === 0) return null;

  return (
    <div>
      <h3 className="text-lg font-bold text-[#0D1B2A] mb-4">
        Market Breakdown (by Language)
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse border border-gray-300 text-sm">
          <thead>
            <tr className="bg-gray-50">
              <th className="border border-gray-300 px-3 py-2 text-center font-semibold text-gray-700">
                Market
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Scans
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Activations
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Completions
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Orders
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Revenue
              </th>
              <th className="border border-gray-300 px-3 py-2 text-right font-semibold text-gray-700">
                Conv %
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((m) => (
              <tr key={m.lang} className="hover:bg-gray-50">
                <td className="border border-gray-300 px-3 py-2 text-center">
                  <span className="inline-block px-2 py-0.5 bg-blue-50 text-[#0D1B2A] rounded text-xs font-bold">
                    {m.lang}
                  </span>
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  {m.scans.toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  {m.activations.toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  {m.completions.toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  {m.orders.toLocaleString()}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right text-emerald-700 font-medium">
                  {formatEUR(m.revenue)}
                </td>
                <td className="border border-gray-300 px-3 py-2 text-right">
                  <span
                    className={`font-medium ${m.conversionRate >= 4 ? "text-emerald-600" : m.conversionRate >= 3 ? "text-yellow-600" : "text-red-500"}`}
                  >
                    {m.conversionRate}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Pod Health Cards ───────────────────────────────────────────────────────

function PodHealthCards({ pods }: { pods: PodHealth[] }) {
  if (pods.length === 0) return null;

  return (
    <div>
      <h3 className="text-lg font-bold text-[#0D1B2A] mb-4">Pod Health</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {pods.map((pod) => (
          <div
            key={pod.lang}
            className="border border-gray-200 rounded-lg p-4 bg-white"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="inline-block px-2.5 py-1 bg-[#0D1B2A] text-white rounded text-sm font-bold">
                {pod.lang}
              </span>
              <span className="text-xs text-gray-400">
                {pod.activeCreators} creator
                {pod.activeCreators !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Scans</span>
                <span className="font-medium text-gray-900">
                  {pod.totalScans.toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Revenue</span>
                <span className="font-medium text-emerald-700">
                  {formatEUR(pod.totalRevenue)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Avg Conv %</span>
                <span
                  className={`font-medium ${pod.avgConversionRate >= 4 ? "text-emerald-600" : pod.avgConversionRate >= 3 ? "text-yellow-600" : "text-red-500"}`}
                >
                  {pod.avgConversionRate}%
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Dashboard ─────────────────────────────────────────────────────────

export function AdminKPIDashboard() {
  const [data, setData] = useState<KPIDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const isDemo = isUsingDemoData();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await fetchKPIDashboardData(days);
      setData(d);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-8">
      {/* Header + period selector */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#0D1B2A]">
            Campaign KPI Dashboard
          </h2>
          {data && (
            <p className="text-xs text-gray-400 mt-0.5">
              {data.period.from} — {data.period.to}
            </p>
          )}
        </div>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.days}
              type="button"
              onClick={() => setDays(p.days)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
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

      {/* Demo data banner */}
      {isDemo && (
        <div className="bg-amber-50 border border-amber-200 rounded-md p-3">
          <p className="text-sm text-amber-800">
            <span className="font-semibold">Demo mode:</span> Showing sample
            data. Connect Supabase credentials in{" "}
            <code className="bg-amber-100 px-1 rounded text-xs">
              src/lib/supabase.ts
            </code>{" "}
            and run the migrations in{" "}
            <code className="bg-amber-100 px-1 rounded text-xs">
              supabase/migrations/
            </code>{" "}
            to see live metrics.
          </p>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#0D1B2A]" />
        </div>
      ) : data ? (
        <>
          <FunnelOverview funnel={data.funnel} />
          <RevenueTimeline data={data.revenueTimeline} />
          <CreatorLeaderboard creators={data.creators} />
          <SalesOverviewSection sales={data.sales} />
          <MarketBreakdownSection data={data.marketBreakdown} />
          <PodHealthCards pods={data.podHealth} />
        </>
      ) : (
        <p className="text-gray-500 text-center py-8">
          Failed to load dashboard data.
        </p>
      )}
    </div>
  );
}
