// ---------------------------------------------------------------------------
// KPI Dashboard — types, demo data, and Supabase queries
// ---------------------------------------------------------------------------

import { getSupabase, isSupabaseConfigured } from "@/lib/supabase";
import {
  noteDemo as noteDemoSource,
  noteUnprovisioned as noteUnprovisionedSource,
  getUnprovisionedTables,
  getDemoReason,
  isUsingDemoData as isUsingDemoSource,
  clearDemo,
} from "@/lib/demoState";

// ─── Swipe File Types ────────────────────────────────────────────────────────

export interface SwipeFileEntry {
  id: string;
  url: string;
  platform: string;
  hookText: string;
  hookType: string;
  format: string;
  niche: string;
  whyItWorks: string;
  tags: string[];
  estimatedViews: number;
  savedBy: string;
  isCompetitor: boolean;
  sourceAccount: string;
  createdAt: string;
}

export interface SwipeFileData {
  entries: SwipeFileEntry[];
  byHookType: Record<string, number>;
  byFormat: Record<string, number>;
  totalEntries: number;
}

// ─── Account Tracking Types ─────────────────────────────────────────────────

export interface TikTokAccount {
  id: string;
  handle: string;
  platform: string;
  language: string;
  description: string;
  followers: number;
  isActive: boolean;
  // Computed from videos
  totalVideos: number;
  totalViews: number;
  avgViews: number;
  hitRate: number;
  bestFormat: string;
  bestHookType: string;
  engagementRate: number;
}

export interface AccountAnalytics {
  accounts: TikTokAccount[];
  totalAccounts: number;
  totalFollowers: number;
  bestPerformingAccount: string;
  formatComparison: Record<string, Record<string, { videos: number; avgViews: number }>>;
}

// ─── Boost/Spark Ads Types ──────────────────────────────────────────────────

export interface BoostMetrics {
  totalBoosted: number;
  totalSpend: number;
  totalBoostedViews: number;
  totalBoostedClicks: number;
  totalBoostedInstalls: number;
  avgCPM: number;
  avgCPC: number;
  avgCPI: number;
  organicROI: number;
  boostedROI: number;
  boostedVideos: Array<{
    videoId: string;
    hookText: string;
    organicViews: number;
    boostedViews: number;
    spend: number;
    installs: number;
    revenue: number;
    roas: number;
  }>;
}

// ─── Types ──────────────────────────────────────────────────────────────────

export interface FunnelMetrics {
  kitOpens: number;
  qrScans: number;
  stepStarts: number;
  videoPlays: number;
  videoWatch90: number;
  stepCompletes: number;
  kitCompletes: number;
  buyClicks: number;
  dropLandingViews: number;
  orders: number;
}

export interface CreatorRow {
  name: string;
  handle: string;
  language: string;
  affiliateCode: string;
  scans: number;
  activations: number;
  completions: number;
  purchases: number;
  revenue: number;
  conversionRate: number;
  netROI: number;          // revenue - COGS - affiliate payout
  kitsSent: number;
  cogsPerKit: number;
  affiliatePayoutPct: number;
}

export interface SalesOverview {
  totalRevenue: number;
  totalOrders: number;
  avgOrderValue: number;
  abandonedCartRate: number;  // buyClicks with no order / buyClicks
  repeatPurchaseRate: number; // repeat orders / total orders
  topKits: Array<{ kitSlug: string; orders: number; revenue: number }>;
}

export interface DailyRevenue {
  date: string;
  orders: number;
  revenue: number;
}

export interface MarketMetrics {
  lang: string;
  scans: number;
  activations: number;
  completions: number;
  orders: number;
  revenue: number;
  conversionRate: number;
}

export interface PodHealth {
  lang: string;
  activeCreators: number;
  totalScans: number;
  totalRevenue: number;
  avgConversionRate: number;
}

// ─── UGC / TikTok Types ─────────────────────────────────────────────────────

export type VideoClassification = "pending" | "fail" | "average" | "hit";

export interface UGCVideo {
  id: string;
  videoId: string;
  accountId: string;
  creatorName: string;
  creatorHandle: string;
  datePosted: string;
  niche: string;
  format: string;
  hookText: string;
  hookType: string;
  conceptCluster: string;
  country: string;
  views2h: number;
  views12h: number;
  views24h: number;
  viewsTotal: number;
  hookRetentionRate: number;
  avgWatchTime: number;
  completionRate: number;
  likes: number;
  comments: number;
  shares: number;
  saves: number;
  clicks: number;
  installs: number;
  revenueCents: number;
  classification: VideoClassification;
  costCents: number;
  videoUrl: string;
  thumbnailUrl: string;
  notes: string;
}

export interface UGCProductionMetrics {
  totalVideos: number;
  videosThisPeriod: number;
  costPerVideo: number;
  avgTimeToPublish: number; // days
  videosPerAccount: Record<string, number>;
  videosPerCreator: Record<string, number>;
}

export interface UGCCreativeMetrics {
  avgHookRetention: number;
  avgWatchTime: number;
  avgCompletionRate: number;
  avgEngagementRate: number;
  avgAmplificationRate: number;
  totalShares: number;
  totalSaves: number;
}

export interface UGCBusinessMetrics {
  avgCTR: number;
  totalInstalls: number;
  avgConversionRate: number;
  revenuePerVideo: number;
  avgCPA: number;
  avgROAS: number;
}

export interface HookAnalysis {
  hookText: string;
  hookType: string;
  videoCount: number;
  avgRetention: number;
  avgViews: number;
  avgShares: number;
}

export interface FormatAnalysis {
  format: string;
  videoCount: number;
  avgWatchTime: number;
  avgCompletionRate: number;
  avgViews: number;
}

export interface ConceptCluster {
  cluster: string;
  videoCount: number;
  avgViews: number;
  bestVideoViews: number;
  hitRate: number; // % of videos classified as "hit"
}

export interface UGCDashboardData {
  videos: UGCVideo[];
  production: UGCProductionMetrics;
  creative: UGCCreativeMetrics;
  business: UGCBusinessMetrics;
  hookAnalysis: HookAnalysis[];
  formatAnalysis: FormatAnalysis[];
  conceptClusters: ConceptCluster[];
  topPerformers: UGCVideo[];
  classificationBreakdown: Record<VideoClassification, number>;
  period: { from: string; to: string; days: number };
}

export interface KPIDashboardData {
  funnel: FunnelMetrics;
  creators: CreatorRow[];
  sales: SalesOverview;
  revenueTimeline: DailyRevenue[];
  marketBreakdown: MarketMetrics[];
  podHealth: PodHealth[];
  period: { from: string; to: string; days: number };
}

// ─── Constants ──────────────────────────────────────────────────────────────

const KIT_COGS_CENTS = 600; // €6
const AFFILIATE_PCT = 15;

// ─── Demo Data ──────────────────────────────────────────────────────────────

/**
 * Demo reporting now lives in demoState.ts, keyed per source. It used to be a
 * single module-global string here, which meant the Creators tab (live rows)
 * showed "Demo Mode" if you had visited Pods first, and tabs whose modules
 * never reported rendered fake numbers under a hidden banner.
 */

/** Records against the "kpi" source: creators / sales / timeline / market. */
function noteDemo<T>(reason: string, value: T): T {
  return noteDemoSource("kpi", reason, value);
}

/**
 * Tables from the admin template that were deliberately never provisioned:
 * kpi_events/orders/daily_revenue/market_metrics modelled a physical kit
 * business and nothing in this app writes them. Their absence means "this
 * section has no data source", which is NOT the same as "these numbers are
 * fake" — so it must not trip the demo banner. Rendered as zeros instead.
 */
function noteUnprovisioned<T>(table: string, zeroValue: T): T {
  return noteUnprovisionedSource("kpi", table, zeroValue);
}

/** Sections with no backing table, for the UI to explain rather than fake. */
export function getUnprovisionedSections(): string[] {
  return getUnprovisionedTables("kpi");
}

const ZERO_FUNNEL: FunnelMetrics = {
  kitOpens: 0, qrScans: 0, stepStarts: 0, videoPlays: 0, videoWatch90: 0,
  stepCompletes: 0, kitCompletes: 0, buyClicks: 0, dropLandingViews: 0, orders: 0,
};

const ZERO_SALES: SalesOverview = {
  totalRevenue: 0, totalOrders: 0, avgOrderValue: 0,
  abandonedCartRate: 0, repeatPurchaseRate: 0, topKits: [],
};

function resetDemoReason(): void {
  clearDemo("kpi");
}

/**
 * Human-readable reason the dashboard is showing demo data, or null when the
 * numbers are real. Only meaningful after an awaited `fetchKPIDashboardData`.
 */
export function getDemoDataReason(): string | null {
  if (!isSupabaseConfigured()) return "Supabase is not configured";
  return getDemoReason("kpi");
}

function getDemoData(days: number): KPIDashboardData {
  const now = new Date();
  const from = new Date(now.getTime() - days * 86400000);

  const creators: CreatorRow[] = [
    { name: "Luna Craft", handle: "@lunacraft_de", language: "DE", affiliateCode: "LUNA10", scans: 842, activations: 387, completions: 156, purchases: 38, revenue: 684, conversionRate: 4.5, kitsSent: 2, cogsPerKit: 6, affiliatePayoutPct: 15, netROI: 0 },
    { name: "Maille Douce", handle: "@maille.douce", language: "FR", affiliateCode: "MAILLE10", scans: 723, activations: 312, completions: 134, purchases: 31, revenue: 558, conversionRate: 4.3, kitsSent: 2, cogsPerKit: 6, affiliatePayoutPct: 15, netROI: 0 },
    { name: "Punto Creativo", handle: "@puntocreativo", language: "IT", affiliateCode: "PUNTO10", scans: 651, activations: 289, completions: 112, purchases: 27, revenue: 486, conversionRate: 4.1, kitsSent: 2, cogsPerKit: 6, affiliatePayoutPct: 15, netROI: 0 },
    { name: "Haak Mee", handle: "@haakmee.nl", language: "NL", affiliateCode: "HAAK10", scans: 598, activations: 267, completions: 98, purchases: 24, revenue: 432, conversionRate: 4.0, kitsSent: 2, cogsPerKit: 6, affiliatePayoutPct: 15, netROI: 0 },
    { name: "Stitch Witch", handle: "@stitchwitch_en", language: "EN", affiliateCode: "STITCH10", scans: 534, activations: 231, completions: 89, purchases: 21, revenue: 378, conversionRate: 3.9, kitsSent: 2, cogsPerKit: 6, affiliatePayoutPct: 15, netROI: 0 },
    { name: "Wolke Wolle", handle: "@wolkewolle", language: "DE", affiliateCode: "WOLKE10", scans: 489, activations: 198, completions: 76, purchases: 18, revenue: 324, conversionRate: 3.7, kitsSent: 2, cogsPerKit: 6, affiliatePayoutPct: 15, netROI: 0 },
    { name: "Collector Carmen", handle: "@collector.carmen", language: "ES", affiliateCode: "CARMEN10", scans: 412, activations: 167, completions: 61, purchases: 14, revenue: 252, conversionRate: 3.4, kitsSent: 2, cogsPerKit: 6, affiliatePayoutPct: 15, netROI: 0 },
    { name: "Garn Lisa", handle: "@garnlisa", language: "DE", affiliateCode: "GARN10", scans: 356, activations: 142, completions: 48, purchases: 11, revenue: 198, conversionRate: 3.1, kitsSent: 2, cogsPerKit: 6, affiliatePayoutPct: 15, netROI: 0 },
    { name: "Fil et Aiguille", handle: "@fil.aiguille", language: "FR", affiliateCode: "FIL10", scans: 287, activations: 108, completions: 37, purchases: 8, revenue: 144, conversionRate: 2.8, kitsSent: 2, cogsPerKit: 6, affiliatePayoutPct: 15, netROI: 0 },
    { name: "Filo Magico", handle: "@filomagico_it", language: "IT", affiliateCode: "FILO10", scans: 234, activations: 89, completions: 29, purchases: 6, revenue: 108, conversionRate: 2.6, kitsSent: 2, cogsPerKit: 6, affiliatePayoutPct: 15, netROI: 0 },
  ];

  // Calculate net ROI for each creator
  for (const c of creators) {
    const seedCost = c.kitsSent * c.cogsPerKit;
    const affiliatePayout = c.revenue * (c.affiliatePayoutPct / 100);
    c.netROI = Math.round((c.revenue - seedCost - affiliatePayout) * 100) / 100;
  }

  const totalScans = creators.reduce((s, c) => s + c.scans, 0);
  const totalActivations = creators.reduce((s, c) => s + c.activations, 0);
  const totalCompletions = creators.reduce((s, c) => s + c.completions, 0);
  const totalPurchases = creators.reduce((s, c) => s + c.purchases, 0);
  const totalRevenue = creators.reduce((s, c) => s + c.revenue, 0);
  const buyClicks = Math.round(totalCompletions * 1.4);
  const kitOpens = Math.round(totalScans * 1.3); // some arrive via non-QR sources
  const videoPlays = Math.round(totalActivations * 0.85);
  const videoWatch90 = Math.round(videoPlays * 0.65);
  const stepCompletes = Math.round(totalActivations * 0.7);
  const dropLandingViews = Math.round(totalScans * 0.4);

  // Generate daily revenue timeline
  const revenueTimeline: DailyRevenue[] = [];
  const daysToShow = Math.min(days, 30);
  for (let i = daysToShow - 1; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 86400000);
    const base = totalRevenue / daysToShow;
    const variance = (Math.sin(i * 0.7) + 1) * 0.3 + 0.7;
    revenueTimeline.push({
      date: d.toISOString().slice(0, 10),
      orders: Math.round((totalPurchases / daysToShow) * variance),
      revenue: Math.round(base * variance),
    });
  }

  // Market breakdown by language
  const langGroups: Record<string, CreatorRow[]> = {};
  for (const c of creators) {
    if (!langGroups[c.language]) langGroups[c.language] = [];
    langGroups[c.language].push(c);
  }

  const marketBreakdown: MarketMetrics[] = Object.entries(langGroups)
    .map(([lang, group]) => {
      const scans = group.reduce((s, c) => s + c.scans, 0);
      const orders = group.reduce((s, c) => s + c.purchases, 0);
      return {
        lang,
        scans,
        activations: group.reduce((s, c) => s + c.activations, 0),
        completions: group.reduce((s, c) => s + c.completions, 0),
        orders,
        revenue: group.reduce((s, c) => s + c.revenue, 0),
        conversionRate: scans > 0 ? Math.round((orders / scans) * 1000) / 10 : 0,
      };
    })
    .sort((a, b) => b.revenue - a.revenue);

  // Pod health
  const podHealth: PodHealth[] = Object.entries(langGroups)
    .map(([lang, group]) => ({
      lang,
      activeCreators: group.length,
      totalScans: group.reduce((s, c) => s + c.scans, 0),
      totalRevenue: group.reduce((s, c) => s + c.revenue, 0),
      avgConversionRate:
        group.reduce((s, c) => s + c.conversionRate, 0) / group.length,
    }))
    .sort((a, b) => b.totalRevenue - a.totalRevenue);

  return {
    funnel: {
      kitOpens,
      qrScans: totalScans,
      stepStarts: totalActivations,
      videoPlays,
      videoWatch90,
      stepCompletes,
      kitCompletes: totalCompletions,
      buyClicks,
      dropLandingViews,
      orders: totalPurchases,
    },
    creators,
    sales: {
      totalRevenue,
      totalOrders: totalPurchases,
      avgOrderValue: Math.round((totalRevenue / totalPurchases) * 100) / 100,
      abandonedCartRate: Math.round(((buyClicks - totalPurchases) / buyClicks) * 1000) / 10,
      repeatPurchaseRate: 18.5, // demo: 18.5% repeat
      topKits: [
        { kitSlug: "momo-frog", orders: 62, revenue: 1116 },
        { kitSlug: "benny-bunny", orders: 48, revenue: 864 },
        { kitSlug: "cleo-camel", orders: 34, revenue: 612 },
        { kitSlug: "remy-frog", orders: 28, revenue: 504 },
        { kitSlug: "dax-horse", orders: 26, revenue: 468 },
      ],
    },
    revenueTimeline,
    marketBreakdown,
    podHealth,
    period: {
      from: from.toISOString().slice(0, 10),
      to: now.toISOString().slice(0, 10),
      days,
    },
  };
}

// ─── Supabase Queries ───────────────────────────────────────────────────────

async function fetchFunnel(days: number): Promise<FunnelMetrics> {
  const sb = getSupabase();
  if (!sb) return noteDemo("no Supabase client", getDemoData(days).funnel);

  const since = new Date(Date.now() - days * 86400000).toISOString();

  const { data, error } = await sb
    .from("kpi_events")
    .select("event_name")
    .gte("created_at", since);

  if (error) {
    // Deliberately unprovisioned template table -> zeros, not demo numbers.
    if (error.code === "42P01") return noteUnprovisioned("kpi_events", ZERO_FUNNEL);
    return noteDemo(
      `kpi_events unreadable (${error.code ?? "?"}: ${error.message})`,
      getDemoData(days).funnel,
    );
  }
  if (!data) return noteDemo("kpi_events returned no data", getDemoData(days).funnel);

  const counts: Record<string, number> = {};
  for (const row of data) {
    counts[row.event_name] = (counts[row.event_name] || 0) + 1;
  }

  const { count: orderCount } = await sb
    .from("orders")
    .select("id", { count: "exact", head: true })
    .gte("created_at", since);

  return {
    kitOpens: counts["kit_open"] || 0,
    qrScans: counts["qr_scan"] || 0,
    stepStarts: counts["step_start"] || 0,
    videoPlays: counts["video_play"] || 0,
    videoWatch90: counts["video_watch90"] || 0,
    stepCompletes: counts["step_complete"] || 0,
    kitCompletes: counts["kit_complete"] || 0,
    buyClicks: counts["buy_click"] || 0,
    dropLandingViews: counts["drop_landing_view"] || 0,
    orders: orderCount || 0,
  };
}

/** Everything /api/kpi-aggregates returns. */
export interface KPIAggregates {
  creators: Record<string, any>[];
  signupCounts: Record<string, number>;
  revenueAgg: Record<string, { count: number; revenue: number }>;
  sales: {
    totalOrders: number; totalRevenue: number;
    attributedOrders: number; attributedRevenue: number;
    byPlan: Record<string, { orders: number; revenue: number }>;
  };
  timeline: DailyRevenue[];
  market: Record<string, { signups: number; orders: number; revenue: number }>;
  totalSignups: number;
  attributedSignups: number;
}

/**
 * Single server-side fetch backing every revenue-bearing section.
 *
 * One call, not four: each section used to read a different table, so a Pro
 * subscription attributed to a creator appeared on the Creators tab and as 0.00
 * everywhere else. Server-side because subscription_events is RLS-locked with
 * no policy — the anon key reads zero rows silently rather than erroring.
 *
 * Returns null (with the demo reason recorded) when unavailable, so callers
 * fall back consistently instead of each inventing its own failure mode.
 */
async function fetchAggregates(days: number): Promise<KPIAggregates | null> {
  try {
    const res = await fetch(`/api/kpi-aggregates?days=${days}`, {
      credentials: "same-origin",
    });
    if (!res.ok) {
      const { error: msg } = (await res.json().catch(() => ({}))) as { error?: string };
      noteDemo(
        res.status === 401
          ? "admin session expired — re-enter the PIN to load dashboard data"
          : (msg ?? `dashboard aggregates unavailable (HTTP ${res.status})`),
        null,
      );
      return null;
    }
    return (await res.json()) as KPIAggregates;
  } catch (e) {
    noteDemo(
      `dashboard aggregates request failed: ${e instanceof Error ? e.message : String(e)}`,
      null,
    );
    return null;
  }
}

function buildCreatorRows(agg: KPIAggregates | null, days: number): CreatorRow[] {
  if (!agg) return getDemoData(days).creators;

  const creators = agg.creators ?? [];
  const signupCounts = agg.signupCounts ?? {};
  const orderAgg = agg.revenueAgg ?? {};

  if (creators.length === 0) {
    return noteDemo("no active creators in the roster", getDemoData(days).creators);
  }

  return creators
    .map((c) => {
      const oa = orderAgg[c.affiliate_code] || { count: 0, revenue: 0 };
      // `scans` is the CreatorRow field name inherited from the kit template;
      // here it means attributed signups — the top of our funnel.
      const scans = signupCounts[c.affiliate_code] || 0;
      const kitsSent = c.kits_sent ?? 2;
      const cogsPerKit = (c.cogs_per_kit_cents ?? KIT_COGS_CENTS) / 100;
      const affiliatePayoutPct = c.affiliate_payout_pct ?? AFFILIATE_PCT;
      const seedCost = kitsSent * cogsPerKit;
      const affiliatePayout = oa.revenue * (affiliatePayoutPct / 100);
      return {
        name: c.name,
        handle: c.handle,
        language: c.language?.toUpperCase() || "—",
        affiliateCode: c.affiliate_code,
        scans,
        // No equivalent app-side signal yet: the kit template measured
        // onboarding steps we do not emit. Left at 0 rather than faked.
        activations: 0,
        completions: 0,
        purchases: oa.count,
        revenue: oa.revenue,
        conversionRate:
          scans > 0 ? Math.round((oa.count / scans) * 1000) / 10 : 0,
        netROI: Math.round((oa.revenue - seedCost - affiliatePayout) * 100) / 100,
        kitsSent,
        cogsPerKit,
        affiliatePayoutPct,
      };
    })
    .sort((a, b) => b.revenue - a.revenue);
}

/**
 * Sales from the subscription ledger — the same rows the creator leaderboard
 * sums, so an attributed Pro subscription reconciles across tabs instead of
 * showing 4.99 on one and 0.00 on the rest.
 *
 * `topKits` now carries the plan mix (pro/premium) rather than kit slugs: this
 * app sells subscriptions, not physical kits. The field name is retained
 * because CreatorRow/SalesOverview are consumed by several components.
 */
function buildSalesOverview(agg: KPIAggregates | null, days: number): SalesOverview {
  if (!agg) return getDemoData(days).sales;

  const { totalOrders, totalRevenue, byPlan } = agg.sales;
  if (totalOrders === 0) return ZERO_SALES;

  const topKits = Object.entries(byPlan)
    .map(([plan, v]) => ({
      kitSlug: plan,
      orders: v.orders,
      revenue: Math.round(v.revenue * 100) / 100,
    }))
    .sort((a, b) => b.orders - a.orders)
    .slice(0, 5);

  return {
    totalRevenue,
    totalOrders,
    avgOrderValue: Math.round((totalRevenue / totalOrders) * 100) / 100,
    // Not derivable without a checkout-intent event; PostHog territory, and
    // reporting 0 is honest where inventing a rate would not be.
    abandonedCartRate: 0,
    // A renewal is the repeat signal. Orders beyond the first per creator code
    // approximate it until we track per-user transaction sequence.
    repeatPurchaseRate:
      totalOrders > 0
        ? Math.round(((totalOrders - Object.keys(agg.revenueAgg).length) / totalOrders) * 1000) / 10
        : 0,
    topKits,
  };
}

/** Daily revenue, derived from the ledger rather than the unused daily_revenue table. */
function buildRevenueTimeline(agg: KPIAggregates | null, days: number): DailyRevenue[] {
  if (!agg) return getDemoData(days).revenueTimeline;
  return agg.timeline ?? [];
}

/**
 * Market breakdown by the creator's language. Signups come from attributed
 * profiles, revenue from the ledger — both rolled up through creators.language.
 */
function buildMarketBreakdown(agg: KPIAggregates | null, days: number): MarketMetrics[] {
  if (!agg) return getDemoData(days).marketBreakdown;

  return Object.entries(agg.market ?? {})
    .map(([lang, m]) => ({
      lang,
      scans: m.signups,
      // No app-side onboarding-step signal yet; 0 rather than fabricated.
      activations: 0,
      completions: 0,
      orders: m.orders,
      revenue: Math.round(m.revenue * 100) / 100,
      conversionRate:
        m.signups > 0 ? Math.round((m.orders / m.signups) * 1000) / 10 : 0,
    }))
    .sort((a, b) => b.revenue - a.revenue);
}

export async function fetchKPIDashboardData(
  days: number = 30,
): Promise<KPIDashboardData> {
  resetDemoReason();

  if (!isSupabaseConfigured()) {
    return getDemoData(days);
  }

  const now = new Date();
  const from = new Date(now.getTime() - days * 86400000);

  // One aggregates call feeds creators, sales, timeline and market, so every
  // tab reconciles against the same ledger rows. Previously each section read a
  // different table and an attributed Pro subscription showed up on the
  // Creators tab alone.
  const [funnel, aggregates] = await Promise.all([
    fetchFunnel(days),
    fetchAggregates(days),
  ]);

  const creators = buildCreatorRows(aggregates, days);
  const sales = buildSalesOverview(aggregates, days);
  const revenueTimeline = buildRevenueTimeline(aggregates, days);
  const marketBreakdown = buildMarketBreakdown(aggregates, days);

  // Derive pod health from creators
  const langGroups: Record<string, CreatorRow[]> = {};
  for (const c of creators) {
    if (!langGroups[c.language]) langGroups[c.language] = [];
    langGroups[c.language].push(c);
  }

  const podHealth: PodHealth[] = Object.entries(langGroups)
    .map(([lang, group]) => ({
      lang,
      activeCreators: group.length,
      totalScans: group.reduce((s, c) => s + c.scans, 0),
      totalRevenue: group.reduce((s, c) => s + c.revenue, 0),
      avgConversionRate:
        Math.round(
          (group.reduce((s, c) => s + c.conversionRate, 0) / group.length) * 10,
        ) / 10,
    }))
    .sort((a, b) => b.totalRevenue - a.totalRevenue);

  return {
    funnel,
    creators,
    sales,
    revenueTimeline,
    marketBreakdown,
    podHealth,
    period: {
      from: from.toISOString().slice(0, 10),
      to: now.toISOString().slice(0, 10),
      days,
    },
  };
}

export function isUsingDemoData(): boolean {
  // Being configured is not the same as being provisioned. If any fetch fell
  // back — missing table, unreadable table, empty roster — the numbers on
  // screen are demo numbers regardless of whether Supabase creds are present.
  return !isSupabaseConfigured() || isUsingDemoSource("kpi");
}

// ─── CSV Export ──────────────────────────────────────────────────────────────

// ─── UGC Classification ──────────────────────────────────────────────────────

function classifyVideo(views24h: number, hookRetention: number, shares: number): VideoClassification {
  if (views24h >= 20000 && (hookRetention >= 0.4 || shares >= 50)) return "hit";
  if (views24h >= 5000) return "average";
  if (views24h > 0) return "fail";
  return "pending";
}

// ─── UGC Demo Data ──────────────────────────────────────────────────────────

function getUGCDemoData(days: number): UGCDashboardData {
  const now = new Date();
  const from = new Date(now.getTime() - days * 86400000);

  const hooks = [
    { text: "POV: your first grail pull from a random pack", type: "POV" },
    { text: "I made this in one evening", type: "statement" },
    { text: "Why is nobody talking about this collecting hack?", type: "question" },
    { text: "Wait for the finished result...", type: "suspense" },
    { text: "3 reasons to start tracking your collection today", type: "list" },
    { text: "This kit changed my evening routine", type: "testimonial" },
  ];
  const formats = ["tutorial", "POV", "transition", "unboxing", "timelapse", "GRWM"];
  const clusters = ["beginner-journey", "evening-routine", "gift-idea", "stress-relief", "mindful-making"];
  const accounts = ["@collectai.eu", "@collectai.de", "@collectai.fr", "@collectai.nl"];
  const creators = [
    { name: "Luna Craft", handle: "@lunacraft_de" },
    { name: "Maille Douce", handle: "@maille.douce" },
    { name: "Stitch Witch", handle: "@stitchwitch_en" },
    { name: "Haak Mee", handle: "@haakmee.nl" },
  ];

  const videos: UGCVideo[] = Array.from({ length: 24 }, (_, i) => {
    const hook = hooks[i % hooks.length];
    const views24h = Math.round(Math.random() * 40000 + 1000);
    const hookRet = Math.round((Math.random() * 0.5 + 0.2) * 10000) / 10000;
    const shares = Math.round(Math.random() * 80);
    const creator = creators[i % creators.length];
    return {
      id: `demo-${i}`,
      videoId: `tiktok-${1000 + i}`,
      accountId: accounts[i % accounts.length],
      creatorName: creator.name,
      creatorHandle: creator.handle,
      datePosted: new Date(now.getTime() - (i * 2 + 1) * 86400000).toISOString().slice(0, 10),
      niche: "collectibles",
      format: formats[i % formats.length],
      hookText: hook.text,
      hookType: hook.type,
      conceptCluster: clusters[i % clusters.length],
      country: ["DE", "FR", "NL", "EN", "ES", "IT"][i % 6],
      views2h: Math.round(views24h * 0.15),
      views12h: Math.round(views24h * 0.6),
      views24h,
      viewsTotal: Math.round(views24h * 1.8),
      hookRetentionRate: hookRet,
      avgWatchTime: Math.round((Math.random() * 20 + 5) * 100) / 100,
      completionRate: Math.round((Math.random() * 0.6 + 0.1) * 10000) / 10000,
      likes: Math.round(Math.random() * 500 + 50),
      comments: Math.round(Math.random() * 40),
      shares,
      saves: Math.round(Math.random() * 120),
      clicks: Math.round(Math.random() * 200 + 10),
      installs: Math.round(Math.random() * 30),
      revenueCents: Math.round(Math.random() * 5000),
      classification: classifyVideo(views24h, hookRet, shares),
      costCents: Math.round(Math.random() * 3000 + 500),
      videoUrl: "",
      thumbnailUrl: "",
      notes: "",
    };
  });

  const totalVideos = videos.length;
  const totalViews = videos.reduce((s, v) => s + v.viewsTotal, 0);
  const totalShares = videos.reduce((s, v) => s + v.shares, 0);
  const totalSaves = videos.reduce((s, v) => s + v.saves, 0);
  const totalClicks = videos.reduce((s, v) => s + v.clicks, 0);
  const totalInstalls = videos.reduce((s, v) => s + v.installs, 0);
  const totalRevenue = videos.reduce((s, v) => s + v.revenueCents, 0);
  const totalCost = videos.reduce((s, v) => s + v.costCents, 0);

  // Production
  const videosPerAccount: Record<string, number> = {};
  const videosPerCreator: Record<string, number> = {};
  for (const v of videos) {
    videosPerAccount[v.accountId] = (videosPerAccount[v.accountId] || 0) + 1;
    videosPerCreator[v.creatorName] = (videosPerCreator[v.creatorName] || 0) + 1;
  }

  // Hook analysis
  const hookGroups: Record<string, UGCVideo[]> = {};
  for (const v of videos) {
    const key = v.hookText;
    if (!hookGroups[key]) hookGroups[key] = [];
    hookGroups[key].push(v);
  }
  const hookAnalysis: HookAnalysis[] = Object.entries(hookGroups)
    .map(([hookText, vids]) => ({
      hookText,
      hookType: vids[0].hookType,
      videoCount: vids.length,
      avgRetention: Math.round((vids.reduce((s, v) => s + v.hookRetentionRate, 0) / vids.length) * 10000) / 10000,
      avgViews: Math.round(vids.reduce((s, v) => s + v.viewsTotal, 0) / vids.length),
      avgShares: Math.round(vids.reduce((s, v) => s + v.shares, 0) / vids.length),
    }))
    .sort((a, b) => b.avgViews - a.avgViews);

  // Format analysis
  const formatGroups: Record<string, UGCVideo[]> = {};
  for (const v of videos) {
    if (!formatGroups[v.format]) formatGroups[v.format] = [];
    formatGroups[v.format].push(v);
  }
  const formatAnalysis: FormatAnalysis[] = Object.entries(formatGroups)
    .map(([format, vids]) => ({
      format,
      videoCount: vids.length,
      avgWatchTime: Math.round((vids.reduce((s, v) => s + v.avgWatchTime, 0) / vids.length) * 100) / 100,
      avgCompletionRate: Math.round((vids.reduce((s, v) => s + v.completionRate, 0) / vids.length) * 10000) / 10000,
      avgViews: Math.round(vids.reduce((s, v) => s + v.viewsTotal, 0) / vids.length),
    }))
    .sort((a, b) => b.avgViews - a.avgViews);

  // Concept clusters
  const clusterGroups: Record<string, UGCVideo[]> = {};
  for (const v of videos) {
    if (!clusterGroups[v.conceptCluster]) clusterGroups[v.conceptCluster] = [];
    clusterGroups[v.conceptCluster].push(v);
  }
  const conceptClusters: ConceptCluster[] = Object.entries(clusterGroups)
    .map(([cluster, vids]) => ({
      cluster,
      videoCount: vids.length,
      avgViews: Math.round(vids.reduce((s, v) => s + v.viewsTotal, 0) / vids.length),
      bestVideoViews: Math.max(...vids.map((v) => v.viewsTotal)),
      hitRate: Math.round((vids.filter((v) => v.classification === "hit").length / vids.length) * 100),
    }))
    .sort((a, b) => b.avgViews - a.avgViews);

  // Classification breakdown
  const classificationBreakdown: Record<VideoClassification, number> = { pending: 0, fail: 0, average: 0, hit: 0 };
  for (const v of videos) classificationBreakdown[v.classification]++;

  return {
    videos,
    production: {
      totalVideos,
      videosThisPeriod: totalVideos,
      costPerVideo: totalCost > 0 ? Math.round(totalCost / totalVideos) / 100 : 0,
      avgTimeToPublish: 1.5,
      videosPerAccount,
      videosPerCreator,
    },
    creative: {
      avgHookRetention: Math.round((videos.reduce((s, v) => s + v.hookRetentionRate, 0) / totalVideos) * 10000) / 10000,
      avgWatchTime: Math.round((videos.reduce((s, v) => s + v.avgWatchTime, 0) / totalVideos) * 100) / 100,
      avgCompletionRate: Math.round((videos.reduce((s, v) => s + v.completionRate, 0) / totalVideos) * 10000) / 10000,
      avgEngagementRate: totalViews > 0 ? Math.round(((videos.reduce((s, v) => s + v.likes + v.comments + v.shares, 0)) / totalViews) * 10000) / 10000 : 0,
      avgAmplificationRate: totalViews > 0 ? Math.round((totalShares / totalViews) * 10000) / 10000 : 0,
      totalShares,
      totalSaves,
    },
    business: {
      avgCTR: totalViews > 0 ? Math.round((totalClicks / totalViews) * 10000) / 10000 : 0,
      totalInstalls,
      avgConversionRate: totalClicks > 0 ? Math.round((totalInstalls / totalClicks) * 10000) / 10000 : 0,
      revenuePerVideo: totalVideos > 0 ? Math.round(totalRevenue / totalVideos) / 100 : 0,
      avgCPA: totalInstalls > 0 ? Math.round(totalCost / totalInstalls) / 100 : 0,
      avgROAS: totalCost > 0 ? Math.round((totalRevenue / totalCost) * 100) / 100 : 0,
    },
    hookAnalysis,
    formatAnalysis,
    conceptClusters,
    topPerformers: [...videos].sort((a, b) => b.viewsTotal - a.viewsTotal).slice(0, 5),
    classificationBreakdown,
    period: { from: from.toISOString().slice(0, 10), to: now.toISOString().slice(0, 10), days },
  };
}

// ─── UGC Fetch ──────────────────────────────────────────────────────────────

export async function fetchUGCDashboardData(days: number = 30): Promise<UGCDashboardData> {
  clearDemo("ugc");
  if (!isSupabaseConfigured()) {
    return noteDemoSource("ugc", "Supabase is not configured", getUGCDemoData(days));
  }

  const sb = getSupabase();
  if (!sb) return noteDemoSource("ugc", "no Supabase client", getUGCDemoData(days));

  const since = new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);

  const { data: rows, error } = await sb
    .from("ugc_videos")
    .select("*, creators(name, handle)")
    .gte("date_posted", since)
    .order("date_posted", { ascending: false });

  if (error) {
    return noteDemoSource(
      "ugc",
      error.code === "42P01"
        ? "ugc_videos not provisioned (003_ugc_video_tracking.sql)"
        : `ugc_videos unreadable (${error.code}: ${error.message})`,
      getUGCDemoData(days),
    );
  }
  if (!rows || rows.length === 0) {
    return noteDemoSource("ugc", "no videos in ugc_videos yet — showing sample data", getUGCDemoData(days));
  }

  const videos: UGCVideo[] = rows.map((r: Record<string, unknown>) => ({
    id: r.id as string,
    videoId: r.video_id as string,
    accountId: r.account_id as string,
    creatorName: (r.creators as Record<string, string>)?.name ?? "",
    creatorHandle: (r.creators as Record<string, string>)?.handle ?? "",
    datePosted: r.date_posted as string,
    niche: (r.niche as string) ?? "",
    format: (r.format as string) ?? "",
    hookText: (r.hook_text as string) ?? "",
    hookType: (r.hook_type as string) ?? "",
    conceptCluster: (r.concept_cluster as string) ?? "",
    country: (r.country as string) ?? "",
    views2h: (r.views_2h as number) ?? 0,
    views12h: (r.views_12h as number) ?? 0,
    views24h: (r.views_24h as number) ?? 0,
    viewsTotal: (r.views_total as number) ?? 0,
    hookRetentionRate: Number(r.hook_retention_rate ?? 0),
    avgWatchTime: Number(r.avg_watch_time ?? 0),
    completionRate: Number(r.completion_rate ?? 0),
    likes: (r.likes as number) ?? 0,
    comments: (r.comments as number) ?? 0,
    shares: (r.shares as number) ?? 0,
    saves: (r.saves as number) ?? 0,
    clicks: (r.clicks as number) ?? 0,
    installs: (r.installs as number) ?? 0,
    revenueCents: (r.revenue_cents as number) ?? 0,
    classification: (r.classification as VideoClassification) ?? "pending",
    costCents: (r.cost_cents as number) ?? 0,
    videoUrl: (r.video_url as string) ?? "",
    thumbnailUrl: (r.thumbnail_url as string) ?? "",
    notes: (r.notes as string) ?? "",
  }));

  // Recompute all aggregates from fetched data
  return computeUGCAggregates(videos, days);
}

function computeUGCAggregates(videos: UGCVideo[], days: number): UGCDashboardData {
  const now = new Date();
  const from = new Date(now.getTime() - days * 86400000);
  const totalVideos = videos.length;
  const totalViews = videos.reduce((s, v) => s + v.viewsTotal, 0);
  const totalShares = videos.reduce((s, v) => s + v.shares, 0);
  const totalSaves = videos.reduce((s, v) => s + v.saves, 0);
  const totalClicks = videos.reduce((s, v) => s + v.clicks, 0);
  const totalInstalls = videos.reduce((s, v) => s + v.installs, 0);
  const totalRevenue = videos.reduce((s, v) => s + v.revenueCents, 0);
  const totalCost = videos.reduce((s, v) => s + v.costCents, 0);

  const videosPerAccount: Record<string, number> = {};
  const videosPerCreator: Record<string, number> = {};
  for (const v of videos) {
    videosPerAccount[v.accountId] = (videosPerAccount[v.accountId] || 0) + 1;
    videosPerCreator[v.creatorName] = (videosPerCreator[v.creatorName] || 0) + 1;
  }

  const hookGroups: Record<string, UGCVideo[]> = {};
  for (const v of videos) {
    if (!hookGroups[v.hookText]) hookGroups[v.hookText] = [];
    hookGroups[v.hookText].push(v);
  }
  const hookAnalysis = Object.entries(hookGroups)
    .map(([hookText, vids]) => ({
      hookText,
      hookType: vids[0].hookType,
      videoCount: vids.length,
      avgRetention: Math.round((vids.reduce((s, v) => s + v.hookRetentionRate, 0) / vids.length) * 10000) / 10000,
      avgViews: Math.round(vids.reduce((s, v) => s + v.viewsTotal, 0) / vids.length),
      avgShares: Math.round(vids.reduce((s, v) => s + v.shares, 0) / vids.length),
    }))
    .sort((a, b) => b.avgViews - a.avgViews);

  const formatGroups: Record<string, UGCVideo[]> = {};
  for (const v of videos) {
    if (!formatGroups[v.format]) formatGroups[v.format] = [];
    formatGroups[v.format].push(v);
  }
  const formatAnalysis = Object.entries(formatGroups)
    .map(([format, vids]) => ({
      format,
      videoCount: vids.length,
      avgWatchTime: Math.round((vids.reduce((s, v) => s + v.avgWatchTime, 0) / vids.length) * 100) / 100,
      avgCompletionRate: Math.round((vids.reduce((s, v) => s + v.completionRate, 0) / vids.length) * 10000) / 10000,
      avgViews: Math.round(vids.reduce((s, v) => s + v.viewsTotal, 0) / vids.length),
    }))
    .sort((a, b) => b.avgViews - a.avgViews);

  const clusterGroups: Record<string, UGCVideo[]> = {};
  for (const v of videos) {
    if (!clusterGroups[v.conceptCluster]) clusterGroups[v.conceptCluster] = [];
    clusterGroups[v.conceptCluster].push(v);
  }
  const conceptClusters = Object.entries(clusterGroups)
    .map(([cluster, vids]) => ({
      cluster,
      videoCount: vids.length,
      avgViews: Math.round(vids.reduce((s, v) => s + v.viewsTotal, 0) / vids.length),
      bestVideoViews: Math.max(...vids.map((v) => v.viewsTotal)),
      hitRate: Math.round((vids.filter((v) => v.classification === "hit").length / vids.length) * 100),
    }))
    .sort((a, b) => b.avgViews - a.avgViews);

  const classificationBreakdown: Record<VideoClassification, number> = { pending: 0, fail: 0, average: 0, hit: 0 };
  for (const v of videos) classificationBreakdown[v.classification]++;

  return {
    videos,
    production: {
      totalVideos,
      videosThisPeriod: totalVideos,
      costPerVideo: totalCost > 0 ? Math.round(totalCost / totalVideos) / 100 : 0,
      avgTimeToPublish: 0,
      videosPerAccount,
      videosPerCreator,
    },
    creative: {
      avgHookRetention: totalVideos > 0 ? Math.round((videos.reduce((s, v) => s + v.hookRetentionRate, 0) / totalVideos) * 10000) / 10000 : 0,
      avgWatchTime: totalVideos > 0 ? Math.round((videos.reduce((s, v) => s + v.avgWatchTime, 0) / totalVideos) * 100) / 100 : 0,
      avgCompletionRate: totalVideos > 0 ? Math.round((videos.reduce((s, v) => s + v.completionRate, 0) / totalVideos) * 10000) / 10000 : 0,
      avgEngagementRate: totalViews > 0 ? Math.round((videos.reduce((s, v) => s + v.likes + v.comments + v.shares, 0) / totalViews) * 10000) / 10000 : 0,
      avgAmplificationRate: totalViews > 0 ? Math.round((totalShares / totalViews) * 10000) / 10000 : 0,
      totalShares,
      totalSaves,
    },
    business: {
      avgCTR: totalViews > 0 ? Math.round((totalClicks / totalViews) * 10000) / 10000 : 0,
      totalInstalls,
      avgConversionRate: totalClicks > 0 ? Math.round((totalInstalls / totalClicks) * 10000) / 10000 : 0,
      revenuePerVideo: totalVideos > 0 ? Math.round(totalRevenue / totalVideos) / 100 : 0,
      avgCPA: totalInstalls > 0 ? Math.round(totalCost / totalInstalls) / 100 : 0,
      avgROAS: totalCost > 0 ? Math.round((totalRevenue / totalCost) * 100) / 100 : 0,
    },
    hookAnalysis,
    formatAnalysis,
    conceptClusters,
    topPerformers: [...videos].sort((a, b) => b.viewsTotal - a.viewsTotal).slice(0, 5),
    classificationBreakdown,
    period: { from: from.toISOString().slice(0, 10), to: now.toISOString().slice(0, 10), days },
  };
}

// ─── UGC CSV Export ─────────────────────────────────────────────────────────

// ─── Swipe File Fetch ───────────────────────────────────────────────────────

function getDemoSwipeData(): SwipeFileData {
  const entries: SwipeFileEntry[] = [
    { id: "sw-1", url: "https://tiktok.com/@competitor/video/1", platform: "tiktok", hookText: "This $3 pack had a $2,000 card inside", hookType: "reveal", format: "unboxing", niche: "pokemon_tcg", whyItWorks: "Suspense + dopamine hit on reveal, relatable low investment", tags: ["pack-opening", "reveal", "value"], estimatedViews: 450000, savedBy: "Merle", isCompetitor: true, sourceAccount: "@pokepulls", createdAt: "2026-03-20" },
    { id: "sw-2", url: "https://tiktok.com/@competitor/video/2", platform: "tiktok", hookText: "I found this at a garage sale for $5", hookType: "suspense", format: "POV", niche: "lego", whyItWorks: "Aspiration + FOMO, every collector dreams of cheap grails", tags: ["thrift-find", "hidden-gem", "value"], estimatedViews: 280000, savedBy: "Merle", isCompetitor: true, sourceAccount: "@brickfinds", createdAt: "2026-03-18" },
    { id: "sw-3", url: "https://tiktok.com/@competitor/video/3", platform: "tiktok", hookText: "How much is this ACTUALLY worth?", hookType: "question", format: "comparison", niche: "funko", whyItWorks: "Universal curiosity gap + price revelation drives engagement", tags: ["price-check", "valuation", "curiosity"], estimatedViews: 190000, savedBy: "Merle", isCompetitor: false, sourceAccount: "@funkovalues", createdAt: "2026-03-15" },
    { id: "sw-4", url: "https://tiktok.com/@competitor/video/4", platform: "instagram", hookText: "My $50K watch collection in 15 seconds", hookType: "list", format: "collection-tour", niche: "watches", whyItWorks: "Social proof + aspiration, rapid-fire visual content", tags: ["collection-flex", "portfolio", "luxury"], estimatedViews: 320000, savedBy: "Merle", isCompetitor: true, sourceAccount: "@watchflex", createdAt: "2026-03-12" },
    { id: "sw-5", url: "https://tiktok.com/@competitor/video/5", platform: "tiktok", hookText: "This just got VAULTED. Prices already moving.", hookType: "suspense", format: "market-analysis", niche: "funko", whyItWorks: "FOMO + urgency, collectors panic-buy on vault announcements", tags: ["market-alert", "vaulted", "urgency"], estimatedViews: 670000, savedBy: "Merle", isCompetitor: true, sourceAccount: "@popmarkets", createdAt: "2026-03-10" },
    { id: "sw-6", url: "https://tiktok.com/@competitor/video/6", platform: "tiktok", hookText: "Gift idea under €20 that doesn't suck", hookType: "statement", format: "unboxing", niche: "gift", whyItWorks: "Universal pain point + price anchor + personality", tags: ["gift", "price", "personality"], estimatedViews: 510000, savedBy: "Merle", isCompetitor: false, sourceAccount: "@giftfinds", createdAt: "2026-03-08" },
  ];

  const byHookType: Record<string, number> = {};
  const byFormat: Record<string, number> = {};
  for (const e of entries) {
    byHookType[e.hookType] = (byHookType[e.hookType] || 0) + 1;
    byFormat[e.format] = (byFormat[e.format] || 0) + 1;
  }

  return { entries, byHookType, byFormat, totalEntries: entries.length };
}

export async function fetchSwipeFileData(): Promise<SwipeFileData> {
  clearDemo("swipe");
  if (!isSupabaseConfigured()) {
    return noteDemoSource("swipe", "Supabase is not configured", getDemoSwipeData());
  }
  const sb = getSupabase();
  if (!sb) return noteDemoSource("swipe", "no Supabase client", getDemoSwipeData());

  const { data, error } = await sb
    .from("ugc_swipe_file").select("*").order("created_at", { ascending: false });

  if (error) {
    return noteDemoSource(
      "swipe",
      error.code === "42P01"
        ? "swipe file unavailable — ugc_swipe_file is not provisioned (005_swipefile_accounts_sparkads.sql)"
        : `ugc_swipe_file unreadable (${error.code}: ${error.message})`,
      getDemoSwipeData(),
    );
  }
  if (!data || data.length === 0) {
    return noteDemoSource("swipe", "swipe file is empty — showing sample entries", getDemoSwipeData());
  }

  const entries: SwipeFileEntry[] = data.map((r: Record<string, unknown>) => ({
    id: r.id as string,
    url: (r.url as string) ?? "",
    platform: (r.platform as string) ?? "tiktok",
    hookText: (r.hook_text as string) ?? "",
    hookType: (r.hook_type as string) ?? "",
    format: (r.format as string) ?? "",
    niche: (r.niche as string) ?? "",
    whyItWorks: (r.why_it_works as string) ?? "",
    tags: (r.tags as string[]) ?? [],
    estimatedViews: (r.estimated_views as number) ?? 0,
    savedBy: (r.saved_by as string) ?? "",
    isCompetitor: (r.is_competitor as boolean) ?? false,
    sourceAccount: (r.source_account as string) ?? "",
    createdAt: (r.created_at as string) ?? "",
  }));

  const byHookType: Record<string, number> = {};
  const byFormat: Record<string, number> = {};
  for (const e of entries) {
    byHookType[e.hookType] = (byHookType[e.hookType] || 0) + 1;
    byFormat[e.format] = (byFormat[e.format] || 0) + 1;
  }

  return { entries, byHookType, byFormat, totalEntries: entries.length };
}

// ─── Account Analytics Fetch ────────────────────────────────────────────────

// Default account metadata — used only for the demo path. Real account
// metadata comes from the ugc_accounts table (see fetchAccountAnalytics).
const DEMO_ACCOUNT_LANG: Record<string, string> = {
  "@collectai.eu": "EN", "@collectai.de": "DE", "@collectai.fr": "FR",
  "@collectai.nl": "NL", "@collectai.es": "ES", "@collectai.it": "IT",
};
const DEMO_ACCOUNT_FOLLOWERS: Record<string, number> = {
  "@collectai.eu": 12400, "@collectai.de": 8900, "@collectai.fr": 7200,
  "@collectai.nl": 4500, "@collectai.es": 3100, "@collectai.it": 2800,
};

/**
 * Aggregate per-account analytics from a set of videos. Pure: `meta` supplies
 * each account's language and follower count (from ugc_accounts for real data,
 * or the demo maps above). Performance metrics are computed from the videos.
 */
function computeAccountAnalytics(
  videos: UGCVideo[],
  meta: Record<string, { language: string; followers: number }>,
): AccountAnalytics {
  const accountMap: Record<string, UGCVideo[]> = {};
  for (const v of videos) {
    if (!accountMap[v.accountId]) accountMap[v.accountId] = [];
    accountMap[v.accountId].push(v);
  }

  const langMap: Record<string, string> = {};
  const followerMap: Record<string, number> = {};
  for (const [handle, m] of Object.entries(meta)) {
    langMap[handle] = m.language;
    followerMap[handle] = m.followers;
  }

  const accounts: TikTokAccount[] = Object.entries(accountMap).map(([handle, vids]) => {
    const totalViews = vids.reduce((s, v) => s + v.viewsTotal, 0);
    const hits = vids.filter((v) => v.classification === "hit").length;
    const formatCounts: Record<string, { views: number; count: number }> = {};
    const hookCounts: Record<string, { views: number; count: number }> = {};
    for (const v of vids) {
      if (!formatCounts[v.format]) formatCounts[v.format] = { views: 0, count: 0 };
      formatCounts[v.format].views += v.viewsTotal;
      formatCounts[v.format].count++;
      if (!hookCounts[v.hookType]) hookCounts[v.hookType] = { views: 0, count: 0 };
      hookCounts[v.hookType].views += v.viewsTotal;
      hookCounts[v.hookType].count++;
    }
    const bestFormat = Object.entries(formatCounts).sort((a, b) => (b[1].views / b[1].count) - (a[1].views / a[1].count))[0]?.[0] ?? "";
    const bestHook = Object.entries(hookCounts).sort((a, b) => (b[1].views / b[1].count) - (a[1].views / a[1].count))[0]?.[0] ?? "";
    const totalEng = vids.reduce((s, v) => s + v.likes + v.comments + v.shares, 0);

    return {
      id: handle,
      handle,
      platform: "tiktok",
      language: langMap[handle] ?? "EN",
      description: `${langMap[handle] ?? "EN"} market account`,
      followers: followerMap[handle] ?? 1000,
      isActive: true,
      totalVideos: vids.length,
      totalViews,
      avgViews: vids.length > 0 ? Math.round(totalViews / vids.length) : 0,
      hitRate: vids.length > 0 ? Math.round((hits / vids.length) * 100) : 0,
      bestFormat,
      bestHookType: bestHook,
      engagementRate: totalViews > 0 ? Math.round((totalEng / totalViews) * 10000) / 10000 : 0,
    };
  }).sort((a, b) => b.totalViews - a.totalViews);

  // Format comparison across accounts
  const formatComparison: Record<string, Record<string, { videos: number; avgViews: number }>> = {};
  for (const acc of accounts) {
    const vids = accountMap[acc.handle];
    const fmts: Record<string, { total: number; count: number }> = {};
    for (const v of vids) {
      if (!fmts[v.format]) fmts[v.format] = { total: 0, count: 0 };
      fmts[v.format].total += v.viewsTotal;
      fmts[v.format].count++;
    }
    formatComparison[acc.handle] = {};
    for (const [fmt, data] of Object.entries(fmts)) {
      formatComparison[acc.handle][fmt] = { videos: data.count, avgViews: Math.round(data.total / data.count) };
    }
  }

  const best = accounts[0]?.handle ?? "";

  return {
    accounts,
    totalAccounts: accounts.length,
    totalFollowers: accounts.reduce((s, a) => s + a.followers, 0),
    bestPerformingAccount: best,
    formatComparison,
  };
}

/** Demo path: aggregate demo videos with the hardcoded account metadata. */
function getDemoAccountData(videos: UGCVideo[]): AccountAnalytics {
  const meta: Record<string, { language: string; followers: number }> = {};
  for (const handle of new Set(videos.map((v) => v.accountId))) {
    meta[handle] = {
      language: DEMO_ACCOUNT_LANG[handle] ?? "EN",
      followers: DEMO_ACCOUNT_FOLLOWERS[handle] ?? 1000,
    };
  }
  return computeAccountAnalytics(videos, meta);
}

export async function fetchAccountAnalytics(videos: UGCVideo[]): Promise<AccountAnalytics> {
  const sb = getSupabase();
  if (!sb) return noteDemoSource("accounts", "no Supabase client", getDemoAccountData(videos));

  // Real account metadata (handle, language, followers) from ugc_accounts;
  // performance is aggregated from the videos already fetched for this period.
  const { data: accts, error } = await sb
    .from("ugc_accounts")
    .select("handle, language, followers")
    .eq("is_active", true);

  if (error) {
    return noteDemoSource(
      "accounts",
      error.code === "42P01"
        ? "ugc_accounts not provisioned (005_swipefile_accounts_sparkads.sql)"
        : `ugc_accounts unreadable (${error.code}: ${error.message})`,
      getDemoAccountData(videos),
    );
  }
  if (!accts || accts.length === 0) {
    return noteDemoSource("accounts", "no accounts in ugc_accounts — showing sample data",
      getDemoAccountData(videos));
  }

  const meta: Record<string, { language: string; followers: number }> = {};
  for (const a of accts as { handle: string; language: string; followers: number }[]) {
    meta[a.handle] = { language: (a.language || "EN").toUpperCase(), followers: a.followers ?? 0 };
  }
  // Real accounts exist → this is live data for the tab.
  clearDemo("accounts");
  return computeAccountAnalytics(videos, meta);
}

// ─── Boost Metrics Fetch ────────────────────────────────────────────────────

function getDemoBoostData(videos: UGCVideo[]): BoostMetrics {
  // Mark top 5 videos as "boosted" for demo
  const sorted = [...videos].sort((a, b) => b.viewsTotal - a.viewsTotal);
  const boosted = sorted.slice(0, 5).map((v) => {
    const spend = Math.round(Math.random() * 5000 + 1000);
    const boostedViews = Math.round(v.viewsTotal * (1.5 + Math.random()));
    const boostedClicks = Math.round(boostedViews * 0.02);
    const boostedInstalls = Math.round(boostedClicks * 0.15);
    const revenue = v.revenueCents + Math.round(boostedInstalls * 800);
    return {
      videoId: v.videoId,
      hookText: v.hookText,
      organicViews: v.viewsTotal,
      boostedViews,
      spend: spend / 100,
      installs: boostedInstalls,
      revenue: revenue / 100,
      roas: spend > 0 ? Math.round((revenue / spend) * 100) / 100 : 0,
    };
  });

  const totalSpend = boosted.reduce((s, b) => s + b.spend, 0);
  const totalBoostedViews = boosted.reduce((s, b) => s + b.boostedViews, 0);
  const totalBoostedClicks = boosted.reduce((s, b) => s + b.installs * 6, 0);
  const totalBoostedInstalls = boosted.reduce((s, b) => s + b.installs, 0);
  const totalBoostedRevenue = boosted.reduce((s, b) => s + b.revenue, 0);

  const organicRevenue = videos.reduce((s, v) => s + v.revenueCents, 0) / 100;
  const organicCost = videos.reduce((s, v) => s + v.costCents, 0) / 100;

  return {
    totalBoosted: boosted.length,
    totalSpend,
    totalBoostedViews,
    totalBoostedClicks,
    totalBoostedInstalls,
    avgCPM: totalBoostedViews > 0 ? Math.round((totalSpend / totalBoostedViews * 1000) * 100) / 100 : 0,
    avgCPC: totalBoostedClicks > 0 ? Math.round((totalSpend / totalBoostedClicks) * 100) / 100 : 0,
    avgCPI: totalBoostedInstalls > 0 ? Math.round((totalSpend / totalBoostedInstalls) * 100) / 100 : 0,
    organicROI: organicCost > 0 ? Math.round((organicRevenue / organicCost) * 100) / 100 : 0,
    boostedROI: totalSpend > 0 ? Math.round((totalBoostedRevenue / totalSpend) * 100) / 100 : 0,
    boostedVideos: boosted,
  };
}

export async function fetchBoostMetrics(videos: UGCVideo[]): Promise<BoostMetrics> {
  const sb = getSupabase();
  if (!sb) return noteDemoSource("boost", "no Supabase client", getDemoBoostData(videos));

  // Real Spark Ads spend lives in the boost_* columns on ugc_videos (added by
  // migration 005). These are NOT mapped onto UGCVideo, so query them directly.
  const { data: rows, error } = await sb
    .from("ugc_videos")
    .select("video_id, hook_text, views_total, revenue_cents, cost_cents, is_boosted, boost_spend_cents, boost_views, boost_clicks, boost_installs")
    .eq("is_boosted", true);

  if (error) {
    return noteDemoSource(
      "boost",
      error.code === "42P01"
        ? "ugc_videos not provisioned (003_ugc_video_tracking.sql)"
        : `ugc_videos unreadable (${error.code}: ${error.message})`,
      getDemoBoostData(videos),
    );
  }
  if (!rows || rows.length === 0) {
    return noteDemoSource("boost", "no boosted videos yet — showing sample data",
      getDemoBoostData(videos));
  }

  type BoostRow = {
    video_id: string; hook_text: string; views_total: number; revenue_cents: number;
    cost_cents: number; boost_spend_cents: number; boost_views: number;
    boost_clicks: number; boost_installs: number;
  };
  const boosted = (rows as BoostRow[]).map((r) => {
    const spend = (r.boost_spend_cents ?? 0) / 100;
    const revenue = (r.revenue_cents ?? 0) / 100;
    return {
      videoId: r.video_id,
      hookText: r.hook_text ?? "",
      organicViews: r.views_total ?? 0,
      boostedViews: r.boost_views ?? 0,
      spend,
      installs: r.boost_installs ?? 0,
      revenue,
      roas: spend > 0 ? Math.round((revenue / spend) * 100) / 100 : 0,
    };
  });

  const totalSpend = boosted.reduce((s, b) => s + b.spend, 0);
  const totalBoostedViews = boosted.reduce((s, b) => s + b.boostedViews, 0);
  const totalBoostedClicks = (rows as BoostRow[]).reduce((s, r) => s + (r.boost_clicks ?? 0), 0);
  const totalBoostedInstalls = boosted.reduce((s, b) => s + b.installs, 0);
  const totalBoostedRevenue = boosted.reduce((s, b) => s + b.revenue, 0);
  const organicRevenue = videos.reduce((s, v) => s + v.revenueCents, 0) / 100;
  const organicCost = videos.reduce((s, v) => s + v.costCents, 0) / 100;

  clearDemo("boost");
  return {
    totalBoosted: boosted.length,
    totalSpend: Math.round(totalSpend * 100) / 100,
    totalBoostedViews,
    totalBoostedClicks,
    totalBoostedInstalls,
    avgCPM: totalBoostedViews > 0 ? Math.round((totalSpend / totalBoostedViews * 1000) * 100) / 100 : 0,
    avgCPC: totalBoostedClicks > 0 ? Math.round((totalSpend / totalBoostedClicks) * 100) / 100 : 0,
    avgCPI: totalBoostedInstalls > 0 ? Math.round((totalSpend / totalBoostedInstalls) * 100) / 100 : 0,
    organicROI: organicCost > 0 ? Math.round((organicRevenue / organicCost) * 100) / 100 : 0,
    boostedROI: totalSpend > 0 ? Math.round((totalBoostedRevenue / totalSpend) * 100) / 100 : 0,
    boostedVideos: boosted,
  };
}

// ─── UGC CSV Export ─────────────────────────────────────────────────────────

export function exportUGCVideosCSV(videos: UGCVideo[]): string {
  const headers = [
    "Video ID", "Account", "Creator", "Date", "Format", "Hook", "Hook Type",
    "Concept", "Views (2h)", "Views (12h)", "Views (24h)", "Views Total",
    "Hook Retention", "Avg Watch Time", "Completion Rate",
    "Likes", "Comments", "Shares", "Saves",
    "Clicks", "Installs", "Revenue (EUR)", "Classification", "Cost (EUR)",
  ];
  const rows = videos.map((v) => [
    v.videoId, v.accountId, v.creatorName, v.datePosted, v.format, `"${v.hookText}"`, v.hookType,
    v.conceptCluster, v.views2h, v.views12h, v.views24h, v.viewsTotal,
    v.hookRetentionRate, v.avgWatchTime, v.completionRate,
    v.likes, v.comments, v.shares, v.saves,
    v.clicks, v.installs, v.revenueCents / 100, v.classification, v.costCents / 100,
  ]);
  return [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
}

export function exportCreatorsCSV(creators: CreatorRow[]): string {
  const headers = [
    "Rank",
    "Name",
    "Handle",
    "Language",
    "Code",
    "Scans",
    "Activations",
    "Completions",
    "Orders",
    "Revenue (EUR)",
    "Conv %",
    "Net ROI (EUR)",
  ];

  const rows = creators.map((c, i) => [
    i + 1,
    c.name,
    c.handle,
    c.language,
    c.affiliateCode,
    c.scans,
    c.activations,
    c.completions,
    c.purchases,
    c.revenue,
    c.conversionRate,
    c.netROI,
  ]);

  return [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
}
