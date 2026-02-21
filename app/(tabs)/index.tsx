/**
 * Portfolio Screen — Collectr-style portfolio view with interactive chart.
 *
 * Features:
 * - Tiffany blue (#81D8D0) themed chart
 * - Analytics banner with CTA
 * - Pressable top valued items
 * - Watchlist section with price targets
 */

import React, { useEffect, useMemo, useState, useCallback } from "react";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Platform,
  ActivityIndicator,
  Animated,
  RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { PortfolioLineChart, type TimeSeriesPoint } from "@/components/PortfolioLineChart";
import { useWatchlist } from "@/state/watchlistStore";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { ThemeToggleButton } from "@/components/ThemeToggleButton";
import { useAppTheme } from "@/hooks/useAppTheme";
import { featureFlags } from "@/config/featureFlags";
import { InsightsCard } from "@/components/home/InsightsCard";
import { AlertsCard } from "@/components/home/AlertsCard";
import { usePortfolioInsights } from "@/hooks/usePortfolioInsights";
import { useAlertsFeed } from "@/hooks/useAlertsFeed";
import { AnimatedPressable, useEnterReveal, AnimatedCounter } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { formatPrice } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { useBillingLimits } from "@/hooks/useBillingLimits";
import { collectorsApi } from "@/api/collectorsApi";
import logger from "@/utils/logger";

// Feature flag check: real mode when EXPO_PUBLIC_SUPABASE_MODE=real
const SUPABASE_MODE = process.env.EXPO_PUBLIC_SUPABASE_MODE ?? "mock";
const USE_REAL_BACKEND = SUPABASE_MODE === "real";

// Keep imports conservative and optional.
let analyticsApi: Record<string, unknown> | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  analyticsApi = require("@/store/portfolioAnalyticsStore");
} catch {
  analyticsApi = null;
}

// Optional: collectors client for real backend
let collectorsClient: Record<string, unknown> | null = null;
if (USE_REAL_BACKEND) {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    collectorsClient = require("@/services/collectorsClient");
  } catch {
    collectorsClient = null;
  }
}

type RangeKey = "1D" | "7D" | "30D";

type ItemRow = {
  id: string;
  name: string;
  category?: string;
  value: number;
  changePct?: number;
};

// ─────────────────────────────────────────────────────────────────────────────
// Formatting helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatPct(p?: number): string {
  if (p === undefined || p === null || Number.isNaN(p)) return "—";
  const sign = p > 0 ? "+" : "";
  return `${sign}${(p * 100).toFixed(2)}%`;
}

function formatDeltaEUR(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${formatPrice(n)}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Data extraction helpers
// ─────────────────────────────────────────────────────────────────────────────

function extractSeries(raw: unknown): TimeSeriesPoint[] {
  const rawObj = raw as Record<string, unknown> | unknown[] | null;
  const arr =
    (Array.isArray(rawObj) && rawObj) ||
    (rawObj && !Array.isArray(rawObj) && (rawObj as Record<string, unknown>).points) ||
    (rawObj && !Array.isArray(rawObj) && (rawObj as Record<string, unknown>).series) ||
    (rawObj && !Array.isArray(rawObj) && (rawObj as Record<string, unknown>).data) ||
    [];
  if (!Array.isArray(arr)) return [];
  return arr
    .map((p: Record<string, unknown>) => {
      const t = p?.t ?? p?.timestamp ?? new Date().toISOString();
      const v = typeof p?.v === "number" ? p.v : typeof p?.value === "number" ? p.value : Number(p?.y);
      if (typeof v !== "number" || Number.isNaN(v)) return null;
      return { t: String(t), v };
    })
    .filter(Boolean) as TimeSeriesPoint[];
}

function extractItems(raw: unknown): ItemRow[] {
  const rawObj = raw as Record<string, unknown> | null;
  const base =
    rawObj?.items ||
    rawObj?.holdings ||
    rawObj?.positions ||
    (rawObj?.snapshot as Record<string, unknown> | undefined)?.items ||
    (rawObj?.snapshot as Record<string, unknown> | undefined)?.holdings ||
    [];
  if (!Array.isArray(base)) return [];
  return base
    .map((it: Record<string, unknown>, i: number) => {
      const value =
        typeof it?.value === "number"
          ? it.value
          : typeof it?.currentValue === "number"
          ? it.currentValue
          : typeof it?.marketValue === "number"
          ? it.marketValue
          : typeof it?.totalValue === "number"
          ? it.totalValue
          : Number(it?.price ?? 0) * Number(it?.qty ?? 1);

      const name = String(it?.name ?? it?.title ?? it?.displayName ?? `Item ${i + 1}`);
      const id = String(it?.id ?? it?.uuid ?? `${i}`);
      const changePct =
        typeof it?.changePct === "number"
          ? it.changePct
          : typeof it?.change1dPct === "number"
          ? it.change1dPct
          : typeof it?.pctChange === "number"
          ? it.pctChange
          : undefined;

      const category = it?.category ? String(it.category) : undefined;

      if (!Number.isFinite(value)) return null;
      return { id, name, category, value, changePct };
    })
    .filter(Boolean) as ItemRow[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

function PortfolioScreen() {
  const router = useRouter();
  const watchlist = useWatchlist();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { limits } = useBillingLimits();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const [range, setRange] = useState<RangeKey>("7D");
  const [series, setSeries] = useState<TimeSeriesPoint[]>([]);
  const [items, setItems] = useState<ItemRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tierSummary, setTierSummary] = useState<{ tier: string; rarityScore: number; completenessScore: number; diversificationScore: number } | null>(null);

  // Category breakdown state
  type CategoryBreakdownItem = { category: string; item_count: number; total_value: number; percentage: number };
  const [categoryBreakdown, setCategoryBreakdown] = useState<CategoryBreakdownItem[]>([]);
  const [breakdownLoading, setBreakdownLoading] = useState(false);

  // Data insights & alerts (feature flagged)
  const { insights } = usePortfolioInsights({
    period: range.toLowerCase() as '7d' | '30d',
    enabled: featureFlags.FEATURE_DATA_INSIGHTS_ALERTS
  });
  const { alerts, markAsRead } = useAlertsFeed({
    limit: 5,
    enabled: featureFlags.FEATURE_DATA_INSIGHTS_ALERTS
  });

  // Get watchlist items with their alerts
  const watchlistItems = useMemo(() => {
    return watchlist.items.slice(0, 5).map((item) => ({
      ...item,
      alert: watchlist.getAlert(item.id),
    }));
  }, [watchlist]);

  // Compute totals from series
  const { total, delta, deltaPct } = useMemo(() => {
    if (!series.length) {
      return { total: 0, delta: 0, deltaPct: 0 };
    }
    const sorted = [...series].sort(
      (a, b) => new Date(a.t).getTime() - new Date(b.t).getTime()
    );
    const startVal = sorted[0].v;
    const endVal = sorted[sorted.length - 1].v;
    const d = endVal - startVal;
    const pct = startVal > 0 ? d / startVal : 0;
    return { total: endVal, delta: d, deltaPct: pct };
  }, [series]);

  // Load data based on mode and range
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Pass 2 (C): Real backend wiring
      if (USE_REAL_BACKEND && collectorsClient?.getPortfolioTimeseries) {
        try {
          const rangeParam = range.toLowerCase() as "1d" | "7d" | "30d";
          const timeseriesData = await collectorsClient.getPortfolioTimeseries(rangeParam);
          const extractedSeries = extractSeries(timeseriesData);
          if (extractedSeries.length) {
            setSeries(extractedSeries);
          } else {
            setSeries([]);
          }

          if (collectorsClient?.getPortfolioItems) {
            const itemsData = await collectorsClient.getPortfolioItems();
            const extractedItems = extractItems(itemsData);
            if (extractedItems.length) {
              setItems(extractedItems.sort((a, b) => b.value - a.value));
            } else {
              setItems([]);
            }
          }
        } catch (realErr: unknown) {
          logger.warn("[Portfolio] Real backend error, falling back:", realErr);
          setError("Could not load portfolio data.");
          setSeries([]);
          setItems([]);
        }
      } else {
        // Mock mode: use analytics store or fallback
        let baseSeries: TimeSeriesPoint[] = [];
        let baseItems: ItemRow[] = [];

        if (analyticsApi?.fetchPortfolioSnapshot) {
          try {
            const snap = await analyticsApi.fetchPortfolioSnapshot();
            const extractedSeries = extractSeries(snap?.series || snap);
            const extractedItems = extractItems(snap);

            baseSeries = extractedSeries.length ? extractedSeries : [];
            baseItems = extractedItems.length
              ? extractedItems.sort((a, b) => b.value - a.value)
              : [];
            if (snap?.tierSummary) setTierSummary(snap.tierSummary);
          } catch (mockErr) {
            logger.warn("[Portfolio] Mock store error:", mockErr);
          }
        }

        // Filter series by selected range
        const now = new Date();
        const rangeDays = range === "1D" ? 1 : range === "7D" ? 7 : 30;
        const cutoff = new Date(now.getTime() - rangeDays * 24 * 60 * 60 * 1000);
        const filtered = baseSeries.filter(
          (p) => new Date(p.t).getTime() >= cutoff.getTime()
        );
        // Use filtered if enough points, otherwise show all (demo data may be older)
        setSeries(filtered.length >= 2 ? filtered : baseSeries);
        setItems(baseItems);
      }
    } catch (err: unknown) {
      logger.warn("[Portfolio] Unexpected error:", err);
      setError("Failed to load portfolio data.");
      setSeries([]);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Load category breakdown
  useEffect(() => {
    setBreakdownLoading(true);
    collectorsApi.get('/analytics/portfolio/category-breakdown')
      .then((res: unknown) => {
        const data = res as Record<string, unknown>;
        const cats = Array.isArray(data?.categories) ? data.categories as CategoryBreakdownItem[] : [];
        setCategoryBreakdown(cats);
      })
      .catch((err: unknown) => {
        logger.warn('[Portfolio] category breakdown fetch failed:', err);
        setCategoryBreakdown([]);
      })
      .finally(() => setBreakdownLoading(false));
  }, []);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setRefreshing(false);
  }, [loadData, settings.hapticsEnabled]);

  // Determine if positive or negative
  const isPositive = deltaPct >= 0;

  const rangeButtons: RangeKey[] = ["1D", "7D", "30D"];

  // Navigate to item detail
  const handleItemPress = (item: ItemRow) => {
    router.push({
      pathname: "/item/[id]",
      params: {
        id: item.id,
        name: item.name,
        category: item.category ?? "",
        value: String(item.value),
      },
    });
  };

  // Navigate to analytics
  const handleAnalyticsPress = () => {
    router.push("/analytics");
  };

  // Navigate to items tab from watchlist
  const handleWatchlistPress = () => {
    router.navigate("/(tabs)/items");
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]} edges={["top", "left", "right"]}>
      <ScrollView
        contentContainerStyle={[styles.container, { backgroundColor: colors.background }]}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            tintColor={colors.accent}
            colors={[colors.accent]}
          />
        }
      >
        <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
        {/* Header */}
        <View style={styles.headerRow}>
          <View style={styles.headerLeft}>
            <Text style={[styles.headerTitle, { color: colors.text }]}>Portfolio</Text>
            <Text style={[styles.headerSubtitle, { color: colors.muted }]}>Track your collection value.</Text>
          </View>
          <View style={styles.headerIcons}>
            <InboxHeaderButton color={colors.text} size={22} />
            <ThemeToggleButton size={22} />
            <AnimatedPressable
              onPress={() => router.push('/settings')}
              style={{ padding: 4 }}
              accessibilityRole="button"
              accessibilityLabel="Open settings"
            >
              <Ionicons name="settings-outline" size={22} color={colors.text} />
            </AnimatedPressable>
          </View>
        </View>

        {/* Collection Value */}
        <View style={styles.valueSection}>
          <Text style={[styles.headerLabel, { color: colors.muted }]}>COLLECTION VALUE</Text>
          <AnimatedCounter
            value={total}
            format={(v) => formatPrice(v)}
            style={[styles.totalValue, { color: colors.text }]}
            enabled={settings.animationsEnabled}
            accessibilityLabel={`Collection value: ${formatPrice(total)}`}
          />
          <Text style={[styles.deltaText, { color: isPositive ? '#10B981' : '#EF4444' }]}>
            {formatDeltaEUR(delta)} ({formatPct(deltaPct)})
          </Text>
        </View>

        {/* Range Toggles */}
        <View style={styles.rangeRow}>
          {rangeButtons.map((k) => {
            const active = k === range;
            return (
              <AnimatedPressable
                key={k}
                accessibilityRole="button"
                accessibilityLabel={`Show ${k} range`}
                onPress={() => {
                  if (k !== range) {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  }
                  setRange(k);
                }}
                style={[
                  styles.rangeBtn,
                  { backgroundColor: colors.card, borderColor: colors.border },
                  active && { backgroundColor: colors.accent + '20', borderColor: colors.accent },
                ]}
              >
                <Text style={[styles.rangeText, { color: colors.muted }, active && { color: colors.text }]}>
                  {k}
                </Text>
              </AnimatedPressable>
            );
          })}
        </View>

        {/* Chart Card with Interactive Line Chart */}
        <View style={[styles.chartCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          {loading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="small" color={colors.accent} />
              <Text style={[styles.loadingText, { color: colors.muted }]}>Loading...</Text>
            </View>
          ) : (
            <PortfolioLineChart
              series={series}
              accentColor={colors.accent}
              showValueHeader={true}
              showAxisLabels={true}
              axisLabelColor={colors.muted}
              gridColor={colors.border}
              textColor={colors.text}
              dotFillColor={colors.card}
            />
          )}
        </View>

        {/* Error message (if any) */}
        {error && (
          <View style={[styles.errorBanner, { backgroundColor: '#EF4444' + '15' }]}>
            <Ionicons name="warning-outline" size={14} color="#EF4444" />
            <Text style={[styles.errorText, { color: '#EF4444' }]}>{error}</Text>
          </View>
        )}

        {/* Category Breakdown */}
        <View style={styles.sectionHeader}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Category Breakdown</Text>
        </View>
        {breakdownLoading ? (
          <View style={[styles.breakdownCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <ActivityIndicator size="small" color={colors.accent} style={{ marginVertical: 16 }} />
          </View>
        ) : categoryBreakdown.length > 0 ? (
          <View style={[styles.breakdownCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            {/* Horizontal bar chart for top 5 */}
            {categoryBreakdown.slice(0, 5).map((cat, idx) => {
              const barColors = [colors.accent, colors.accent + 'CC', colors.accent + '99', colors.accent + '66', colors.accent + '44'];
              const barColor = barColors[idx] || colors.accent;
              return (
                <View key={cat.category} style={styles.breakdownBarRow}>
                  <Text style={[styles.breakdownBarLabel, { color: colors.text }]} numberOfLines={1}>
                    {cat.category}
                  </Text>
                  <View style={styles.breakdownBarTrack}>
                    <View
                      style={[
                        styles.breakdownBarFill,
                        { backgroundColor: barColor, width: `${Math.max(cat.percentage, 2)}%` },
                      ]}
                    />
                  </View>
                  <Text style={[styles.breakdownBarPct, { color: colors.muted }]}>
                    {cat.percentage.toFixed(0)}%
                  </Text>
                </View>
              );
            })}

            {/* Scrollable category cards */}
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.breakdownCardsRow}
              style={styles.breakdownCardsScroll}
            >
              {categoryBreakdown.map((cat) => (
                <View
                  key={cat.category}
                  style={[styles.breakdownCategoryCard, { backgroundColor: colors.background, borderColor: colors.border }]}
                >
                  <Text style={[styles.breakdownCatName, { color: colors.text }]} numberOfLines={1}>
                    {cat.category}
                  </Text>
                  <Text style={[styles.breakdownCatItems, { color: colors.muted }]}>
                    {cat.item_count} item{cat.item_count !== 1 ? 's' : ''}
                  </Text>
                  <Text style={[styles.breakdownCatValue, { color: colors.text }]}>
                    {formatPrice(cat.total_value)}
                  </Text>
                  <View style={[styles.breakdownPctBadge, { backgroundColor: colors.accent + '15' }]}>
                    <Text style={[styles.breakdownPctBadgeText, { color: colors.accent }]}>
                      {cat.percentage.toFixed(0)}%
                    </Text>
                  </View>
                </View>
              ))}
            </ScrollView>
          </View>
        ) : (
          <View style={[styles.breakdownCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[styles.breakdownEmpty, { color: colors.muted }]}>
              Add items to see your category breakdown.
            </Text>
          </View>
        )}

        {/* Watchlist Card (always show - has empty state) */}
        {featureFlags.FEATURE_DATA_INSIGHTS_ALERTS && (
          <AlertsCard
            alerts={alerts}
            onAlertPress={(alert) => {
              markAsRead(alert.id);
              const itemId = alert.itemId || alert.id;
              router.push({
                pathname: '/item/[id]',
                params: {
                  id: itemId,
                  name: alert.itemName,
                  category: alert.itemCategory || '',
                  value: String(alert.value || 0),
                },
              });
            }}
            onStartWatchlist={handleWatchlistPress}
            showEmptyState={true}
          />
        )}

        {/* Deal Agent Summary Card */}
        <AnimatedPressable
          style={[styles.analyticsBanner, { backgroundColor: colors.card, borderColor: colors.border }]}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.push(limits.deal_discovery ? "/purchase" : "/subscription");
          }}
          accessibilityRole="button"
          accessibilityLabel={limits.deal_discovery ? "Open Deal Agent" : "Upgrade to unlock Deal Agent"}
        >
          <View style={styles.analyticsBannerLeft}>
            <View style={[styles.analyticsIconWrap, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name={limits.deal_discovery ? "flash" : "lock-closed"} size={18} color={colors.accent} />
            </View>
            <View style={styles.analyticsBannerText}>
              <Text style={[styles.analyticsBannerTitle, { color: colors.text }]}>Deal Agent</Text>
              <Text style={[styles.analyticsBannerSubtitle, { color: colors.muted }]}>
                {limits.deal_discovery ? "Always-on deal discovery" : "Upgrade to Pro to unlock"}
              </Text>
            </View>
          </View>
          <View style={[styles.analyticsBannerBtn, { backgroundColor: colors.accent }]}>
            <Text style={styles.analyticsBannerBtnText}>{limits.deal_discovery ? "View" : "Upgrade"}</Text>
          </View>
        </AnimatedPressable>

        {featureFlags.FEATURE_DATA_INSIGHTS_ALERTS && insights && limits.advanced_analytics && (
          <InsightsCard
            insights={insights}
            tierSummary={tierSummary}
            onViewDetails={handleAnalyticsPress}
          />
        )}

        {/* Collection Section Header */}
        <View style={styles.sectionHeader}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Collection</Text>
        </View>

        {/* Top Movers & Shakers */}
        <View style={[styles.listCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          {/* Movers (top gainers) */}
          {items
            .filter((it) => (it.changePct ?? 0) > 0)
            .sort((a, b) => (b.changePct ?? 0) - (a.changePct ?? 0))
            .slice(0, 3)
            .map((it, idx) => (
              <AnimatedPressable
                key={it.id}
                style={[
                  styles.itemRow,
                  { borderTopColor: colors.border },
                  idx === 0 && styles.itemRowFirst,
                ]}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  handleItemPress(it);
                }}
                accessibilityRole="button"
                accessibilityLabel={`View ${it.name}`}
              >
                <View style={styles.itemLeft}>
                  <View style={styles.moverLabel}>
                    <Ionicons name="trending-up" size={12} color="#10B981" />
                    <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>
                      {it.name}
                    </Text>
                  </View>
                  <Text style={[styles.itemCategory, { color: colors.muted }]} numberOfLines={1}>
                    {it.category ?? "—"}
                  </Text>
                </View>
                <View style={styles.itemRight}>
                  <Text style={[styles.itemValue, { color: colors.text }]}>{formatPrice(it.value)}</Text>
                  <Text style={[styles.itemPct, { color: '#10B981' }]}>
                    {formatPct(it.changePct)}
                  </Text>
                </View>
              </AnimatedPressable>
            ))}
          {/* Shakers (top losers) */}
          {items
            .filter((it) => (it.changePct ?? 0) < 0)
            .sort((a, b) => (a.changePct ?? 0) - (b.changePct ?? 0))
            .slice(0, 3)
            .map((it, idx, arr) => {
              const isFirstInList = idx === 0 && items.filter((i) => (i.changePct ?? 0) > 0).length === 0;
              return (
                <AnimatedPressable
                  key={it.id}
                  style={[
                    styles.itemRow,
                    { borderTopColor: colors.border },
                    isFirstInList && styles.itemRowFirst,
                  ]}
                  onPress={() => {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                    handleItemPress(it);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`View ${it.name}`}
                >
                  <View style={styles.itemLeft}>
                    <View style={styles.moverLabel}>
                      <Ionicons name="trending-down" size={12} color="#EF4444" />
                      <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>
                        {it.name}
                      </Text>
                    </View>
                    <Text style={[styles.itemCategory, { color: colors.muted }]} numberOfLines={1}>
                      {it.category ?? "—"}
                    </Text>
                  </View>
                  <View style={styles.itemRight}>
                    <Text style={[styles.itemValue, { color: colors.text }]}>{formatPrice(it.value)}</Text>
                    <Text style={[styles.itemPct, { color: '#EF4444' }]}>
                      {formatPct(it.changePct)}
                    </Text>
                  </View>
                </AnimatedPressable>
              );
            })}
        </View>

        {/* Watchlist Section */}
        {watchlistItems.length > 0 && (
          <>
            <View style={styles.sectionHeader}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Watchlist</Text>
              <AnimatedPressable
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  handleWatchlistPress();
                }}
                accessibilityRole="link"
                accessibilityLabel="See all watchlist items"
              >
                <Text style={[styles.seeAllLink, { color: colors.accent }]}>See all →</Text>
              </AnimatedPressable>
            </View>

            <View style={[styles.listCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
              {watchlistItems.map((it, idx) => {
                const hasAlert = Boolean(it.alert);
                const targetPrice = it.alert?.threshold;
                const currentValue = it.currentValue ?? it.value ?? 0;

                return (
                  <AnimatedPressable
                    key={it.id}
                    style={[
                      styles.watchlistRow,
                      { borderTopColor: colors.border },
                      idx === 0 && styles.itemRowFirst,
                    ]}
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                      router.navigate('/(tabs)/items');
                    }}
                    accessibilityRole="button"
                    accessibilityLabel={`Watchlist item: ${it.name ?? it.title}`}
                  >
                    <View style={styles.watchlistLeft}>
                      <View style={styles.watchlistNameRow}>
                        <Ionicons
                          name={hasAlert ? "notifications" : "notifications-outline"}
                          size={16}
                          color={hasAlert ? colors.accent : colors.muted}
                          style={styles.bellIcon}
                        />
                        <Text style={[styles.itemName, { color: colors.text }]} numberOfLines={1}>
                          {it.name ?? it.title ?? "Watchlist Item"}
                        </Text>
                      </View>
                      <Text style={[styles.itemCategory, { color: colors.muted }]} numberOfLines={1}>
                        {it.category ?? "—"}
                      </Text>
                    </View>
                    <View style={styles.watchlistRight}>
                      {targetPrice != null && (
                        <Text style={[styles.targetPrice, { color: colors.accent }]}>
                          Target {formatPrice(targetPrice)}
                        </Text>
                      )}
                      <Text style={[styles.currentPrice, { color: colors.muted }]}>
                        Current {formatPrice(currentValue)}
                      </Text>
                    </View>
                  </AnimatedPressable>
                );
              })}
            </View>
          </>
        )}

        {/* Bottom spacing */}
        <View style={{ height: Platform.OS === "ios" ? 24 : 18 }} />
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Styles (layout only — colors applied inline via useAppTheme)
// ─────────────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  container: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 24,
  },

  // Header
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
  },
  headerLeft: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: "700",
  },
  headerSubtitle: {
    fontSize: 12,
    marginTop: 4,
  },
  headerIcons: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  valueSection: {
    marginBottom: 16,
  },
  headerLabel: {
    fontSize: 12,
    fontWeight: "600",
    marginBottom: 4,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  totalValue: {
    fontSize: 36,
    fontWeight: "800",
    letterSpacing: -0.5,
  },
  deltaText: {
    fontSize: 15,
    fontWeight: "700",
    marginTop: 4,
  },

  // Range toggles
  rangeRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 8,
    marginBottom: 12,
  },
  rangeBtn: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderWidth: 1,
    borderRadius: 8,
  },
  rangeText: {
    fontWeight: "700",
    fontSize: 13,
  },

  // Chart card
  chartCard: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    minHeight: 220,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 190,
  },
  loadingText: {
    fontSize: 12,
    marginTop: 8,
  },

  // Error
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    marginBottom: 12,
  },
  errorText: {
    fontSize: 12,
    fontWeight: "500",
  },

  // Mode indicator (dev)
  modeIndicator: {
    fontSize: 10,
    textAlign: "center",
    marginBottom: 8,
  },

  // Analytics Banner
  analyticsBanner: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  analyticsBannerLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  analyticsIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  analyticsBannerText: {
    flex: 1,
  },
  analyticsBannerTitle: {
    fontSize: 14,
    fontWeight: "600",
    marginBottom: 2,
  },
  analyticsBannerSubtitle: {
    fontSize: 12,
  },
  analyticsBannerBtn: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    marginLeft: 12,
  },
  analyticsBannerBtnText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "600",
  },

  // Section header
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
  },
  seeAllLink: {
    fontSize: 13,
    fontWeight: "600",
  },

  // Items list
  listCard: {
    borderWidth: 1,
    borderRadius: 12,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
    marginBottom: 20,
  },
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderTopWidth: 1,
  },
  itemRowFirst: {
    borderTopWidth: 0,
  },
  itemLeft: {
    flex: 1,
    paddingRight: 12,
  },
  moverLabel: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  itemName: {
    fontWeight: "700",
    fontSize: 14,
  },
  itemCategory: {
    fontWeight: "600",
    fontSize: 12,
    marginTop: 2,
  },
  itemRight: {
    alignItems: "flex-end",
    minWidth: 90,
  },
  itemValue: {
    fontWeight: "800",
    fontSize: 14,
  },
  itemPct: {
    fontWeight: "700",
    fontSize: 12,
    marginTop: 2,
  },

  // Watchlist rows
  watchlistRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderTopWidth: 1,
  },
  watchlistLeft: {
    flex: 1,
    paddingRight: 12,
  },
  watchlistNameRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  bellIcon: {
    marginRight: 6,
  },
  watchlistRight: {
    alignItems: "flex-end",
    minWidth: 100,
  },
  targetPrice: {
    fontWeight: "700",
    fontSize: 13,
  },
  currentPrice: {
    fontWeight: "600",
    fontSize: 12,
    marginTop: 2,
  },

  // Category Breakdown
  breakdownCard: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
  },
  breakdownBarRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
  },
  breakdownBarLabel: {
    width: 80,
    fontSize: 12,
    fontWeight: "600",
    marginRight: 8,
  },
  breakdownBarTrack: {
    flex: 1,
    height: 10,
    borderRadius: 5,
    backgroundColor: "#E2E8F020",
    overflow: "hidden",
    marginRight: 8,
  },
  breakdownBarFill: {
    height: "100%",
    borderRadius: 5,
  },
  breakdownBarPct: {
    width: 36,
    fontSize: 12,
    fontWeight: "600",
    textAlign: "right",
  },
  breakdownCardsScroll: {
    marginTop: 10,
  },
  breakdownCardsRow: {
    gap: 10,
  },
  breakdownCategoryCard: {
    width: 130,
    borderRadius: 10,
    borderWidth: 1,
    padding: 10,
  },
  breakdownCatName: {
    fontSize: 13,
    fontWeight: "700",
    marginBottom: 2,
  },
  breakdownCatItems: {
    fontSize: 11,
    marginBottom: 4,
  },
  breakdownCatValue: {
    fontSize: 14,
    fontWeight: "800",
    marginBottom: 6,
  },
  breakdownPctBadge: {
    alignSelf: "flex-start",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  breakdownPctBadgeText: {
    fontSize: 11,
    fontWeight: "700",
  },
  breakdownEmpty: {
    fontSize: 13,
    textAlign: "center",
    paddingVertical: 16,
  },
});

export default function PortfolioScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Portfolio">
      <PortfolioScreen />
    </ScreenErrorBoundary>
  );
}
