"use client";

import { useEffect, useState, useCallback } from "react";
import {
  fetchUGCDashboardData,
  exportUGCVideosCSV,
} from "@/lib/kpi";
import { AdminDemoBanner } from "@/components/AdminDemoBanner";
import type {
  UGCDashboardData,
  UGCVideo,
  VideoClassification,
} from "@/lib/kpi";

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "All", days: 365 },
];

const CLASS_COLORS: Record<VideoClassification, string> = {
  hit: "bg-emerald-100 text-emerald-700",
  average: "bg-amber-100 text-amber-700",
  fail: "bg-red-100 text-red-700",
  pending: "bg-gray-100 text-gray-500",
};

const CLASS_ACTIONS: Record<VideoClassification, string> = {
  hit: "Replicate 5-10x with new hooks",
  average: "Test new hooks on same visuals",
  fail: "Reuse visuals, completely new hook",
  pending: "Awaiting data",
};

function formatPct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

function formatNum(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
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

export function AdminUGCDashboard() {
  const [data, setData] = useState<UGCDashboardData | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [activeView, setActiveView] = useState<"overview" | "hooks" | "formats" | "clusters" | "creators" | "compare" | "trends" | "videos">("overview");
  const [compareA, setCompareA] = useState<string>("");
  const [compareB, setCompareB] = useState<string>("");

  useEffect(() => {
    setLoading(true);
    fetchUGCDashboardData(days).then((d) => {
      setData(d);
      setLoading(false);
    });
  }, [days]);

  const handleExport = useCallback(() => {
    if (!data) return;
    const csv = exportUGCVideosCSV(data.videos);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ugc-videos-${data.period.from}-to-${data.period.to}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [data]);

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-[#FF6B6B]" />
      </div>
    );
  }

  const { production, creative, business, classificationBreakdown } = data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-[#0D1B2A]">UGC / TikTok Analytics</h2>
          <AdminDemoBanner source="ugc" />
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

      {/* Classification breakdown */}
      <div className="grid grid-cols-4 gap-3">
        {(["hit", "average", "fail", "pending"] as VideoClassification[]).map((cls) => (
          <div key={cls} className={`rounded-xl p-4 ${CLASS_COLORS[cls]}`}>
            <p className="text-xs font-bold uppercase">{cls}</p>
            <p className="mt-1 text-3xl font-extrabold tabular-nums">{classificationBreakdown[cls]}</p>
            <p className="mt-1 text-[10px] opacity-70">{CLASS_ACTIONS[cls]}</p>
          </div>
        ))}
      </div>

      {/* Sub-navigation */}
      <div className="flex gap-1 border-b border-gray-200">
        {(["overview", "hooks", "formats", "clusters", "creators", "compare", "trends", "videos"] as const).map((view) => (
          <button
            key={view}
            onClick={() => setActiveView(view)}
            className={`px-4 py-2 text-xs font-semibold capitalize transition ${
              activeView === view
                ? "border-b-2 border-[#0D1B2A] text-[#0D1B2A]"
                : "text-gray-400 hover:text-gray-600"
            }`}
          >
            {view}
          </button>
        ))}
      </div>

      {/* Overview */}
      {activeView === "overview" && (
        <div className="space-y-6">
          {/* Production metrics */}
          <div>
            <h3 className="mb-3 text-sm font-bold text-gray-500 uppercase tracking-wider">Production</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Total Videos" value={String(production.totalVideos)} />
              <StatCard label="Cost / Video" value={`\u20AC${production.costPerVideo.toFixed(2)}`} />
              <StatCard label="Accounts" value={String(Object.keys(production.videosPerAccount).length)} />
              <StatCard label="Creators" value={String(Object.keys(production.videosPerCreator).length)} />
            </div>
          </div>

          {/* Creative metrics */}
          <div>
            <h3 className="mb-3 text-sm font-bold text-gray-500 uppercase tracking-wider">Creative Performance</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Hook Retention" value={formatPct(creative.avgHookRetention)} sub="3s viewers / total" />
              <StatCard label="Avg Watch Time" value={`${creative.avgWatchTime.toFixed(1)}s`} />
              <StatCard label="Completion Rate" value={formatPct(creative.avgCompletionRate)} />
              <StatCard label="Engagement Rate" value={formatPct(creative.avgEngagementRate)} sub="(likes+comments+shares)/views" />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Total Shares" value={formatNum(creative.totalShares)} />
              <StatCard label="Total Saves" value={formatNum(creative.totalSaves)} />
              <StatCard label="Amplification" value={formatPct(creative.avgAmplificationRate)} sub="shares / views" />
              <div />
            </div>
          </div>

          {/* Business metrics */}
          <div>
            <h3 className="mb-3 text-sm font-bold text-gray-500 uppercase tracking-wider">Business</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="CTR" value={formatPct(business.avgCTR)} sub="clicks / views" />
              <StatCard label="Installs" value={String(business.totalInstalls)} />
              <StatCard label="Conv. Rate" value={formatPct(business.avgConversionRate)} sub="installs / clicks" />
              <StatCard label="Revenue / Video" value={`\u20AC${business.revenuePerVideo.toFixed(2)}`} />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="CPA" value={`\u20AC${business.avgCPA.toFixed(2)}`} />
              <StatCard label="ROAS" value={`${business.avgROAS.toFixed(2)}x`} />
              <div />
              <div />
            </div>
          </div>

          {/* Top Performers */}
          <div>
            <h3 className="mb-3 text-sm font-bold text-gray-500 uppercase tracking-wider">Top 5 Performers</h3>
            <div className="overflow-x-auto rounded-xl border border-gray-200">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 text-gray-500">
                  <tr>
                    <th className="px-3 py-2">#</th>
                    <th className="px-3 py-2">Hook</th>
                    <th className="px-3 py-2">Creator</th>
                    <th className="px-3 py-2 text-right">Views</th>
                    <th className="px-3 py-2 text-right">Retention</th>
                    <th className="px-3 py-2 text-right">Shares</th>
                    <th className="px-3 py-2 text-right">Revenue</th>
                    <th className="px-3 py-2">Class</th>
                  </tr>
                </thead>
                <tbody>
                  {data.topPerformers.map((v, i) => (
                    <tr key={v.id} className="border-t border-gray-100">
                      <td className="px-3 py-2 font-bold text-gray-400">{i + 1}</td>
                      <td className="max-w-[200px] truncate px-3 py-2 font-medium text-[#0D1B2A]">{v.hookText}</td>
                      <td className="px-3 py-2 text-gray-500">{v.creatorName}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatNum(v.viewsTotal)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatPct(v.hookRetentionRate)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{v.shares}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{`\u20AC${(v.revenueCents / 100).toFixed(0)}`}</td>
                      <td className="px-3 py-2">
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${CLASS_COLORS[v.classification]}`}>
                          {v.classification}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Hook Analysis */}
      {activeView === "hooks" && (
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="px-3 py-2">Hook Text</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2 text-right">Videos</th>
                <th className="px-3 py-2 text-right">Avg Retention</th>
                <th className="px-3 py-2 text-right">Avg Views</th>
                <th className="px-3 py-2 text-right">Avg Shares</th>
              </tr>
            </thead>
            <tbody>
              {data.hookAnalysis.map((h) => (
                <tr key={h.hookText} className="border-t border-gray-100">
                  <td className="max-w-[300px] truncate px-3 py-2.5 font-medium text-[#0D1B2A]">{h.hookText}</td>
                  <td className="px-3 py-2.5">
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-600">{h.hookType}</span>
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{h.videoCount}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatPct(h.avgRetention)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatNum(h.avgViews)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{h.avgShares}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Format Analysis */}
      {activeView === "formats" && (
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="px-3 py-2">Format</th>
                <th className="px-3 py-2 text-right">Videos</th>
                <th className="px-3 py-2 text-right">Avg Watch Time</th>
                <th className="px-3 py-2 text-right">Completion Rate</th>
                <th className="px-3 py-2 text-right">Avg Views</th>
              </tr>
            </thead>
            <tbody>
              {data.formatAnalysis.map((f) => (
                <tr key={f.format} className="border-t border-gray-100">
                  <td className="px-3 py-2.5 font-semibold text-[#0D1B2A] capitalize">{f.format}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{f.videoCount}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{f.avgWatchTime.toFixed(1)}s</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatPct(f.avgCompletionRate)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatNum(f.avgViews)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Concept Clusters */}
      {activeView === "clusters" && (
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="px-3 py-2">Concept Cluster</th>
                <th className="px-3 py-2 text-right">Videos</th>
                <th className="px-3 py-2 text-right">Avg Views</th>
                <th className="px-3 py-2 text-right">Best Video</th>
                <th className="px-3 py-2 text-right">Hit Rate</th>
              </tr>
            </thead>
            <tbody>
              {data.conceptClusters.map((c) => (
                <tr key={c.cluster} className="border-t border-gray-100">
                  <td className="px-3 py-2.5 font-semibold text-[#0D1B2A] capitalize">{c.cluster.replace(/-/g, " ")}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{c.videoCount}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatNum(c.avgViews)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{formatNum(c.bestVideoViews)}</td>
                  <td className="px-3 py-2.5 text-right">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${c.hitRate >= 30 ? "bg-emerald-100 text-emerald-700" : c.hitRate >= 10 ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-500"}`}>
                      {c.hitRate}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Creator Scorecard */}
      {activeView === "creators" && (() => {
        // Group videos by creator
        const creatorGroups: Record<string, UGCVideo[]> = {};
        for (const v of data.videos) {
          const key = v.creatorName || "Unknown";
          if (!creatorGroups[key]) creatorGroups[key] = [];
          creatorGroups[key].push(v);
        }
        const scorecards = Object.entries(creatorGroups)
          .map(([name, vids]) => {
            const totalViews = vids.reduce((s, v) => s + v.viewsTotal, 0);
            const hits = vids.filter((v) => v.classification === "hit").length;
            const totalRevenue = vids.reduce((s, v) => s + v.revenueCents, 0);
            const avgRetention = vids.reduce((s, v) => s + v.hookRetentionRate, 0) / vids.length;
            const avgEngagement = totalViews > 0
              ? vids.reduce((s, v) => s + v.likes + v.comments + v.shares, 0) / totalViews
              : 0;
            return { name, handle: vids[0].creatorHandle, videos: vids.length, totalViews, hits, hitRate: Math.round((hits / vids.length) * 100), totalRevenue, avgRetention, avgEngagement, bestVideo: [...vids].sort((a, b) => b.viewsTotal - a.viewsTotal)[0] };
          })
          .sort((a, b) => b.totalViews - a.totalViews);

        return (
          <div className="grid gap-4 sm:grid-cols-2">
            {scorecards.map((c) => (
              <div key={c.name} className="rounded-xl border border-gray-200 bg-white p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-[#0D1B2A]">{c.name}</h3>
                    <p className="text-xs text-gray-400">{c.handle}</p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${c.hitRate >= 25 ? "bg-emerald-100 text-emerald-700" : c.hitRate >= 10 ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-500"}`}>
                    {c.hitRate}% hit rate
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-4 gap-2 text-center">
                  <div>
                    <p className="text-lg font-bold text-[#0D1B2A]">{c.videos}</p>
                    <p className="text-[9px] text-gray-400">Videos</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-[#0D1B2A]">{formatNum(c.totalViews)}</p>
                    <p className="text-[9px] text-gray-400">Views</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-emerald-600">{c.hits}</p>
                    <p className="text-[9px] text-gray-400">Hits</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-[#0D1B2A]">{"\u20AC"}{(c.totalRevenue / 100).toFixed(0)}</p>
                    <p className="text-[9px] text-gray-400">Revenue</p>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div className="rounded-lg bg-gray-50 p-2 text-center">
                    <p className="text-xs font-bold text-[#0D1B2A]">{formatPct(c.avgRetention)}</p>
                    <p className="text-[9px] text-gray-400">Avg Retention</p>
                  </div>
                  <div className="rounded-lg bg-gray-50 p-2 text-center">
                    <p className="text-xs font-bold text-[#0D1B2A]">{formatPct(c.avgEngagement)}</p>
                    <p className="text-[9px] text-gray-400">Avg Engagement</p>
                  </div>
                </div>
                {c.bestVideo && (
                  <div className="mt-3 rounded-lg border border-gray-100 p-2">
                    <p className="text-[9px] font-semibold text-gray-400">BEST VIDEO</p>
                    <p className="mt-0.5 text-xs font-medium text-[#0D1B2A] truncate">{c.bestVideo.hookText}</p>
                    <p className="text-[10px] text-gray-400">{formatNum(c.bestVideo.viewsTotal)} views · {c.bestVideo.shares} shares</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        );
      })()}

      {/* A/B Comparison */}
      {activeView === "compare" && (() => {
        const allHooks = [...new Set(data.videos.map((v) => v.hookText))].filter(Boolean);
        const getGroup = (hookText: string) => data.videos.filter((v) => v.hookText === hookText);
        const computeStats = (vids: UGCVideo[]) => {
          if (vids.length === 0) return null;
          const totalViews = vids.reduce((s, v) => s + v.viewsTotal, 0);
          return {
            count: vids.length,
            avgViews: Math.round(totalViews / vids.length),
            avgRetention: vids.reduce((s, v) => s + v.hookRetentionRate, 0) / vids.length,
            avgWatchTime: vids.reduce((s, v) => s + v.avgWatchTime, 0) / vids.length,
            avgCompletion: vids.reduce((s, v) => s + v.completionRate, 0) / vids.length,
            avgEngagement: totalViews > 0 ? vids.reduce((s, v) => s + v.likes + v.comments + v.shares, 0) / totalViews : 0,
            totalShares: vids.reduce((s, v) => s + v.shares, 0),
            totalRevenue: vids.reduce((s, v) => s + v.revenueCents, 0),
            hits: vids.filter((v) => v.classification === "hit").length,
          };
        };
        const statsA = compareA ? computeStats(getGroup(compareA)) : null;
        const statsB = compareB ? computeStats(getGroup(compareB)) : null;

        const CompareCol = ({ label, a, b, format = "num", higher = "better" }: { label: string; a: number | null; b: number | null; format?: "num" | "pct" | "eur" | "sec"; higher?: "better" | "worse" }) => {
          const fmt = (n: number | null) => {
            if (n === null) return "—";
            if (format === "pct") return formatPct(n);
            if (format === "eur") return `\u20AC${(n / 100).toFixed(0)}`;
            if (format === "sec") return `${n.toFixed(1)}s`;
            return formatNum(n);
          };
          const aWins = a !== null && b !== null && ((higher === "better" && a > b) || (higher === "worse" && a < b));
          const bWins = a !== null && b !== null && ((higher === "better" && b > a) || (higher === "worse" && b < a));
          return (
            <div className="grid grid-cols-3 gap-2 py-2 border-b border-gray-100 items-center">
              <p className={`text-right text-sm font-bold tabular-nums ${aWins ? "text-emerald-600" : "text-[#0D1B2A]"}`}>{fmt(a)}</p>
              <p className="text-center text-[10px] text-gray-400">{label}</p>
              <p className={`text-left text-sm font-bold tabular-nums ${bWins ? "text-emerald-600" : "text-[#0D1B2A]"}`}>{fmt(b)}</p>
            </div>
          );
        };

        return (
          <div className="space-y-4">
            <p className="text-sm text-gray-500">Pick two hooks to compare side-by-side</p>
            <div className="grid grid-cols-2 gap-4">
              <select value={compareA} onChange={(e) => setCompareA(e.target.value)} className="rounded-lg border border-gray-200 bg-white p-2 text-xs">
                <option value="">Select Hook A</option>
                {allHooks.map((h) => <option key={h} value={h}>{h}</option>)}
              </select>
              <select value={compareB} onChange={(e) => setCompareB(e.target.value)} className="rounded-lg border border-gray-200 bg-white p-2 text-xs">
                <option value="">Select Hook B</option>
                {allHooks.map((h) => <option key={h} value={h}>{h}</option>)}
              </select>
            </div>
            {statsA && statsB && (
              <div className="rounded-xl border border-gray-200 bg-white p-4">
                <div className="grid grid-cols-3 gap-2 mb-2">
                  <p className="text-right text-xs font-bold text-[#FF6B6B] truncate">{compareA}</p>
                  <p className="text-center text-xs font-bold text-gray-400">vs</p>
                  <p className="text-left text-xs font-bold text-[#1E3A8A] truncate">{compareB}</p>
                </div>
                <CompareCol label="Videos" a={statsA.count} b={statsB.count} />
                <CompareCol label="Avg Views" a={statsA.avgViews} b={statsB.avgViews} />
                <CompareCol label="Hook Retention" a={statsA.avgRetention} b={statsB.avgRetention} format="pct" />
                <CompareCol label="Watch Time" a={statsA.avgWatchTime} b={statsB.avgWatchTime} format="sec" />
                <CompareCol label="Completion" a={statsA.avgCompletion} b={statsB.avgCompletion} format="pct" />
                <CompareCol label="Engagement" a={statsA.avgEngagement} b={statsB.avgEngagement} format="pct" />
                <CompareCol label="Total Shares" a={statsA.totalShares} b={statsB.totalShares} />
                <CompareCol label="Revenue" a={statsA.totalRevenue} b={statsB.totalRevenue} format="eur" />
                <CompareCol label="Hits" a={statsA.hits} b={statsB.hits} />
              </div>
            )}
          </div>
        );
      })()}

      {/* Trends */}
      {activeView === "trends" && (() => {
        // Group videos by date for trend visualization
        const dateGroups: Record<string, UGCVideo[]> = {};
        for (const v of data.videos) {
          if (!dateGroups[v.datePosted]) dateGroups[v.datePosted] = [];
          dateGroups[v.datePosted].push(v);
        }
        const dates = Object.keys(dateGroups).sort();
        const maxViews = Math.max(...dates.map((d) => dateGroups[d].reduce((s, v) => s + v.viewsTotal, 0)), 1);

        return (
          <div className="space-y-6">
            {/* Views trend bar chart */}
            <div>
              <h3 className="mb-3 text-sm font-bold text-gray-500 uppercase tracking-wider">Daily Views</h3>
              <div className="rounded-xl border border-gray-200 bg-white p-4">
                <div className="flex items-end gap-1" style={{ height: 160 }}>
                  {dates.map((date) => {
                    const views = dateGroups[date].reduce((s, v) => s + v.viewsTotal, 0);
                    const pct = (views / maxViews) * 100;
                    const hits = dateGroups[date].filter((v) => v.classification === "hit").length;
                    return (
                      <div key={date} className="group relative flex-1 flex flex-col items-center justify-end" style={{ height: "100%" }}>
                        <div
                          className={`w-full min-w-[4px] rounded-t transition-all ${hits > 0 ? "bg-emerald-400" : "bg-[#FF6B6B]"}`}
                          style={{ height: `${Math.max(pct, 2)}%` }}
                        />
                        <div className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[9px] text-white opacity-0 transition group-hover:opacity-100">
                          {date}: {formatNum(views)} views ({dateGroups[date].length} vids)
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-1 flex justify-between text-[9px] text-gray-400">
                  <span>{dates[0]}</span>
                  <span>{dates[dates.length - 1]}</span>
                </div>
              </div>
            </div>

            {/* Classification trend */}
            <div>
              <h3 className="mb-3 text-sm font-bold text-gray-500 uppercase tracking-wider">Classification Over Time</h3>
              <div className="rounded-xl border border-gray-200 bg-white p-4">
                <div className="space-y-1">
                  {dates.map((date) => {
                    const vids = dateGroups[date];
                    const total = vids.length;
                    if (total === 0) return null;
                    const hits = vids.filter((v) => v.classification === "hit").length;
                    const avg = vids.filter((v) => v.classification === "average").length;
                    const fail = vids.filter((v) => v.classification === "fail").length;
                    return (
                      <div key={date} className="flex items-center gap-2">
                        <span className="w-20 text-right text-[9px] text-gray-400 tabular-nums">{date.slice(5)}</span>
                        <div className="flex flex-1 h-5 rounded overflow-hidden bg-gray-100">
                          {hits > 0 && <div className="bg-emerald-400" style={{ width: `${(hits / total) * 100}%` }} />}
                          {avg > 0 && <div className="bg-amber-400" style={{ width: `${(avg / total) * 100}%` }} />}
                          {fail > 0 && <div className="bg-red-400" style={{ width: `${(fail / total) * 100}%` }} />}
                        </div>
                        <span className="w-6 text-[9px] text-gray-400 tabular-nums">{total}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-3 flex gap-4 text-[10px]">
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-400" /> Hit</span>
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-400" /> Average</span>
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-400" /> Fail</span>
                </div>
              </div>
            </div>

            {/* Engagement trend */}
            <div>
              <h3 className="mb-3 text-sm font-bold text-gray-500 uppercase tracking-wider">Engagement Rate Trend</h3>
              <div className="rounded-xl border border-gray-200 bg-white p-4">
                <div className="flex items-end gap-1" style={{ height: 120 }}>
                  {dates.map((date) => {
                    const vids = dateGroups[date];
                    const totalViews = vids.reduce((s, v) => s + v.viewsTotal, 0);
                    const totalEng = vids.reduce((s, v) => s + v.likes + v.comments + v.shares, 0);
                    const engRate = totalViews > 0 ? totalEng / totalViews : 0;
                    const pct = Math.min(engRate * 500, 100); // scale: 20% eng = full bar
                    return (
                      <div key={date} className="group relative flex-1 flex flex-col items-center justify-end" style={{ height: "100%" }}>
                        <div className="w-full min-w-[4px] rounded-t bg-[#1E3A8A] transition-all" style={{ height: `${Math.max(pct, 2)}%` }} />
                        <div className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[9px] text-white opacity-0 transition group-hover:opacity-100">
                          {formatPct(engRate)}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-1 flex justify-between text-[9px] text-gray-400">
                  <span>{dates[0]}</span>
                  <span>{dates[dates.length - 1]}</span>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* All Videos */}
      {activeView === "videos" && (
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="px-2 py-2">Date</th>
                <th className="px-2 py-2">Hook</th>
                <th className="px-2 py-2">Creator</th>
                <th className="px-2 py-2">Format</th>
                <th className="px-2 py-2 text-right">2h</th>
                <th className="px-2 py-2 text-right">12h</th>
                <th className="px-2 py-2 text-right">24h</th>
                <th className="px-2 py-2 text-right">Total</th>
                <th className="px-2 py-2 text-right">Ret.</th>
                <th className="px-2 py-2 text-right">Eng.</th>
                <th className="px-2 py-2">Class</th>
              </tr>
            </thead>
            <tbody>
              {data.videos.map((v) => {
                const eng = v.viewsTotal > 0
                  ? ((v.likes + v.comments + v.shares) / v.viewsTotal)
                  : 0;
                return (
                  <tr key={v.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="whitespace-nowrap px-2 py-2 text-gray-500">{v.datePosted}</td>
                    <td className="max-w-[180px] truncate px-2 py-2 font-medium text-[#0D1B2A]">{v.hookText}</td>
                    <td className="px-2 py-2 text-gray-500">{v.creatorName}</td>
                    <td className="px-2 py-2 capitalize text-gray-500">{v.format}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{formatNum(v.views2h)}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{formatNum(v.views12h)}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{formatNum(v.views24h)}</td>
                    <td className="px-2 py-2 text-right font-semibold tabular-nums">{formatNum(v.viewsTotal)}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{formatPct(v.hookRetentionRate)}</td>
                    <td className="px-2 py-2 text-right tabular-nums">{formatPct(eng)}</td>
                    <td className="px-2 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${CLASS_COLORS[v.classification]}`}>
                        {v.classification}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Core Loop reminder */}
      <div className="rounded-xl bg-[#0D1B2A] px-5 py-4 text-center">
        <p className="text-xs font-bold uppercase tracking-widest text-white/40">Core Loop</p>
        <p className="mt-2 text-sm font-semibold text-white">
          Volume &rarr; Measure &rarr; Outliers &rarr; Replicate &rarr; Scale
        </p>
      </div>
    </div>
  );
}
