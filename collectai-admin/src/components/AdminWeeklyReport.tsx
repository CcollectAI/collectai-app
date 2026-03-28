"use client";

import { useEffect, useState } from "react";
import { fetchUGCDashboardData } from "@/lib/kpi";
import { AdminDemoBanner } from "@/components/AdminDemoBanner";
import type { UGCDashboardData } from "@/lib/kpi";
import { fetchPodPlannerData } from "@/lib/pod-planner";
import type { PodPlannerData } from "@/lib/pod-planner";
import {
  generateWeeklyReport,
  exportReportWhatsApp,
} from "@/lib/weekly-report";
import type { WeeklyReport, WeeklyInsight } from "@/lib/weekly-report";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatNum(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

function formatPct(n: number): string {
  return `${(n * 100).toFixed(0)}%`;
}

const INSIGHT_COLORS: Record<WeeklyInsight["type"], string> = {
  hit: "bg-emerald-100 text-emerald-700",
  trend: "bg-blue-100 text-blue-700",
  alert: "bg-red-100 text-red-700",
  action: "bg-amber-100 text-amber-700",
};

// ─── Stat Card (matches AdminUGCDashboard) ──────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  badge,
}: {
  label: string;
  value: string;
  sub?: string;
  badge?: { text: string; positive: boolean } | null;
}) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
        {label}
      </p>
      <div className="mt-1 flex items-baseline gap-2">
        <p className="text-2xl font-bold tabular-nums text-[#0D1B2A]">
          {value}
        </p>
        {badge && (
          <span
            className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
              badge.positive
                ? "bg-emerald-100 text-emerald-700"
                : "bg-red-100 text-red-700"
            }`}
          >
            {badge.positive ? "+" : ""}
            {badge.text}
          </span>
        )}
      </div>
      {sub && <p className="mt-0.5 text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

// ─── Pod Report Card ─────────────────────────────────────────────────────────

function PodReportCard({ report }: { report: WeeklyReport }) {
  const [copied, setCopied] = useState(false);

  const handleCopyWhatsApp = async () => {
    const text = exportReportWhatsApp(report);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="rounded-2xl bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-[#0D1B2A]">
              {report.podName}
            </h3>
            <p className="text-xs text-gray-400">
              {report.periodStart} &rarr; {report.periodEnd}
            </p>
          </div>
          <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[10px] font-bold uppercase text-gray-500">
            {report.podLanguage}
          </span>
        </div>

        {/* Summary stats row */}
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
          <StatCard label="Videos" value={String(report.videosPosted)} />
          <StatCard
            label="Views"
            value={formatNum(report.totalViews)}
            badge={
              report.viewsChange !== 0
                ? {
                    text: `${report.viewsChange}%`,
                    positive: report.viewsChange > 0,
                  }
                : null
            }
          />
          <StatCard
            label="Retention"
            value={formatPct(report.avgRetention)}
          />
          <StatCard label="HITs" value={String(report.hits)} />
          <StatCard
            label="Revenue"
            value={`\u20AC${report.revenue.toFixed(0)}`}
          />
        </div>

        {/* Insights */}
        {report.insights.length > 0 && (
          <div className="mt-5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-2">
              Insights
            </p>
            <div className="flex flex-wrap gap-2">
              {report.insights.map((insight, i) => (
                <div
                  key={i}
                  className={`rounded-full px-3 py-1.5 text-xs font-semibold ${INSIGHT_COLORS[insight.type]}`}
                  title={insight.detail}
                >
                  {insight.title}
                </div>
              ))}
            </div>
            {/* Insight details */}
            <div className="mt-3 space-y-1.5">
              {report.insights.map((insight, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 rounded-lg bg-gray-50 px-3 py-2"
                >
                  <span
                    className={`mt-0.5 inline-block h-2 w-2 shrink-0 rounded-full ${
                      {
                        hit: "bg-emerald-500",
                        trend: "bg-blue-500",
                        alert: "bg-red-500",
                        action: "bg-amber-500",
                      }[insight.type]
                    }`}
                  />
                  <div>
                    <p className="text-xs font-semibold text-[#0D1B2A]">
                      {insight.title}
                    </p>
                    <p className="text-xs text-gray-500">{insight.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top video highlight */}
        {report.topVideo && (
          <div className="mt-5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-2">
              Top Video
            </p>
            <div className="rounded-xl bg-emerald-50 p-4">
              <p className="text-sm font-bold text-[#0D1B2A]">
                &ldquo;{report.topVideo.hookText}&rdquo;
              </p>
              <div className="mt-2 flex items-center gap-4 text-xs text-gray-600">
                <span className="font-semibold">
                  {formatNum(report.topVideo.viewsTotal)} views
                </span>
                <span>{report.topVideo.shares} shares</span>
                <span>by {report.topVideo.creatorName}</span>
              </div>
            </div>
          </div>
        )}

        {/* Suggested hooks */}
        {report.suggestedHooks.length > 0 && (
          <div className="mt-5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-2">
              Suggested Hooks for Next Week
            </p>
            <ul className="space-y-1.5">
              {report.suggestedHooks.map((hook, i) => (
                <li
                  key={i}
                  className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-800"
                >
                  <span className="shrink-0 text-blue-400">&bull;</span>
                  &ldquo;{hook}&rdquo;
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Replicate candidates */}
        {report.replicateCandidates.length > 0 && (
          <div className="mt-5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-2">
              Replicate These HITs
            </p>
            <div className="space-y-1.5">
              {report.replicateCandidates.map((v) => (
                <div
                  key={v.id}
                  className="flex items-center justify-between rounded-lg bg-emerald-50 px-3 py-2"
                >
                  <div>
                    <p className="text-xs font-semibold text-[#0D1B2A]">
                      &ldquo;{v.hookText}&rdquo;
                    </p>
                    <p className="text-[10px] text-gray-400">
                      {v.creatorName} &middot; {v.format}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-bold text-emerald-700">
                      {formatNum(v.viewsTotal)} views
                    </p>
                    <p className="text-[10px] text-gray-400">
                      {v.shares} shares
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Copy WhatsApp Report button */}
        <button
          onClick={handleCopyWhatsApp}
          className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-[#25D366] px-4 py-2.5 text-sm font-bold text-white transition hover:bg-[#20bd5a] active:scale-95"
        >
          <svg
            className="h-4 w-4"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
          </svg>
          {copied ? "Copied!" : "Copy WhatsApp Report"}
        </button>
      </div>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function AdminWeeklyReport() {
  const [reports, setReports] = useState<WeeklyReport[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchUGCDashboardData(7), fetchPodPlannerData()]).then(
      ([ugcData, podData]: [UGCDashboardData, PodPlannerData]) => {
        const generated = podData.pods.map((pod) =>
          generateWeeklyReport(ugcData, pod),
        );
        setReports(generated);
        setLoading(false);
      },
    );
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-[#FF6B6B]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold text-[#0D1B2A]">Weekly Reports</h2>
        <AdminDemoBanner />
      </div>

      {/* Report cards */}
      <div className="grid gap-6 lg:grid-cols-2">
        {reports.map((report) => (
          <PodReportCard key={report.podName} report={report} />
        ))}
      </div>

      {reports.length === 0 && (
        <div className="rounded-xl bg-white p-8 text-center shadow-sm">
          <p className="text-sm text-gray-500">
            No pods found. Add pods in Pod Management first.
          </p>
        </div>
      )}
    </div>
  );
}
