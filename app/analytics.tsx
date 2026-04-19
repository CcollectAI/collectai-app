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
import { WinnersLosersSection } from '@/components/analytics/WinnersLosersSection';
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
  const { limits } = useBillingLimits();
  const [refreshing, setRefreshing] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const [collectionTrends, setCollectionTrends] = useState<Record<string, unknown> | null>(null);
  const [predictionAccuracy, setPredictionAccuracy] = useState<{ category: string; mae: number; mape: number; r2: number }[] | null>(null);
  const [categoryStats, setCategoryStats] = useState<{ category: string; item_count: number; total_value: number; avg_value: number; change_7d: number; change_7d_pct: number; trend: string; max_item_value: number }[]>([]);
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

  // Fetch backend collection trends + prediction accuracy (enrichment) — parallelized
  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      collectorsApi.getCollectionTrends(30),
      collectorsApi.getPredictionAccuracy(),
      collectorsApi.getPortfolioCategoryStats(),
      collectorsApi.getCategoryHealth(),
    ]).then(([trendsResult, accuracyResult, statsResult, healthResult]) => {
      if (cancelled) return;
      if (trendsResult.status === 'fulfilled' && trendsResult.value) {
        setCollectionTrends(trendsResult.value as Record<string, unknown>);
      } else if (trendsResult.status === 'rejected') {
        logger.warn('[Analytics] collection trends fetch failed:', trendsResult.reason);
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

  // M4: Memoize derived snapshot data to avoid recomputing on every render
  const { pl, allocations, winnersLosers, tierSummary, items } = useMemo(() => snapshot ?? {
    pl: null,
    allocations: [],
    winnersLosers: { winners: [], losers: [], neutral: [] },
    tierSummary: null,
    items: [],
  }, [snapshot]);

  const isPositive = useMemo(() => (pl?.deltaPct ?? 0) >= 0, [pl?.deltaPct]);

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
    return categorySummaries
      .filter((c) => c.ownedCount > 0)
      .sort((a, b) => b.completionPct - a.completionPct);
  }, [categorySummaries]);

  if (loading) {
    return (
      <View style={[styles.safe, { backgroundColor: colors.background }]}>
        <Stack.Screen options={{ headerTitle: 'Analytics' }} />
        <View style={styles.loadingContainer}>
          <SkeletonList count={3} type="analytics" />
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

        {/* Upgrade prompt for free-tier users */}
        {!limits.advanced_analytics && (
          <UpgradePrompt feature="Advanced Analytics" requiredPlan="Pro" />
        )}

        {/* Hot Right Now (moved from home 2026-04-18, Pro-gated) */}
        {limits.advanced_analytics ? (
          <DemandHeatSection />
        ) : (
          <UpgradePrompt feature="Hot Right Now" requiredPlan="Pro" />
        )}

        {/* Error Banner */}
        {error && (
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
              <View style={[styles.badge, { backgroundColor: isPositive ? colors.successBg : colors.dangerBg }]}>
                <Text style={[styles.badgeText, { color: isPositive ? colors.success : colors.danger }]}>
                  {formatPct(pl.deltaPct)}
                </Text>
              </View>
            </View>

            <View style={styles.metricsGrid}>
              <View style={styles.metricItem}>
                <Text style={[styles.metricLabel, { color: colors.muted }]}>Current Value</Text>
                <Text style={[styles.metricValue, { color: colors.text }]}>{formatPrice(pl.currentValue, settings.currency ?? 'EUR')}</Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={[styles.metricLabel, { color: colors.muted }]}>Starting Value</Text>
                <Text style={[styles.metricValueMuted, { color: colors.muted }]}>{formatPrice(pl.startValue, settings.currency ?? 'EUR')}</Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={[styles.metricLabel, { color: colors.muted }]}>Total Gain/Loss</Text>
                <Text style={[styles.metricValue, { color: isPositive ? colors.success : colors.danger }]}>
                  {pl.deltaAbs >= 0 ? "+" : ""}{formatPrice(pl.deltaAbs, settings.currency ?? 'EUR')}
                </Text>
              </View>
              <View style={styles.metricItem}>
                <Text style={[styles.metricLabel, { color: colors.muted }]}>Max Drawdown</Text>
                <Text style={[styles.metricValue, { color: colors.danger }]}>
                  {formatPct(pl.maxDrawdownPct, false)}
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
          </View>
        )}

        {/* H1: Category Statistics Dashboard (Pro+) */}
        {limits.advanced_analytics ? (
          <CategoryPerformanceSection categoryStats={categoryStats} categoryHealth={categoryHealth} />
        ) : (
          <UpgradePrompt feature="Category Performance" requiredPlan="Pro" />
        )}

        {/* Winners & Losers (Pro+) */}
        {limits.advanced_analytics && (
          <WinnersLosersSection
            winners={winnersLosers.winners}
            losers={winnersLosers.losers}
          />
        )}

        {/* Items Summary (Pro+) */}
        {!limits.advanced_analytics && items.length > 0 && (
          <UpgradePrompt feature="Holdings Breakdown" requiredPlan="Pro" />
        )}
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
        {!limits.advanced_analytics && activeCategories.length > 0 && (
          <UpgradePrompt feature="Collection Completeness" requiredPlan="Pro" />
        )}
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
