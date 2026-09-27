"use client";

import React, { useState, useEffect, useCallback } from "react";
import { ForecastChart } from "@/components/charts/ForecastChart";
import { CohortHeatmap } from "@/components/charts/CohortHeatmap";
import { PostingTimeHeatmap } from "@/components/charts/PostingTimeHeatmap";
import { MetricCard } from "@/components/ui/MetricCard";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";
import { getSupabase } from "@/lib/supabase";


// ---------- Types ----------

interface ForecastPoint {
  label: string;
  actual: number;
  forecast?: number;
}

interface CohortRow {
  creator: string;
  weeks: number[];
}

interface PostingTimePoint {
  hour: number;
  day: string;
  avgViews: number;
}

interface QuickInsights {
  avg_views: number;
  avg_views_trend: number;
  avg_views_sparkline: number[];
  hit_rate: number;
  hit_rate_trend: number;
  hit_rate_sparkline: number[];
  revenue: number;
  revenue_trend: number;
  revenue_sparkline: number[];
  engagement: number;
  engagement_trend: number;
  engagement_sparkline: number[];
}

interface IntelligenceData {
  insights: QuickInsights;
  revenue_forecast: ForecastPoint[];
  cohort_data: CohortRow[];
  cohort_week_labels: string[];
  posting_times: PostingTimePoint[];
}

// ---------- Empty State ----------

function EmptyState({ title, message }: { title?: string; message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-14 px-6">
      <div className="w-14 h-14 rounded-full bg-gray-100 dark:bg-slate-700 flex items-center justify-center mb-3">
        <svg className="w-7 h-7 text-gray-400 dark:text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
        </svg>
      </div>
      <h3 className="text-base font-semibold text-gray-700 dark:text-gray-300 mb-1">
        {title || "Waiting for data"}
      </h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-md">
        {message || "Intelligence insights will populate once content is being created and tracked."}
      </p>
    </div>
  );
}

// ---------- Section Empty ----------

function SectionEmpty({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center py-12 text-sm text-gray-400 dark:text-gray-500">
      {message}
    </div>
  );
}

// ---------- Loading Skeleton ----------

function IntelligenceLoadingSkeleton() {
  return (
    <div className="space-y-8">
      <div>
        <Skeleton width="40%" height={28} rounded="md" className="mb-2" />
        <Skeleton width="25%" height={14} rounded="md" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6">
        <Skeleton width="30%" height={14} rounded="md" className="mb-4" />
        <Skeleton width="100%" height={320} rounded="lg" />
      </div>
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6">
        <Skeleton width="35%" height={14} rounded="md" className="mb-4" />
        <Skeleton width="100%" height={200} rounded="lg" />
      </div>
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6">
        <Skeleton width="25%" height={14} rounded="md" className="mb-4" />
        <Skeleton width="100%" height={250} rounded="lg" />
      </div>
    </div>
  );
}

// ---------- Fetch ----------

// Loaded from Supabase only. (There is no /admin/intelligence-summary endpoint
// on the server — checked against scripts/api.lock.json 2026-09-27 — so the
// API call that used to come first could only ever fail.)
//
// Until 2026-09-27 this selected ugc_tiktok_metrics.posted_at and
// ugc_video_scripts.creator_handle / engagement_score — none of which exist —
// and ignored the error, so 6 real metric rows rendered as "Waiting for data".
// Gate: collectai-admin/scripts/check-admin-columns.mjs.

type IntelligenceLoad =
  | { kind: "data"; data: IntelligenceData }
  | { kind: "empty"; reason: string }
  | { kind: "error"; reason: string };

async function fetchIntelligenceData(): Promise<IntelligenceLoad> {
  const sb = getSupabase();
  if (!sb) return { kind: "error", reason: "Supabase is not configured for the dashboard" };

  const { data: metrics, error } = await sb
    .from("ugc_tiktok_metrics")
    .select("snapshot_at, views, shares, likes, comments, ugc_video_scripts(posted_at, creator_id)")
    .order("snapshot_at", { ascending: false })
    .limit(500);
  if (error) return { kind: "error", reason: `ugc_tiktok_metrics: ${error.message}` };
  if (!metrics || metrics.length === 0) {
    return { kind: "empty", reason: "No TikTok metrics recorded yet (ugc_tiktok_metrics is empty)." };
  }

  type Row = {
    snapshot_at: string; views: number | null; shares: number | null; likes: number | null; comments: number | null;
    ugc_video_scripts: { posted_at: string | null; creator_id: string | null } | null;
  };
  const rows = metrics as unknown as Row[];

  // Posting-time heatmap: by when the VIDEO was posted (the script's
  // posted_at), not when a metric snapshot was taken.
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const buckets: Record<string, { total: number; count: number }> = {};
  let postedKnown = 0;
  for (const r of rows) {
    const posted = r.ugc_video_scripts?.posted_at;
    if (!posted) continue;
    postedKnown++;
    const dt = new Date(posted);
    const dayIdx = dt.getDay();
    const key = `${days[dayIdx === 0 ? 6 : dayIdx - 1]}-${dt.getHours()}`;
    const b = (buckets[key] ??= { total: 0, count: 0 });
    b.total += r.views ?? 0;
    b.count += 1;
  }
  const posting_times: PostingTimePoint[] = [];
  if (postedKnown > 0) {
    for (const day of days) {
      for (let h = 0; h < 24; h++) {
        const b = buckets[`${day}-${h}`];
        posting_times.push({ hour: h, day, avgViews: b ? Math.round(b.total / b.count) : 0 });
      }
    }
  }

  // Creator cohorts need scripts tied to a creator; averaged views per 4 slices.
  const byCreator: Record<string, number[]> = {};
  for (const r of rows) {
    const c = r.ugc_video_scripts?.creator_id;
    if (c) (byCreator[c] ??= []).push(r.views ?? 0);
  }
  const cohort_data: CohortRow[] = Object.entries(byCreator).map(([creator, views]) => {
    const size = Math.ceil(views.length / 4);
    const weeks = [0, 1, 2, 3].map((w) => {
      const chunk = views.slice(w * size, (w + 1) * size);
      return chunk.length ? Math.round(chunk.reduce((a, b) => a + b, 0) / chunk.length) : 0;
    });
    return { creator, weeks };
  });

  const totalViews = rows.reduce((s, r) => s + (r.views ?? 0), 0);
  const totalEngagement = rows.reduce((s, r) => s + (r.likes ?? 0) + (r.comments ?? 0) + (r.shares ?? 0), 0);

  return {
    kind: "data",
    data: {
      insights: {
        avg_views: Math.round(totalViews / rows.length),
        avg_views_trend: 0,
        avg_views_sparkline: [],
        hit_rate: 0,
        hit_rate_trend: 0,
        hit_rate_sparkline: [],
        revenue: 0,
        revenue_trend: 0,
        revenue_sparkline: [],
        engagement: totalViews > 0 ? parseFloat(((totalEngagement / totalViews) * 100).toFixed(1)) : 0,
        engagement_trend: 0,
        engagement_sparkline: [],
      },
      revenue_forecast: [],
      cohort_data,
      cohort_week_labels: ["W1", "W2", "W3", "W4"],
      posting_times,
    },
  };
}

// ---------- Component ----------

export function IntelligenceTab() {
  const [data, setData] = useState<IntelligenceData | null>(null);
  const [problem, setProblem] = useState<{ kind: "empty" | "error"; reason: string } | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const result = await fetchIntelligenceData().catch(
      (e): IntelligenceLoad => ({ kind: "error", reason: e instanceof Error ? e.message : String(e) }),
    );
    if (result.kind === "data") { setData(result.data); setProblem(null); }
    else { setData(null); setProblem(result); }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 120_000); // refresh every 2min
    return () => clearInterval(interval);
  }, [load]);

  if (loading) return <IntelligenceLoadingSkeleton />;
  if (!data) {
    return problem?.kind === "error"
      ? <EmptyState title="Could not load intelligence data" message={problem.reason} />
      : <EmptyState title="No data yet" message={problem?.reason ?? "No TikTok metrics recorded yet."} />;
  }

  const { insights, revenue_forecast, cohort_data, cohort_week_labels, posting_times } = data;

  const hasInsights = insights.avg_views > 0 || insights.revenue > 0;
  const hasForecast = revenue_forecast.length > 0;
  const hasCohort = cohort_data.length > 0;
  const hasPostingTimes = posting_times.some((p) => p.avgViews > 0);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
          Intelligence & Insights
        </h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          AI-powered content analytics
        </p>
      </div>

      {/* Quick Insights */}
      <section>
        <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-3">
          Quick Insights
        </h3>
        {hasInsights ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              label="Avg Views"
              value={insights.avg_views}
              trend={insights.avg_views_trend || undefined}
              sparklineData={insights.avg_views_sparkline.length > 0 ? insights.avg_views_sparkline : undefined}
              subtitle="Per post, last 30d"
            />
            <MetricCard
              label="Hit Rate"
              value={insights.hit_rate}
              suffix="%"
              trend={insights.hit_rate_trend || undefined}
              sparklineData={insights.hit_rate_sparkline.length > 0 ? insights.hit_rate_sparkline : undefined}
              subtitle="Posts exceeding 2x avg"
            />
            <MetricCard
              label="Revenue"
              value={insights.revenue}
              prefix="$"
              trend={insights.revenue_trend || undefined}
              sparklineData={insights.revenue_sparkline.length > 0 ? insights.revenue_sparkline : undefined}
              subtitle="Monthly recurring"
            />
            <MetricCard
              label="Engagement"
              value={insights.engagement}
              suffix="%"
              trend={insights.engagement_trend || undefined}
              sparklineData={insights.engagement_sparkline.length > 0 ? insights.engagement_sparkline : undefined}
              subtitle="Avg interaction rate"
            />
          </div>
        ) : (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6">
            <SectionEmpty message="No content metrics available yet" />
          </div>
        )}
      </section>

      {/* Revenue Forecast */}
      <section className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 transition-colors">
        <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-4">
          Revenue Forecast
        </h3>
        {hasForecast ? (
          <ForecastChart data={revenue_forecast} height={320} />
        ) : (
          <SectionEmpty message="Revenue forecast will appear once subscription data is available" />
        )}
      </section>

      {/* Creator Cohort Performance */}
      <section className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 transition-colors">
        <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-4">
          Creator Cohort Performance
        </h3>
        {hasCohort ? (
          <CohortHeatmap data={cohort_data} weekLabels={cohort_week_labels} />
        ) : (
          <SectionEmpty message="Cohort data will appear once creators have weekly performance records" />
        )}
      </section>

      {/* Best Posting Times */}
      <section className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-6 transition-colors">
        <h3 className="text-sm font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-4">
          Best Posting Times
        </h3>
        {hasPostingTimes ? (
          <PostingTimeHeatmap data={posting_times} />
        ) : (
          <SectionEmpty message="Posting time analysis will appear once TikTok metrics are being tracked" />
        )}
      </section>
    </div>
  );
}
