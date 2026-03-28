// ---------------------------------------------------------------------------
// Weekly Auto-Report Generator — surfaces insights for pod leads
// ---------------------------------------------------------------------------

import type { UGCDashboardData, UGCVideo } from "./kpi";
import type { Pod } from "./pod-planner";

// ─── Types ──────────────────────────────────────────────────────────────────

export interface WeeklyInsight {
  type: "hit" | "trend" | "alert" | "action";
  icon: string;
  title: string;
  detail: string;
}

export interface WeeklyReport {
  periodStart: string;
  periodEnd: string;
  podName: string;
  podLanguage: string;

  // Summary stats
  videosPosted: number;
  totalViews: number;
  avgRetention: number;
  avgEngagement: number;
  hits: number;
  revenue: number;

  // Comparisons (vs previous period)
  viewsChange: number;    // percentage
  hitsChange: number;

  // Actionable insights
  insights: WeeklyInsight[];

  // Top content
  topVideo: UGCVideo | null;
  worstVideo: UGCVideo | null;

  // Next week suggestions
  suggestedHooks: string[];
  suggestedFormats: string[];
  replicateCandidates: UGCVideo[];
}

// ─── Generator ──────────────────────────────────────────────────────────────

export function generateWeeklyReport(
  ugcData: UGCDashboardData,
  pod: Pod,
): WeeklyReport {
  const now = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 86400000);
  const twoWeeksAgo = new Date(now.getTime() - 14 * 86400000);

  const periodStart = weekAgo.toISOString().slice(0, 10);
  const periodEnd = now.toISOString().slice(0, 10);

  // Filter videos for this pod's creators
  const podCreators = new Set(pod.members.map((m) => m.name));
  const allPodVideos = ugcData.videos.filter((v) => podCreators.has(v.creatorName));

  // This week's videos
  const thisWeek = allPodVideos.filter((v) => v.datePosted >= periodStart);
  // Last week's videos (for comparison)
  const lastWeek = allPodVideos.filter(
    (v) => v.datePosted >= twoWeeksAgo.toISOString().slice(0, 10) && v.datePosted < periodStart,
  );

  const totalViews = thisWeek.reduce((s, v) => s + v.viewsTotal, 0);
  const lastWeekViews = lastWeek.reduce((s, v) => s + v.viewsTotal, 0);
  const hits = thisWeek.filter((v) => v.classification === "hit");
  const lastWeekHits = lastWeek.filter((v) => v.classification === "hit");

  const avgRetention = thisWeek.length > 0
    ? thisWeek.reduce((s, v) => s + v.hookRetentionRate, 0) / thisWeek.length
    : 0;
  const avgEngagement = totalViews > 0
    ? thisWeek.reduce((s, v) => s + v.likes + v.comments + v.shares, 0) / totalViews
    : 0;
  const revenue = thisWeek.reduce((s, v) => s + v.revenueCents, 0) / 100;

  const sorted = [...thisWeek].sort((a, b) => b.viewsTotal - a.viewsTotal);
  const topVideo = sorted[0] ?? null;
  const worstVideo = sorted.length > 1 ? sorted[sorted.length - 1] : null;

  // Generate insights
  const insights: WeeklyInsight[] = [];

  if (hits.length > 0) {
    insights.push({
      type: "hit",
      icon: "fire",
      title: `${hits.length} HIT${hits.length > 1 ? "S" : ""} this week`,
      detail: `Best: "${hits[0].hookText}" with ${fmtNum(hits[0].viewsTotal)} views. Replicate this hook with 5 new angles.`,
    });
  }

  if (avgRetention > 0.4) {
    insights.push({
      type: "trend",
      icon: "trending-up",
      title: "Strong hook retention",
      detail: `${(avgRetention * 100).toFixed(0)}% avg 3s retention — above the 40% benchmark. Your hooks are working.`,
    });
  } else if (avgRetention < 0.25 && thisWeek.length > 0) {
    insights.push({
      type: "alert",
      icon: "alert",
      title: "Low hook retention",
      detail: `${(avgRetention * 100).toFixed(0)}% avg 3s retention — below 25%. Test more provocative/curiosity-driven hooks.`,
    });
  }

  const viewsChange = lastWeekViews > 0
    ? Math.round(((totalViews - lastWeekViews) / lastWeekViews) * 100)
    : 0;

  if (viewsChange > 20) {
    insights.push({
      type: "trend",
      icon: "trending-up",
      title: `Views up ${viewsChange}% vs last week`,
      detail: "Momentum is building. Increase volume to ride the wave.",
    });
  } else if (viewsChange < -20 && lastWeekViews > 0) {
    insights.push({
      type: "alert",
      icon: "trending-down",
      title: `Views down ${Math.abs(viewsChange)}% vs last week`,
      detail: "Try different hooks or formats. Review what competitors are posting.",
    });
  }

  // Check if behind target
  if (thisWeek.length < pod.targetVideosPerWeek) {
    insights.push({
      type: "alert",
      icon: "clock",
      title: `Behind target: ${thisWeek.length}/${pod.targetVideosPerWeek} videos`,
      detail: `Need ${pod.targetVideosPerWeek - thisWeek.length} more videos this week to hit the weekly target.`,
    });
  }

  // Suggest hooks based on top performers
  const topHooks = ugcData.hookAnalysis.slice(0, 3).map((h) => h.hookText);
  const topFormats = ugcData.formatAnalysis.slice(0, 2).map((f) => f.format);

  // Replicate candidates: HITs that haven't been replicated yet
  const replicateCandidates = allPodVideos
    .filter((v) => v.classification === "hit")
    .sort((a, b) => b.viewsTotal - a.viewsTotal)
    .slice(0, 3);

  // Auto-action suggestions
  if (replicateCandidates.length > 0) {
    insights.push({
      type: "action",
      icon: "copy",
      title: "Replicate top performers",
      detail: `${replicateCandidates.length} HIT videos ready for replication. Same visuals, new hooks.`,
    });
  }

  return {
    periodStart,
    periodEnd,
    podName: pod.name,
    podLanguage: pod.language,
    videosPosted: thisWeek.length,
    totalViews,
    avgRetention,
    avgEngagement,
    hits: hits.length,
    revenue,
    viewsChange,
    hitsChange: lastWeekHits.length > 0
      ? Math.round(((hits.length - lastWeekHits.length) / lastWeekHits.length) * 100)
      : 0,
    insights,
    topVideo,
    worstVideo,
    suggestedHooks: topHooks,
    suggestedFormats: topFormats,
    replicateCandidates,
  };
}

/**
 * Exports the weekly report as a WhatsApp-friendly plain text message.
 */
export function exportReportWhatsApp(report: WeeklyReport): string {
  const lines = [
    `*${report.podName} — Weekly Report*`,
    `${report.periodStart} → ${report.periodEnd}`,
    "",
    `*Summary*`,
    `Videos: ${report.videosPosted}`,
    `Views: ${fmtNum(report.totalViews)} ${report.viewsChange > 0 ? `(+${report.viewsChange}%)` : report.viewsChange < 0 ? `(${report.viewsChange}%)` : ""}`,
    `Retention: ${(report.avgRetention * 100).toFixed(0)}%`,
    `HITs: ${report.hits}`,
    `Revenue: \u20AC${report.revenue.toFixed(0)}`,
    "",
  ];

  if (report.topVideo) {
    lines.push(
      `*Best video*`,
      `"${report.topVideo.hookText}"`,
      `${fmtNum(report.topVideo.viewsTotal)} views · ${report.topVideo.shares} shares`,
      "",
    );
  }

  if (report.insights.length > 0) {
    lines.push(`*Insights*`);
    for (const insight of report.insights) {
      lines.push(`- ${insight.title}: ${insight.detail}`);
    }
    lines.push("");
  }

  if (report.suggestedHooks.length > 0) {
    lines.push(`*Try these hooks next:*`);
    for (const hook of report.suggestedHooks) {
      lines.push(`- "${hook}"`);
    }
  }

  return lines.join("\n");
}

function fmtNum(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}
