/**
 * Portfolio Analytics Screen — Pro-grade analytics dashboard
 *
 * Features:
 * - P/L summary with max drawdown
 * - Portfolio tier badge (Diamond/Gold/Silver)
 * - Category allocations visualization
 * - Winners & losers section
 * - Full items breakdown
 */

import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { BRAND_COLORS } from '@/constants/colors';
import React, { useState, useMemo, useCallback, useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Animated,
  RefreshControl,
} from "react-native";
import { Stack, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useAppTheme } from "@/hooks/useAppTheme";
import { SkeletonList } from "@/components/Skeleton";
import { useHasEverHadItems } from "@/hooks/useHasEverHadItems";
import {
  mapRiskNotes,
  type PortfolioRiskNote,
  type RawPersonalizedInsights,
} from "@/data/personalizedInsights";
import { ItemsEmptyState } from "@/components/items";
import { splitPortfolioByValueSource } from '@/lib/portfolioAnalytics';
import { formatPrice } from "@/lib/format";
import { QuickNavBar } from "@/components/QuickNavBar";
import { useAsync } from "@/hooks/useAsync";
import { useBillingLimits } from "@/hooks/useBillingLimits";
import { UpgradePrompt } from "@/components/UpgradePrompt";

// Import analytics store
import {
  fetchPortfolioSnapshot,
} from "@/store/portfolioAnalyticsStore";
import type { PortfolioSnapshot } from "@/analytics/portfolioMetrics";
import { dataProvider } from "@/data";
import type { CategorySummary } from "@/data/types";
import { collectorsApi } from "@/api/collectorsApi";
import logger from "@/utils/logger";
import { radius, spacing, text, fontWeight, shadow } from '@/theme/tokens';
import { CategoryPerformanceSection } from '@/components/CategoryPerformanceSection';
import { PortfolioTierBadge } from '@/components/analytics/PortfolioTierBadge';
import { PredictionAccuracySection } from '@/components/analytics/PredictionAccuracySection';
import { DemandHeatSection } from '@/components/home/DemandHeatSection';

// ─────────────────────────────────────────────────────────────────────────────
// Tier-specific tokens (not theme-dependent)
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Formatting helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatPct(p: number, includeSign = true): string {
  const sign = includeSign && p > 0 ? "+" : "";
  return `${sign}${(p * 100).toFixed(2)}%`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

function AnalyticsScreen() {
  const router = useRouter();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { colors } = useAppTheme();
  const themeColors = useMemo(() => ({
    background: colors.card,
    text: colors.text,
    muted: colors.muted,
    border: colors.border,
    accent: colors.accent,
    success: colors.success,
    danger: colors.danger,
  }), [colors]);
  const { limits, isForced } = useBillingLimits();
  const [refreshing, setRefreshing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const { hasEverHadItems, markHasItems } = useHasEverHadItems();

  // Concentration-risk warnings + diversification tips from
  // /insights/personalized. Previously the ONLY caller of that endpoint was a
  // marketplace effect that wrote to state nothing rendered (the trending rail
  // it fed was removed), so all four of its arrays were computed and thrown
  // away. Mapped through a pure seam fn — see src/data/personalizedInsights.ts.
  const [riskNotes, setRiskNotes] = useState<PortfolioRiskNote[]>([]);
  const [predictionAccuracy, setPredictionAccuracy] = useState<{ category: string; mae: number; mape: number; r2: number }[] | null>(null);
  // `avg_value` removed 2026-08-10 — the server counted unpriced items as EUR 0
  // in the denominator. Replaced by median + spread; null means nothing in the
  // category is priced. See server/app/routes/portfolio_router.py.
  const [categoryStats, setCategoryStats] = useState<{ category: string; item_count: number; priced_count: number; total_value: number; median_value: number | null; min_item_value: number | null; max_item_value: number | null; change_7d: number; change_7d_pct: number; trend: string }[]>([]);
  const [categoryHealth, setCategoryHealth] = useState<{ category: string; volatility: number; trend_strength: number; health: string }[]>([]);

  // Split fetches so a single endpoint failure doesn't blank the whole screen
  // (previously Promise.all short-circuited — if either snapshot or categories
  // threw, paid users saw "analytics fetch failed" with no diagnostic).
  const {
    data: snapshotData,
    loading: snapshotLoading,
    error: snapshotError,
    retry: retrySnapshot,
  } = useAsync(() => fetchPortfolioSnapshot(), []);

  const {
    data: categoryData,
    loading: categoriesLoading,
    error: categoryError,
    retry: retryCategories,
  } = useAsync(() => dataProvider.listCategorySummaries(), []);

  const loading = snapshotLoading || categoriesLoading;
  const errMsg = (e: unknown): string => {
    if (!e) return '';
    if (typeof e === 'string') return e;
    if (e instanceof Error) return e.message;
    return String(e);
  };
  const errorParts: string[] = [];
  if (snapshotError) errorParts.push(`snapshot: ${errMsg(snapshotError)}`);
  if (categoryError) errorParts.push(`categories: ${errMsg(categoryError)}`);
  const error = errorParts.length ? errorParts.join(' · ') : null;
  const retry = useCallback(async () => {
    await Promise.all([retrySnapshot(), retryCategories()]);
  }, [retrySnapshot, retryCategories]);
  const analyticsData = useMemo(
    () => ({ snapshot: snapshotData, categorySummaries: categoryData ?? [] }),
    [snapshotData, categoryData],
  );

  // Fetch personalized insights + prediction accuracy (enrichment) — parallelized
  //
  // getCollectionTrends(30) used to lead this list. It was dropped 2026-07-24:
  // its three payloads were each already on this screen from another source —
  // total_history duplicates the Home portfolio chart, dca_history duplicates
  // the Cost Basis Summary card below, and per_category_gain_loss duplicates
  // categoryStats.change_7d_pct. Its result was stored in state nothing read,
  // so it cost three DB queries per screen open and rendered nothing.
  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      collectorsApi.fetchInsights(),
      collectorsApi.getPredictionAccuracy(),
      collectorsApi.getPortfolioCategoryStats(),
      collectorsApi.getCategoryHealth(),
    ]).then(([insightsResult, accuracyResult, statsResult, healthResult]) => {
      if (cancelled) return;
      if (insightsResult.status === 'fulfilled' && insightsResult.value) {
        setRiskNotes(mapRiskNotes(insightsResult.value as RawPersonalizedInsights));
      } else if (insightsResult.status === 'rejected') {
        logger.warn('[Analytics] personalized insights fetch failed:', insightsResult.reason);
      }
      if (accuracyResult.status === 'fulfilled') {
        const data = accuracyResult.value as { categories?: { category: string; mae: number; mape: number; r2: number }[] } | undefined;
        if (Array.isArray(data?.categories)) setPredictionAccuracy(data!.categories);
      } else {
        logger.warn('[Analytics] prediction accuracy fetch failed:', accuracyResult.reason);
      }
      if (statsResult.status === 'fulfilled') {
        const data = statsResult.value as { categories?: typeof categoryStats } | undefined;
        if (Array.isArray(data?.categories)) setCategoryStats(data!.categories);
      } else {
        logger.warn('[Analytics] category stats fetch failed:', statsResult.reason);
      }
      if (healthResult.status === 'fulfilled') {
        const data = healthResult.value as { health?: typeof categoryHealth } | undefined;
        if (Array.isArray(data?.health)) setCategoryHealth(data!.health);
      } else {
        logger.warn('[Analytics] category health fetch failed:', healthResult.reason);
      }
    });
    return () => { cancelled = true; };
  }, [refreshKey]);

  const snapshot = analyticsData?.snapshot ?? null;
  const categorySummaries = analyticsData?.categorySummaries ?? [];

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    setRefreshKey((k) => k + 1);
    await retry();
    setRefreshing(false);
  }, [retry]);

  // Mock snapshot used ONLY when plan is dev-forced AND real fetch returned
  // nothing useful (common on web dev with no real user items). Lets the
  // design team preview Pro-tier layout end-to-end. Real users with a real
  // paid plan never see this path — they see their own data.
  // Typed as `PortfolioSnapshot` via `as any` cast because constructing the
  // full schema (every field, every nested type) is expensive for sample
  // data that never leaves dev mode.
  const MOCK_SNAPSHOT = useMemo<PortfolioSnapshot>(
    () => ({
      pl: {
        startValue: 3200,
        currentValue: 4680,
        deltaAbs: 1480,
        deltaPct: 0.4625,
        maxDrawdownPct: -0.08,
      },
      allocations: [
        { category: 'Pokemon',      totalValue: 2340, weight: 0.50 },
        { category: 'LEGO',         totalValue: 1100, weight: 0.24 },
        { category: 'Hot Toys',     totalValue:  620, weight: 0.13 },
        { category: 'Warhammer',    totalValue:  380, weight: 0.08 },
        { category: 'Vinyl Records', totalValue: 240, weight: 0.05 },
      ],
      winnersLosers: {
        winners: [
          { id: 'm1', name: 'Charizard VMAX SWSH07', category: 'Pokemon', currentValue: 218, change7dPct: 0.18 },
          { id: 'm2', name: 'LEGO Millennium Falcon 75192', category: 'LEGO', currentValue: 910, change7dPct: 0.11 },
        ],
        losers: [
          { id: 'm3', name: 'Funko Batman Dorbz', category: 'Funko', currentValue: 24, change7dPct: -0.22 },
        ],
        neutral: [],
      },
      tierSummary: { tier: 'Gold', totalScore: 78, rarityScore: 72, completenessScore: 81, diversificationScore: 82 },
      items: [
        { id: 'm1', name: 'Charizard VMAX SWSH07', category: 'Pokemon',  currentValue: 218, change1dPct: 0.02, change7dPct: 0.18, quantity: 1 },
        { id: 'm2', name: 'LEGO Millennium Falcon 75192', category: 'LEGO',  currentValue: 910, change1dPct: 0.00, change7dPct: 0.11, quantity: 1 },
        { id: 'm3', name: 'Hot Toys Iron Man MK85',  category: 'Hot Toys', currentValue: 520, change1dPct: 0.01, change7dPct: 0.05, quantity: 1 },
        { id: 'm4', name: 'Warhammer Space Marines box', category: 'Warhammer', currentValue: 120, change1dPct: -0.01, change7dPct: 0.02, quantity: 1 },
        { id: 'm5', name: "Thriller (MJ) Vinyl", category: 'Vinyl Records', currentValue: 80, change1dPct: 0.00, change7dPct: 0.00, quantity: 1 },
        { id: 'm6', name: 'Funko Batman Dorbz', category: 'Funko', currentValue: 24, change1dPct: -0.03, change7dPct: -0.22, quantity: 1 },
      ],
      series: [],
    } as unknown as PortfolioSnapshot),
    [],
  );

  const MOCK_CATEGORIES = useMemo(
    () => [
      { id: 'pokemon',  name: 'Pokemon',  ownedCount: 47, totalCount: 185, completionPct: 25 },
      { id: 'lego',     name: 'LEGO',     ownedCount: 12, totalCount:  60, completionPct: 20 },
      { id: 'hot_toys', name: 'Hot Toys', ownedCount:  8, totalCount:  40, completionPct: 20 },
    ],
    [],
  );

  // When dev plan is forced AND real snapshot produced no useful data, swap
  // in MOCK_SNAPSHOT so the Pro-tier Analytics layout renders end-to-end.
  // Gated behind __DEV__ so a stale AsyncStorage force_plan value can never
  // leak fake Pokemon/LEGO/Hot Toys data into a production TestFlight build.
  const effectiveSnapshot = useMemo(() => {
    const real = snapshot;
    const realHasData = real && ((real.items?.length ?? 0) > 0 || real.pl);
    if (__DEV__ && isForced && !realHasData) return MOCK_SNAPSHOT;
    return real;
  }, [snapshot, isForced, MOCK_SNAPSHOT]);

  const effectiveCategories = useMemo(() => {
    if (__DEV__ && isForced && (!categorySummaries || categorySummaries.length === 0)) {
      return MOCK_CATEGORIES;
    }
    return categorySummaries;
  }, [categorySummaries, isForced, MOCK_CATEGORIES]);

  // Show the preview banner whenever sample/mock data is on screen, even if
  // the user isn't on a forced plan. Previously gated on `isForced`, which
  // meant real users seeing the mock fallback (empty portfolio in dev) had no
  // visual cue that the numbers weren't theirs.
  const isPreview = effectiveSnapshot === MOCK_SNAPSHOT;

  // M4: Memoize derived snapshot data to avoid recomputing on every render
  const { pl, allocations, tierSummary, items } = useMemo(() => effectiveSnapshot ?? {
    pl: null,
    allocations: [],
    winnersLosers: { winners: [], losers: [], neutral: [] },
    tierSummary: null,
    items: [],
  }, [effectiveSnapshot]);

  const isPositive = useMemo(() => (pl?.deltaPct ?? 0) >= 0, [pl?.deltaPct]);

  // How many holdings have a real purchase price behind their P/L. See the
  // note on the Performance card: without one the server uses the earliest
  // prediction as cost basis, so the "gain" is model drift.
  const pricedCount = useMemo(
    () => items.filter((i) => i.hasPurchasePrice).length,
    [items],
  );

  /**
   * The three numbers a collection actually has (decided 2026-08-19).
   *
   * They are not three versions of one figure: what you PAID is a fact about
   * your past, what the MARKET says is a claim we can back with comps, and an
   * ESTIMATE is somebody's opinion — the member's own, or a vision scan's.
   * Presenting the third as the second is what this whole change exists to
   * stop, and collapsing the first two is how `unrealized_pl` came to measure
   * model drift instead of profit.
   */
  const valueSplit = useMemo(() => splitPortfolioByValueSource(items), [items]);

  /**
   * Split the personalized-insights notes into the two things they actually
   * are, because rendering them as one list said the same fact twice.
   *
   * `concentration` — the note carrying a share + level. Its NUMBER duplicates
   * the Allocations bar, so only its level and category are used, inline in
   * that card.
   * `actionableNotes` — the rest: suggestions that tell you to do something.
   *
   * A suggestion naming "uncategorized" is dropped. That bucket is items with
   * a NULL category, so "grow your uncategorized collection" is advice to buy
   * more of a non-category — it read as a bug because it is one.
   */
  const concentration = useMemo(
    () => riskNotes.find((n) => n.sharePct != null && n.category) ?? null,
    [riskNotes],
  );
  const actionableNotes = useMemo(
    () =>
      riskNotes.filter(
        (n) =>
          n.sharePct == null &&
          !/uncategori[sz]ed/i.test(n.text),
      ),
    [riskNotes],
  );

  // Category colors for allocation bars
  const categoryColors = useMemo(() => {
    const colors = [BRAND_COLORS.tiffany, BRAND_COLORS.tiffanyDark, "#44A9A1", "#2D8A84", "#1F6B66"];
    const map: Record<string, string> = {};
    allocations.forEach((a, i) => {
      map[a.category] = colors[i % colors.length];
    });
    return map;
  }, [allocations]);

  // Categories with owned items, sorted by completionPct desc
  const activeCategories = useMemo(() => {
    return effectiveCategories
      .filter((c) => c.ownedCount > 0)
      .sort((a, b) => b.completionPct - a.completionPct);
  }, [effectiveCategories]);

  // Flip the persistent flag once we know the user actually has items.
  useEffect(() => {
    const itemCount = effectiveSnapshot?.items?.length ?? 0;
    if (itemCount > 0 && !isPreview) markHasItems();
  }, [effectiveSnapshot, isPreview, markHasItems]);

  if (loading) {
    // First-run users skip the skeleton entirely and see the hero CTA so
    // they're prompted to add their first item instead of staring at grey
    // silhouettes. Returning users (hasEverHadItems === true) keep the
    // skeleton because real data is on its way.
    if (hasEverHadItems !== true) {
      return (
        <View style={[styles.safe, { backgroundColor: colors.background }]}>
          <Stack.Screen options={{ headerTitle: 'Analytics' }} />
          <View style={{ flex: 1, justifyContent: 'center' }}>
            <ItemsEmptyState />
          </View>
        </View>
      );
    }
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <Stack.Screen options={{ headerTitle: 'Analytics' }} />
        <View style={styles.loadingContainer}>
          <SkeletonList count={3} type="analytics" />
        </View>
      </View>
    );
  }

  // Loaded with no items: also short-circuit to the hero CTA.
  if (!isPreview && (effectiveSnapshot?.items?.length ?? 0) === 0) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <Stack.Screen options={{ headerTitle: 'Analytics' }} />
        <View style={{ flex: 1, justifyContent: 'center' }}>
          <ItemsEmptyState />
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: 'Analytics' }} />
      <ScrollView
        contentContainerStyle={styles.container}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      >
        <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>

        {/* ONE upgrade prompt for the whole screen.
            There used to be five — "Advanced Analytics", "Hot Right Now",
            "Category Performance", "Holdings Breakdown" and "Collection
            Completeness" — so a free member scrolled past five near-identical
            cards asking for the same upgrade to the same plan. Repetition does
            not add persuasion; it reads as a screen that is mostly advertising.
            The gated sections below now simply render nothing. */}
        {!limits.advanced_analytics && (
          <UpgradePrompt feature="Advanced Analytics" requiredPlan="Pro" />
        )}

        {/* Hot Right Now (moved from home 2026-04-18, Pro-gated) */}
        {limits.advanced_analytics ? <DemandHeatSection /> : null}

        {/* Preview banner when the dev plan override is active and we're
            falling back to mock analytics data (real fetch failed/empty). */}
        {isPreview && (
          <View style={[styles.errorBanner, { backgroundColor: colors.accent + '18' }]}>
            <Ionicons name="construct-outline" size={16} color={colors.accent} />
            <Text style={[styles.errorText, { color: colors.text }]}>
              Preview — these are sample numbers. Add items to your portfolio to see your real analytics.
            </Text>
          </View>
        )}

        {/* Error banner (suppressed in forced-plan preview mode — errors
            are noise when we're knowingly showing mock data). */}
        {error && !isPreview && (
          <View style={[styles.errorBanner, { backgroundColor: colors.dangerBg }]}>
            <Ionicons name="warning-outline" size={16} color={colors.error} />
            <Text style={[styles.errorText, { color: colors.danger }]}>{error}</Text>
            <AnimatedPressable
              onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); retry(); }}
              style={[styles.errorRetryBtn, { backgroundColor: colors.danger }]}
              accessibilityRole="button"
              accessibilityLabel="Retry loading analytics data"
            >
              <Ionicons name="refresh-outline" size={14} color="#fff" />
              <Text style={styles.errorRetryText}>Retry</Text>
            </AnimatedPressable>
          </View>
        )}

        {/* P/L Summary Card */}
        {pl && (
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.cardHeader}>
              <Text style={[styles.cardTitle, { color: colors.text }]}>Performance</Text>
              {/* No badge without a baseline. "0.00%" beside "+EUR 8,070"
                  was the card contradicting itself on a real account. */}
              {pl.hasBaseline ? (
                <View style={[styles.badge, { backgroundColor: isPositive ? colors.successBg : colors.dangerBg }]}>
                  <Text style={[styles.badgeText, { color: isPositive ? colors.success : colors.danger }]}>
                    {formatPct(pl.deltaPct)}
                  </Text>
                </View>
              ) : null}
            </View>

            {/* ONE explanation, once. This block was written three times over —
                same condition, same sentence in three near-identical wordings —
                and shipped as a card that says the same thing three times. If
                this needs rewording again, EDIT it; do not add another. */}
            {!pl.hasBaseline ? (
              <Text style={[styles.plBasis, { color: colors.muted }]}>
                Everything you own was added inside this window, so there is no
                earlier value to measure against yet. Performance appears once
                your portfolio has history behind it.
              </Text>
            ) : null}

            {/* The three numbers, before the P/L that compares two of them.
                Rendered only when there is something to split; a card of three
                zeroes on an empty account is chrome. */}
            {items.length > 0 ? (
              <View style={styles.metricsGrid}>
                <View style={styles.metricItem}>
                  <Text style={[styles.metricLabel, { color: colors.muted }]}>You paid</Text>
                  <Text style={[styles.metricValue, { color: colors.text }]}>
                    {valueSplit.purchaseCount > 0
                      ? formatPrice(valueSplit.purchaseTotal, settings.currency ?? 'EUR')
                      : '—'}
                  </Text>
                  <Text style={[styles.metricLabel, { color: colors.muted }]}>
                    {valueSplit.purchaseCount} of {items.length} items
                  </Text>
                </View>
                <View style={styles.metricItem}>
                  <Text style={[styles.metricLabel, { color: colors.muted }]}>Market value</Text>
                  <Text style={[styles.metricValue, { color: colors.text }]}>
                    {valueSplit.marketCount > 0
                      ? formatPrice(valueSplit.marketTotal, settings.currency ?? 'EUR')
                      : '—'}
                  </Text>
                  <Text style={[styles.metricLabel, { color: colors.muted }]}>
                    {valueSplit.marketCount} priced by comps
                  </Text>
                </View>
                <View style={styles.metricItem}>
                  <Text style={[styles.metricLabel, { color: colors.muted }]}>Estimated</Text>
                  <Text style={[styles.metricValueMuted, { color: colors.muted }]}>
                    {valueSplit.estimateCount > 0
                      ? formatPrice(valueSplit.estimateTotal, settings.currency ?? 'EUR')
                      : '—'}
                  </Text>
                  {/* Named as an estimate, not hidden. For the 40+ categories
                      with no sold-comp source this is the ONLY number a member
                      has, and dropping it would show them a collection worth
                      less than they know it is. */}
                  <Text style={[styles.metricLabel, { color: colors.muted }]}>
                    {valueSplit.estimateCount} not comp-backed
                  </Text>
                </View>
              </View>
            ) : null}

            {/* What the P/L above is actually BASED on.
                `cost_basis` falls back to the earliest prediction when an item
                has no purchase price, so its "profit" is really model drift —
                and it arrives as the same number, in the same field, looking
                identical. A trader reading a gain has to know how much of their
                portfolio it can possibly apply to. */}
            {items.length > 0 ? (
              <Text style={[styles.plBasis, { color: colors.muted }]}>
                {pricedCount === items.length
                  ? `Based on what you paid for all ${items.length} items.`
                  : pricedCount === 0
                    ? `No purchase prices on file, so this tracks how our valuation has moved — not profit. Add what you paid to track that.`
                    : `Based on what you paid for ${pricedCount} of ${items.length} items. The other ${items.length - pricedCount} track our valuation instead.`}
              </Text>
            ) : null}

            <View style={styles.metricsGrid}>
              <View style={styles.metricItem}>
                <Text style={[styles.metricLabel, { color: colors.muted }]}>Current Value</Text>
                <Text style={[styles.metricValue, { color: colors.text }]}>{formatPrice(pl.currentValue, settings.currency ?? 'EUR')}</Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={[styles.metricLabel, { color: colors.muted }]}>Starting Value</Text>
                <Text style={[styles.metricValueMuted, { color: colors.muted }]}>
                  {pl.hasBaseline ? formatPrice(pl.startValue, settings.currency ?? 'EUR') : '—'}
                </Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={[styles.metricLabel, { color: colors.muted }]}>Total Gain/Loss</Text>
                <Text
                  style={[
                    styles.metricValue,
                    { color: pl.hasBaseline ? (isPositive ? colors.success : colors.danger) : colors.muted },
                  ]}
                >
                  {pl.hasBaseline
                    ? `${pl.deltaAbs >= 0 ? '+' : ''}${formatPrice(pl.deltaAbs, settings.currency ?? 'EUR')}`
                    : '—'}
                </Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={[styles.metricLabel, { color: colors.muted }]}>Max Drawdown</Text>
                {/* Same rule as Starting Value and Gain/Loss directly above: with
                    no earlier value there is no series to draw down FROM, and a
                    red 0.00% is a measured number rather than an absent one. */}
                <Text
                  style={[
                    styles.metricValue,
                    { color: pl.hasBaseline ? colors.danger : colors.muted },
                  ]}
                >
                  {pl.hasBaseline ? formatPct(pl.maxDrawdownPct, false) : '—'}
                </Text>
              </View>
            </View>
          </View>
        )}

        {/* Portfolio Tier Card */}
        {tierSummary && (
          <PortfolioTierBadge tierSummary={tierSummary} />
        )}

        {/* Category Allocations */}
        {allocations.length > 0 && (
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.cardHeader}>
              <Text style={[styles.cardTitle, { color: colors.text }]}>Allocations</Text>
              <Text style={[styles.cardSubtitle, { color: colors.muted }]}>{allocations.length} categories</Text>
            </View>

            {/* Allocation Bar */}
            <View style={styles.allocationBar}>
              {allocations.map((a) => (
                <View
                  key={a.category}
                  style={[
                    styles.allocationSegment,
                    {
                      flex: a.weight,
                      backgroundColor: categoryColors[a.category],
                    },
                  ]}
                />
              ))}
            </View>

            {/* Allocation List */}
            <View style={styles.allocationList}>
              {allocations.slice(0, 6).map((a) => (
                <View key={a.category} style={styles.allocationRow}>
                  <View style={styles.allocationLeft}>
                    <View style={[styles.allocationDot, { backgroundColor: categoryColors[a.category] }]} />
                    <Text style={[styles.allocationName, { color: colors.text }]}>{a.category}</Text>
                  </View>
                  <View style={styles.allocationRight}>
                    <Text style={[styles.allocationValue, { color: colors.text }]}>{formatPrice(a.totalValue, settings.currency ?? 'EUR')}</Text>
                    <Text style={[styles.allocationPct, { color: colors.muted }]}>{formatPct(a.weight, false)}</Text>
                  </View>
                </View>
              ))}
            </View>

            {/* The concentration VERDICT, inside the card that shows the
                distribution — not a second card below it.

                "Concentration & Balance" used to be its own section and its
                lead line read "Your 'pokemon' exposure is 93% of your
                portfolio", directly under an allocation bar already showing
                pokemon at 93%. Reported as "seems like the exact same as
                allocations", and it was: the same fact, twice, adjacent. Only
                the RISK LEVEL was new information, so only that survives here.
                Rendered from `sharePct`/`level`, never from the server's
                sentence, so it cannot drift back into restating the number. */}
            {concentration && (
              <View style={[styles.concentrationRow, { borderTopColor: colors.border }]}>
                <View
                  style={[
                    styles.riskDot,
                    {
                      backgroundColor:
                        concentration.level === 'high'
                          ? colors.danger
                          : concentration.level === 'medium'
                            ? colors.accent
                            : colors.muted,
                    },
                  ]}
                />
                <Text style={[styles.concentrationText, { color: colors.muted }]}>
                  {concentration.level === 'high'
                    ? `High concentration — ${concentration.category} carries most of your value`
                    : concentration.level === 'medium'
                      ? `Moderately concentrated in ${concentration.category}`
                      : `Reasonably spread across ${allocations.length} categories`}
                </Text>
              </View>
            )}
          </View>
        )}

        {/* Diversification SUGGESTIONS only — the concentration figure itself
            now lives in the Allocations card above. */}
        {actionableNotes.length > 0 && (
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.cardHeader}>
              <Ionicons name="shield-outline" size={18} color={colors.accent} />
              <Text style={[styles.cardTitle, { color: colors.text }]}>Ways to balance it</Text>
            </View>
            {actionableNotes.map((note) => (
              <View key={note.id} style={styles.riskRow}>
                <View
                  style={[
                    styles.riskDot,
                    {
                      backgroundColor:
                        note.level === 'high'
                          ? colors.danger
                          : note.level === 'medium'
                            ? colors.accent
                            : colors.muted,
                    },
                  ]}
                />
                <Text style={[styles.riskText, { color: colors.text }]}>{note.text}</Text>
              </View>
            ))}
          </View>
        )}

        {/* H1: Category Statistics Dashboard (Pro+) */}
        {limits.advanced_analytics ? (
          <CategoryPerformanceSection categoryStats={categoryStats} categoryHealth={categoryHealth} />
        ) : null}

        {/* The "Movers" card was REMOVED here on 2026-08-14.
            It rendered per-item 24h winners and losers off `change1dPct` — and
            `/portfolio/items` has never returned `change_1d_pct`. Every item
            therefore mapped to undefined, `computeWinnersAndLosers` pushed all
            of them into `neutral`, winners and losers came back empty, and the
            component returned null. It has never drawn a single row.
            Verified against prod: the endpoint returns exactly category,
            cost_basis, current_value, id, name, q10, q90, unrealized_pl.
            Its job — what is moving and by how much — is already done properly
            by CategoryPerformanceSection directly above, on real 7d data with a
            trend direction and a median. Two cards for one question, one of
            which could never answer it. */}

        {/* Items Summary (Pro+) */}
        {limits.advanced_analytics && items.length > 0 && (
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.cardHeader}>
              <Text style={[styles.cardTitle, { color: colors.text }]}>Holdings</Text>
              <Text style={[styles.cardSubtitle, { color: colors.muted }]}>{items.length} {items.length === 1 ? 'item' : 'items'}</Text>
            </View>

            {items.slice(0, 8).map((item, idx) => (
              <View
                key={item.id}
                style={[styles.itemRow, { borderTopColor: colors.border }, idx === 0 && styles.itemRowFirst]}
              >
                <View style={styles.itemLeft}>
                  <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>{item.name}</Text>
                  <Text style={[styles.itemCategory, { color: colors.muted }]}>{item.category}</Text>
                </View>
                <View style={styles.itemRight}>
                  <Text style={[styles.itemValue, { color: colors.text }]}>{formatPrice(item.currentValue, settings.currency ?? 'EUR')}</Text>
                  {item.change1dPct !== undefined && (
                    <Text
                      style={[
                        styles.itemPct,
                        (item.change1dPct ?? 0) >= 0
                          ? { color: colors.success }
                          : { color: colors.danger },
                      ]}
                    >
                      {formatPct(item.change1dPct)}
                    </Text>
                  )}
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Collection Completeness (Pro+) */}
        {limits.advanced_analytics && activeCategories.length > 0 && (
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.cardHeader}>
              <Text style={[styles.cardTitle, { color: colors.text }]}>Collection Completeness</Text>
              <Text style={[styles.cardSubtitle, { color: colors.muted }]}>{activeCategories.length} categories</Text>
            </View>

            {activeCategories.slice(0, 8).map((cat) => {
              const displayPct = Math.min(cat.completionPct, 100);
              const hasDuplicates = cat.ownedCount > cat.totalCount;
              const barColor =
                displayPct >= 75 ? colors.success
                : displayPct >= 50 ? colors.warning
                : colors.accent;
              return (
                <View key={cat.id} style={styles.completenessRow}>
                  <View style={styles.completenessInfo}>
                    <Text style={[styles.completenessName, { color: colors.text }]} numberOfLines={1}>{cat.name}</Text>
                    <View style={styles.completenessCountRow}>
                      {hasDuplicates && (
                        <View style={[styles.dupBadge, { backgroundColor: colors.border }]}>
                          <Ionicons name="copy-outline" size={10} color={colors.muted} />
                          <Text style={[styles.dupBadgeText, { color: colors.muted }]}>dupes</Text>
                        </View>
                      )}
                      <Text style={[styles.completenessCount, { color: colors.muted }]}>
                        {cat.ownedCount}/{cat.totalCount}
                      </Text>
                    </View>
                  </View>
                  <View style={styles.completenessBarWrap}>
                    <View style={[styles.completenessBarBg, { backgroundColor: colors.border }]}>
                      <View
                        style={[
                          styles.completenessBarFill,
                          {
                            width: `${displayPct}%`,
                            backgroundColor: barColor,
                          },
                        ]}
                      />
                    </View>
                    <Text style={[styles.completenessPct, { color: colors.text }]}>
                      {displayPct}%
                    </Text>
                  </View>
                </View>
              );
            })}

            {activeCategories.length > 8 && (
              <AnimatedPressable
                style={[styles.viewAllBtn, { borderTopColor: colors.border }]}
                onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled }); router.push("/categories"); }}
                accessibilityRole="link"
                accessibilityLabel="View all categories"
              >
                <Text style={[styles.viewAllText, { color: colors.accent }]}>
                  View all
                </Text>
                <Ionicons name="chevron-forward" size={14} color={colors.accent} />
              </AnimatedPressable>
            )}
          </View>
        )}

        {/* ── M3: Cost Basis / DCA Overlay (Pro+) ── */}
        {limits.advanced_analytics && pl && (
          <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.cardHeader}>
              <Ionicons name="wallet-outline" size={18} color={colors.accent} />
              <Text style={[styles.cardTitle, { color: colors.text }]}>Cost Basis Summary</Text>
            </View>
            <View style={styles.dcaRow}>
              <View style={styles.dcaStat}>
                <Text style={[styles.dcaLabel, { color: colors.muted }]}>Total Invested</Text>
                <Text style={[styles.dcaValue, { color: colors.text }]}>
                  {formatPrice(pl.startValue, settings.currency ?? 'EUR')}
                </Text>
              </View>
              <View style={styles.dcaStat}>
                <Text style={[styles.dcaLabel, { color: colors.muted }]}>Current Value</Text>
                <Text style={[styles.dcaValue, { color: colors.text }]}>
                  {formatPrice(pl.currentValue, settings.currency ?? 'EUR')}
                </Text>
              </View>
              <View style={styles.dcaStat}>
                <Text style={[styles.dcaLabel, { color: colors.muted }]}>Unrealized P/L</Text>
                <Text style={[styles.dcaValue, { color: isPositive ? colors.success : colors.danger }]}>
                  {isPositive ? '+' : ''}{formatPrice(pl.deltaAbs, settings.currency ?? 'EUR')}
                </Text>
              </View>
            </View>
            {pl.startValue > 0 && (
              <View style={[styles.dcaBar, { backgroundColor: colors.border + '40' }]}>
                <View
                  style={[
                    styles.dcaBarFill,
                    {
                      backgroundColor: isPositive ? colors.success : colors.danger,
                      width: `${Math.min(100, Math.max(5, (pl.currentValue / pl.startValue) * 100))}%`,
                    },
                  ]}
                />
              </View>
            )}
          </View>
        )}

        {/* ── M4: Prediction Accuracy (Premium) ── */}
        {limits.advanced_analytics && predictionAccuracy && predictionAccuracy.length > 0 && (
          <PredictionAccuracySection data={predictionAccuracy} />
        )}

        {/* Bottom spacing */}
        <View style={{ height: 32 }} />
        </Animated.View>
      </ScrollView>
      <QuickNavBar />
    </View>
  );
}

export default function AnalyticsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Analytics">
      <AnalyticsScreen />
    </ScreenErrorBoundary>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  plBasis: { fontSize: 12, lineHeight: 17, marginBottom: 10 },
  safe: {
    flex: 1,
    // backgroundColor set inline via colors.background
  },
  container: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  loadingText: {
    marginTop: 12,
    // color set inline via colors.muted
    fontSize: text.md,
  },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 16,
  },
  backBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: -8,
  },
  headerText: {
    flex: 1,
    marginLeft: 4,
  },
  headerLabel: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
    // color set inline via colors.muted
    letterSpacing: 0.5,
  },
  headerTitle: {
    fontSize: text['2xl'],
    fontWeight: fontWeight.extrabold,
    // color set inline via colors.text
  },
  refreshBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },

  // Error
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    padding: 12,
    borderRadius: radius.md,
    marginBottom: 16,
  },
  errorText: {
    // color set inline via colors.danger
    fontSize: text.md,
    flex: 1,
  },
  errorRetryBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.sm,
    marginLeft: 8,
  },
  errorRetryText: {
    color: "#fff",
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
  },

  // Cards
  card: {
    // backgroundColor set inline via colors.card
    borderRadius: radius.md,
    borderWidth: 1,
    // borderColor set inline via colors.border
    padding: 16,
    marginBottom: 16,
    ...shadow.card,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
    // color set inline via colors.text
  },
  cardSubtitle: {
    fontSize: text.md,
    // color set inline via colors.muted
  },

  // Badge
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: radius.md,
  },
  badgeSuccess: {},
  badgeDanger: {},
  badgeText: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
  },
  badgeTextSuccess: {
    // color set inline via colors.success
  },
  badgeTextDanger: {
    // color set inline via colors.danger
  },

  // Metrics Grid
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  metricItem: {
    width: "50%",
    marginBottom: 16,
  },
  metricLabel: {
    fontSize: text.sm,
    // color set inline via colors.muted
    marginBottom: 4,
  },
  metricValue: {
    fontSize: text.xl,
    fontWeight: fontWeight.bold,
    // color set inline via colors.text
  },
  metricValueMuted: {
    fontSize: text.xl,
    fontWeight: fontWeight.bold,
    // color set inline via colors.muted
  },

  // Text colors
  textSuccess: {
    // color set inline via colors.success
  },
  textDanger: {
    // color set inline via colors.danger
  },

  // Allocations
  allocationBar: {
    flexDirection: "row",
    height: 8,
    borderRadius: radius.xs,
    overflow: "hidden",
    marginBottom: 16,
  },
  allocationSegment: {
    minWidth: 4,
  },
  allocationList: {
    gap: 12,
  },
  allocationRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  allocationLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  allocationDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 10,
  },
  allocationName: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    // color set inline via colors.text
  },
  allocationRight: {
    alignItems: "flex-end",
  },
  allocationValue: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
    // color set inline via colors.text
  },
  allocationPct: {
    fontSize: text.sm,
    // color set inline via colors.muted
  },

  // Items
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 12,
    borderTopWidth: 1,
    // borderTopColor set inline via colors.border
  },
  itemRowFirst: {
    borderTopWidth: 0,
  },
  itemLeft: {
    flex: 1,
    marginRight: 12,
  },
  itemName: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    // color set inline via colors.text
  },
  itemCategory: {
    fontSize: text.sm,
    // color set inline via colors.muted
    marginTop: 2,
  },
  itemRight: {
    alignItems: "flex-end",
  },
  itemValue: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
    // color set inline via colors.text
  },
  itemPct: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
    marginTop: 2,
  },

  // Completeness
  completenessRow: {
    marginBottom: 12,
  },
  completenessInfo: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  completenessName: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    // color set inline via colors.text
    flex: 1,
    marginRight: 8,
  },
  completenessCountRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  completenessCount: {
    fontSize: text.sm,
    // color set inline via colors.muted
  },
  dupBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    // backgroundColor set inline via colors.border
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderRadius: radius.xs,
  },
  dupBadgeText: {
    fontSize: 9,
    fontWeight: fontWeight.semibold,
    // color set inline via colors.muted
  },
  completenessBarWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  completenessBarBg: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    // backgroundColor set inline via colors.border
    overflow: "hidden",
  },
  completenessBarFill: {
    height: 6,
    borderRadius: 3,
  },
  completenessPct: {
    fontSize: text.sm,
    fontWeight: fontWeight.bold,
    // color set inline via colors.text
    minWidth: 36,
    textAlign: "right",
  },
  viewAllBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    paddingTop: 8,
    borderTopWidth: 1,
    // borderTopColor set inline via colors.border
  },
  viewAllText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },

  // The concentration verdict, inline at the foot of the Allocations card.
  // Separated from the list above by a hairline so it reads as a conclusion
  // drawn FROM the distribution rather than another row of it.
  concentrationRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  concentrationText: {
    flex: 1,
    fontSize: text.sm,
    lineHeight: 18,
  },

  // Diversification suggestions
  riskRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    marginTop: 10,
  },
  riskDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    // Nudge down so the dot optically centres on the first line of text.
    marginTop: 6,
  },
  riskText: {
    flex: 1,
    fontSize: text.sm,
    lineHeight: 20,
  },

  // DCA Cost Basis (M3)
  dcaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
    marginBottom: 12,
  },
  dcaStat: {
    flex: 1,
    alignItems: "center",
  },
  dcaLabel: {
    fontSize: text.sm,
    fontWeight: fontWeight.medium,
    marginBottom: 4,
  },
  dcaValue: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
  },
  dcaBar: {
    height: 6,
    borderRadius: 3,
    overflow: "hidden",
  },
  dcaBarFill: {
    height: 6,
    borderRadius: 3,
  },

});
