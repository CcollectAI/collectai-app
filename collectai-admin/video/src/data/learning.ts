// ═══════════════════════════════════════════════════════════════════════════
// CollectAI Video Self-Learning System
// Tracks video performance → scores hooks/templates/niches → recommends
//
// The flywheel:
//   More videos → More data → Smarter templates → Better videos → More views
//   ↑                                                                      ↓
//   └──────────────────────── More downloads ←─────────────────────────────┘
// ═══════════════════════════════════════════════════════════════════════════

import { HOOKS, type Hook, getHooksForFormat } from "./hooks";
import { NICHES, type NicheInfo } from "./niches";
import { BRAND_IDENTITY, PRODUCT_CONTEXT, CONTENT_ANGLES, BRAND_VOICE, CTA_SYSTEM, PLATFORM_CONTEXT } from "./brand";
import { NICHE_PLAYBOOKS, getPlaybook } from "./playbooks";
import { COLLECTOR_PERSONAS, getPersonasForAngle } from "./personas";

// ─── Types ───────────────────────────────────────────────────────────────

export interface VideoRecord {
  videoId: string;
  templateId: string;        // pull_reveal | whats_it_worth | hidden_gem | market_alert | collection_flex
  nicheId: string;
  hookId: string;
  language: string;
  publishedAt: string;
  // Metrics (populated after 24h/48h/7d)
  views2h?: number;
  views12h?: number;
  views24h?: number;
  viewsTotal?: number;
  retention3s?: number;      // 0-1
  completionRate?: number;   // 0-1
  shares?: number;
  linkClicks?: number;
  installs?: number;
  classification?: "hit" | "average" | "fail" | "pending";
}

export interface HookScore {
  hookId: string;
  nicheId: string;
  score: number;             // 0-100 composite
  uses: number;
  hits: number;
  avgRetention: number;
  avgViews: number;
  lastUsed: string;
}

export interface TemplateScore {
  templateId: string;
  nicheId: string;
  score: number;
  uses: number;
  hits: number;
  avgViews: number;
  trend: "rising" | "stable" | "declining";
}

export interface NicheScore {
  nicheId: string;
  totalVideos: number;
  totalViews: number;
  hitRate: number;
  bestTemplate: string;
  bestHook: string;
}

export interface LearningStore {
  videos: VideoRecord[];
  hookScores: Record<string, HookScore>;         // key: `${hookId}__${nicheId}`
  templateScores: Record<string, TemplateScore>;  // key: `${templateId}__${nicheId}`
  nicheScores: Record<string, NicheScore>;        // key: nicheId
}

// ─── Classification ──────────────────────────────────────────────────────

const HIT_THRESHOLDS = {
  minViews: 50000,
  minRetention: 0.40,
  minShares: 100,
};

const AVERAGE_THRESHOLDS = {
  minViews: 10000,
};

export function classifyVideo(video: VideoRecord): "hit" | "average" | "fail" | "pending" {
  if (!video.viewsTotal || !video.retention3s) return "pending";
  if (
    video.viewsTotal >= HIT_THRESHOLDS.minViews &&
    video.retention3s >= HIT_THRESHOLDS.minRetention &&
    (video.shares ?? 0) >= HIT_THRESHOLDS.minShares
  ) {
    return "hit";
  }
  if (video.viewsTotal >= AVERAGE_THRESHOLDS.minViews) return "average";
  return "fail";
}

// ─── Score Computation ───────────────────────────────────────────────────

/**
 * Hook score = 40% retention + 25% completion + 20% views-normalized + 15% hit-rate
 */
export function computeHookScore(videos: VideoRecord[]): number {
  if (videos.length === 0) return 0;

  const avgRetention = videos.reduce((s, v) => s + (v.retention3s ?? 0), 0) / videos.length;
  const avgCompletion = videos.reduce((s, v) => s + (v.completionRate ?? 0), 0) / videos.length;
  const avgViews = videos.reduce((s, v) => s + (v.viewsTotal ?? 0), 0) / videos.length;
  const hitRate = videos.filter((v) => v.classification === "hit").length / videos.length;

  // Normalize views to 0-1 (50K = 1.0)
  const viewsNorm = Math.min(avgViews / 50000, 1);

  return Math.round(
    (avgRetention * 40 + avgCompletion * 25 + viewsNorm * 20 + hitRate * 15) * 100,
  ) / 100;
}

/**
 * Template trend: compare last 7 days vs. prior 7 days
 */
export function computeTrend(videos: VideoRecord[]): "rising" | "stable" | "declining" {
  const now = Date.now();
  const recent = videos.filter((v) => now - new Date(v.publishedAt).getTime() < 7 * 86400000);
  const prior = videos.filter((v) => {
    const age = now - new Date(v.publishedAt).getTime();
    return age >= 7 * 86400000 && age < 14 * 86400000;
  });

  const recentAvg = recent.length > 0
    ? recent.reduce((s, v) => s + (v.viewsTotal ?? 0), 0) / recent.length
    : 0;
  const priorAvg = prior.length > 0
    ? prior.reduce((s, v) => s + (v.viewsTotal ?? 0), 0) / prior.length
    : 0;

  if (priorAvg === 0) return "stable";
  const change = (recentAvg - priorAvg) / priorAvg;
  if (change > 0.15) return "rising";
  if (change < -0.15) return "declining";
  return "stable";
}

// ─── Store Operations ────────────────────────────────────────────────────

export function recordVideo(store: LearningStore, video: VideoRecord): LearningStore {
  video.classification = classifyVideo(video);
  store.videos.push(video);
  return recomputeScores(store);
}

export function recomputeScores(store: LearningStore): LearningStore {
  // Reset
  store.hookScores = {};
  store.templateScores = {};
  store.nicheScores = {};

  // Group by hook+niche
  const hookGroups: Record<string, VideoRecord[]> = {};
  const templateGroups: Record<string, VideoRecord[]> = {};
  const nicheGroups: Record<string, VideoRecord[]> = {};

  for (const v of store.videos) {
    const hk = `${v.hookId}__${v.nicheId}`;
    const tk = `${v.templateId}__${v.nicheId}`;
    (hookGroups[hk] ??= []).push(v);
    (templateGroups[tk] ??= []).push(v);
    (nicheGroups[v.nicheId] ??= []).push(v);
  }

  for (const [key, videos] of Object.entries(hookGroups)) {
    const [hookId, nicheId] = key.split("__");
    store.hookScores[key] = {
      hookId,
      nicheId,
      score: computeHookScore(videos),
      uses: videos.length,
      hits: videos.filter((v) => v.classification === "hit").length,
      avgRetention: videos.reduce((s, v) => s + (v.retention3s ?? 0), 0) / videos.length,
      avgViews: videos.reduce((s, v) => s + (v.viewsTotal ?? 0), 0) / videos.length,
      lastUsed: videos.sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))[0].publishedAt,
    };
  }

  for (const [key, videos] of Object.entries(templateGroups)) {
    const [templateId, nicheId] = key.split("__");
    store.templateScores[key] = {
      templateId,
      nicheId,
      score: computeHookScore(videos),
      uses: videos.length,
      hits: videos.filter((v) => v.classification === "hit").length,
      avgViews: videos.reduce((s, v) => s + (v.viewsTotal ?? 0), 0) / videos.length,
      trend: computeTrend(videos),
    };
  }

  for (const [nicheId, videos] of Object.entries(nicheGroups)) {
    const hits = videos.filter((v) => v.classification === "hit").length;

    // Find best template for this niche
    const tScores = Object.values(store.templateScores).filter((t) => t.nicheId === nicheId);
    const bestTemplate = tScores.sort((a, b) => b.score - a.score)[0]?.templateId ?? "";

    // Find best hook for this niche
    const hScores = Object.values(store.hookScores).filter((h) => h.nicheId === nicheId);
    const bestHook = hScores.sort((a, b) => b.score - a.score)[0]?.hookId ?? "";

    store.nicheScores[nicheId] = {
      nicheId,
      totalVideos: videos.length,
      totalViews: videos.reduce((s, v) => s + (v.viewsTotal ?? 0), 0),
      hitRate: videos.length > 0 ? hits / videos.length : 0,
      bestTemplate,
      bestHook,
    };
  }

  return store;
}

// ─── Recommendations ─────────────────────────────────────────────────────

export interface Recommendation {
  action: "create" | "replicate" | "test_hook" | "retire";
  templateId: string;
  hookId: string;
  nicheId: string;
  reason: string;
}

export function getRecommendation(
  store: LearningStore,
  nicheId: string,
  templateId: string,
): Recommendation {
  const tk = `${templateId}__${nicheId}`;
  const tScore = store.templateScores[tk];

  // If template is declining for this niche, suggest retirement
  if (tScore && tScore.trend === "declining" && tScore.uses >= 5) {
    return {
      action: "retire",
      templateId,
      hookId: "",
      nicheId,
      reason: `Template has declining performance (${tScore.uses} videos, trend: declining)`,
    };
  }

  // Find untested hooks for this niche+template
  const allHooks = getHooksForFormat(templateId);
  const usedHookIds = new Set(
    Object.values(store.hookScores)
      .filter((h) => h.nicheId === nicheId)
      .map((h) => h.hookId),
  );
  const untestedHooks = allHooks.filter((h) => !usedHookIds.has(h.id));

  if (untestedHooks.length > 0 && Math.random() < 0.3) {
    // 30% chance to test a new hook
    return {
      action: "test_hook",
      templateId,
      hookId: untestedHooks[0].id,
      nicheId,
      reason: `Untested hook "${untestedHooks[0].id}" — worth testing`,
    };
  }

  // Check for hits worth replicating to other niches
  const nicheScore = store.nicheScores[nicheId];
  if (nicheScore && nicheScore.hitRate > 0.2) {
    return {
      action: "replicate",
      templateId,
      hookId: nicheScore.bestHook,
      nicheId,
      reason: `${nicheId} has ${Math.round(nicheScore.hitRate * 100)}% hit rate — replicate winning formula`,
    };
  }

  // Default: create with best-performing hook
  const bestHookScore = Object.values(store.hookScores)
    .filter((h) => h.nicheId === nicheId)
    .sort((a, b) => b.score - a.score)[0];

  return {
    action: "create",
    templateId,
    hookId: bestHookScore?.hookId ?? allHooks[0]?.id ?? "",
    nicheId,
    reason: bestHookScore
      ? `Using best hook (score: ${bestHookScore.score})`
      : "No data yet — using highest estimated retention hook",
  };
}

/** Get top hooks for a niche+template, ordered by score */
export function getTopHooksForNiche(
  store: LearningStore,
  nicheId: string,
  format: string,
): Hook[] {
  const scores = Object.values(store.hookScores)
    .filter((h) => h.nicheId === nicheId)
    .sort((a, b) => b.score - a.score);

  const formatHooks = getHooksForFormat(format);
  const scoredIds = new Set(scores.map((s) => s.hookId));

  // Return scored hooks first, then unscored (by estimated retention)
  const scored = scores
    .map((s) => formatHooks.find((h) => h.id === s.hookId))
    .filter(Boolean) as Hook[];
  const unscored = formatHooks.filter((h) => !scoredIds.has(h.id));

  return [...scored, ...unscored];
}

// ─── Bootstrap ───────────────────────────────────────────────────────────

/**
 * Scan CollectAI codebase to initialize the learning store with
 * niche metadata. This seeds scores at 0 so the system has structure
 * from day 1.
 */
export function bootstrapFromCodebase(store: LearningStore): LearningStore {
  // Initialize niche scores for all known niches
  for (const niche of NICHES) {
    if (!store.nicheScores[niche.id]) {
      store.nicheScores[niche.id] = {
        nicheId: niche.id,
        totalVideos: 0,
        totalViews: 0,
        hitRate: 0,
        bestTemplate: "",
        bestHook: "",
      };
    }
  }

  // Initialize hook scores for all hook × niche combinations
  for (const hook of HOOKS) {
    for (const niche of NICHES) {
      const key = `${hook.id}__${niche.id}`;
      if (!store.hookScores[key]) {
        store.hookScores[key] = {
          hookId: hook.id,
          nicheId: niche.id,
          score: hook.retentionRate * 100, // Seed with estimated retention
          uses: 0,
          hits: 0,
          avgRetention: hook.retentionRate,
          avgViews: 0,
          lastUsed: "",
        };
      }
    }
  }

  // ── Brand context integration ──
  // The brand guide, niche playbooks, and personas are now imported as
  // structured data rather than hardcoded strings. The learning loop uses
  // these to:
  //  1. Score hooks against niche-specific cultural context (playbooks)
  //  2. Match content angles to target personas
  //  3. Enforce brand voice rules when evaluating scripts
  //  4. Select CTAs matched to persona conversion paths

  const playbookCount = NICHE_PLAYBOOKS.length;
  const personaCount = COLLECTOR_PERSONAS.length;
  const angleCount = CONTENT_ANGLES.length;
  const featureCount = PRODUCT_CONTEXT.features.length;
  const ctaCount = CTA_SYSTEM.primaryCTAs.length;
  const winningPatternCount = PLATFORM_CONTEXT.tiktok.winningPatterns.length;
  const voiceRuleCount = BRAND_VOICE.rules.length;

  console.log("[bootstrap] CollectAI brand context loaded:");
  console.log(`  Brand: ${BRAND_IDENTITY.name} — "${BRAND_IDENTITY.tagline}"`);
  console.log(`  Product stats: ${PRODUCT_CONTEXT.stats.categories} categories, ${PRODUCT_CONTEXT.stats.catalogItems} items, ${PRODUCT_CONTEXT.stats.marketplaces} marketplaces`);
  console.log(`  Features: ${featureCount} (best for content: ${PRODUCT_CONTEXT.features.slice(0, 3).map(f => f.id).join(", ")})`);
  console.log(`  Niche playbooks: ${playbookCount} (${NICHE_PLAYBOOKS.map(p => p.nicheId).join(", ")})`);
  console.log(`  Audience personas: ${personaCount} (${COLLECTOR_PERSONAS.map(p => p.id).join(", ")})`);
  console.log(`  Content angles: ${angleCount} (${CONTENT_ANGLES.map(a => a.id).join(", ")})`);
  console.log(`  CTAs: ${ctaCount}, Winning patterns: ${winningPatternCount}, Voice rules: ${voiceRuleCount}`);

  return store;
}
