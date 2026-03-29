// ---------------------------------------------------------------------------
// TikTok Metrics API Integration — auto-pull video performance data
// Feeds into learning system to close the content flywheel loop.
//
// Flow: Video posted → 2h/12h/24h/7d snapshots → classify → update learning scores
// ---------------------------------------------------------------------------

import { getSupabase, isSupabaseConfigured } from "@/lib/supabase";

// ─── Types ──────────────────────────────────────────────────────────────

export interface TikTokCredentials {
  accessToken: string;
  openId: string;             // TikTok Business Account open_id
  refreshToken?: string;
  expiresAt?: string;
}

export interface TikTokVideoMetrics {
  videoId: string;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  avgWatchTime: number;       // seconds
  retention3s: number;        // 0-1
  completionRate: number;     // 0-1
  reach: number;
  profileViews: number;
}

export interface MetricsSnapshot {
  videoScriptId: string;
  tiktokVideoId: string;
  snapshotAt: string;
  metrics: TikTokVideoMetrics;
}

export interface MetricsPullSchedule {
  videoScriptId: string;
  tiktokVideoId: string;
  postedAt: string;
  nextPullAt: string;
  pullsCompleted: number;     // 0=pending, 1=2h, 2=12h, 3=24h, 4=7d
}

// ─── Classification thresholds (matches admin.config.ts) ─────────────────

const CLASSIFICATION = {
  hit: { minViews: 50000, minRetention: 0.40, minShares: 100 },
  average: { minViews: 10000 },
};

export function classifyFromMetrics(m: TikTokVideoMetrics): "hit" | "average" | "fail" {
  if (
    m.views >= CLASSIFICATION.hit.minViews &&
    m.retention3s >= CLASSIFICATION.hit.minRetention &&
    m.shares >= CLASSIFICATION.hit.minShares
  ) {
    return "hit";
  }
  if (m.views >= CLASSIFICATION.average.minViews) return "average";
  return "fail";
}

// ─── Pull schedule — when to fetch metrics ───────────────────────────────

const PULL_INTERVALS_MS = [
  2 * 3600000,    // 2 hours
  12 * 3600000,   // 12 hours
  24 * 3600000,   // 24 hours
  7 * 86400000,   // 7 days
];

export function getNextPullTime(postedAt: string, pullsCompleted: number): string | null {
  if (pullsCompleted >= PULL_INTERVALS_MS.length) return null;
  const posted = new Date(postedAt).getTime();
  const next = posted + PULL_INTERVALS_MS[pullsCompleted];
  return new Date(next).toISOString();
}

export function isDueToPull(schedule: MetricsPullSchedule): boolean {
  return new Date(schedule.nextPullAt).getTime() <= Date.now();
}

// ─── TikTok Business API client ──────────────────────────────────────────

const TIKTOK_API_BASE = "https://open.tiktokapis.com/v2";

/**
 * Fetch video metrics from TikTok Business API.
 * Requires valid OAuth2 access token with video.list scope.
 *
 * Docs: https://developers.tiktok.com/doc/research-api-specs-query-videos
 */
export async function fetchTikTokVideoMetrics(
  credentials: TikTokCredentials,
  videoIds: string[],
): Promise<TikTokVideoMetrics[]> {
  const fields = [
    "id", "view_count", "like_count", "comment_count", "share_count",
    "reach_count", "average_time_watched",
  ].join(",");

  const results: TikTokVideoMetrics[] = [];

  for (const videoId of videoIds) {
    try {
      const res = await fetch(
        `${TIKTOK_API_BASE}/video/query/?fields=${fields}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${credentials.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            filters: { video_ids: [videoId] },
          }),
        },
      );

      if (!res.ok) {
        console.error(`[tiktok] Failed to fetch ${videoId}: ${res.status}`);
        continue;
      }

      const data = await res.json();
      const video = data?.data?.videos?.[0];
      if (!video) continue;

      const avgWatch = video.average_time_watched ?? 0;
      // Estimate retention_3s: if avg watch time > 3s, retention is high
      const estimated3sRetention = Math.min(avgWatch / 3, 1);
      // Estimate completion rate from avg watch time / typical video length (18s)
      const estimatedCompletion = Math.min(avgWatch / 18, 1);

      results.push({
        videoId,
        views: video.view_count ?? 0,
        likes: video.like_count ?? 0,
        comments: video.comment_count ?? 0,
        shares: video.share_count ?? 0,
        avgWatchTime: avgWatch,
        retention3s: estimated3sRetention,
        completionRate: estimatedCompletion,
        reach: video.reach_count ?? 0,
        profileViews: 0,
      });
    } catch (err) {
      console.error(`[tiktok] Error fetching ${videoId}:`, (err as Error).message);
    }
  }

  return results;
}

// ─── Persist snapshot to Supabase ────────────────────────────────────────

export async function saveMetricsSnapshot(snapshot: MetricsSnapshot): Promise<boolean> {
  if (!isSupabaseConfigured()) return false;
  const sb = getSupabase();
  if (!sb) return false;

  const { error: snapError } = await sb.from("ugc_tiktok_metrics").insert({
    video_script_id: snapshot.videoScriptId,
    tiktok_video_id: snapshot.tiktokVideoId,
    snapshot_at: snapshot.snapshotAt,
    views: snapshot.metrics.views,
    likes: snapshot.metrics.likes,
    comments: snapshot.metrics.comments,
    shares: snapshot.metrics.shares,
    avg_watch_time: snapshot.metrics.avgWatchTime,
    retention_3s: snapshot.metrics.retention3s,
    completion_rate: snapshot.metrics.completionRate,
    reach: snapshot.metrics.reach,
    profile_views: snapshot.metrics.profileViews,
  });

  if (snapError) {
    console.error("[tiktok] Failed to save snapshot:", snapError.message);
    return false;
  }

  // Update the video script with latest metrics
  const classification = classifyFromMetrics(snapshot.metrics);
  const { error: updateError } = await sb
    .from("ugc_video_scripts")
    .update({
      views_total: snapshot.metrics.views,
      retention_3s: snapshot.metrics.retention3s,
      completion_rate: snapshot.metrics.completionRate,
      shares: snapshot.metrics.shares,
      link_clicks: 0,
      classification,
    })
    .eq("id", snapshot.videoScriptId);

  if (updateError) {
    console.error("[tiktok] Failed to update script:", updateError.message);
    return false;
  }

  return true;
}

// ─── A/B Test Winner Declaration ─────────────────────────────────────────

export interface ABTestResult {
  winnerId: string;
  loserId: string;
  winnerMetrics: TikTokVideoMetrics;
  loserMetrics: TikTokVideoMetrics;
  reason: string;
}

/**
 * Compare two A/B variants after 24h and declare a winner.
 * Score = 40% retention + 25% completion + 20% views-normalized + 15% shares-normalized
 */
export function declareABWinner(
  variantA: { id: string; metrics: TikTokVideoMetrics },
  variantB: { id: string; metrics: TikTokVideoMetrics },
): ABTestResult {
  const score = (m: TikTokVideoMetrics) => {
    const viewsNorm = Math.min(m.views / 50000, 1);
    const sharesNorm = Math.min(m.shares / 100, 1);
    return m.retention3s * 0.4 + m.completionRate * 0.25 + viewsNorm * 0.2 + sharesNorm * 0.15;
  };

  const scoreA = score(variantA.metrics);
  const scoreB = score(variantB.metrics);

  const winner = scoreA >= scoreB ? variantA : variantB;
  const loser = scoreA >= scoreB ? variantB : variantA;

  return {
    winnerId: winner.id,
    loserId: loser.id,
    winnerMetrics: winner.metrics,
    loserMetrics: loser.metrics,
    reason: `Score ${(Math.max(scoreA, scoreB) * 100).toFixed(1)} vs ${(Math.min(scoreA, scoreB) * 100).toFixed(1)} — ${scoreA >= scoreB ? "Variant A" : "Variant B"} wins on ${
      winner.metrics.retention3s > loser.metrics.retention3s ? "retention" : "views"
    }`,
  };
}

// ─── Demo data for dashboard display ─────────────────────────────────────

export interface TikTokMetricsSummary {
  connectedAccounts: number;
  totalPulls: number;
  lastPullAt: string;
  pendingPulls: number;
  abTestsRunning: number;
  abTestsCompleted: number;
}

export function getDemoMetricsSummary(): TikTokMetricsSummary {
  return {
    connectedAccounts: 3,
    totalPulls: 42,
    lastPullAt: new Date(Date.now() - 7200000).toISOString(),
    pendingPulls: 2,
    abTestsRunning: 1,
    abTestsCompleted: 8,
  };
}
