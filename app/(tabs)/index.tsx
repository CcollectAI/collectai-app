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
  Modal,
  TouchableOpacity,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { PortfolioLineChart, type TimeSeriesPoint } from "@/components/PortfolioLineChart";
import { SkeletonPortfolioHeader } from "@/components/Skeleton";
import { dataProvider } from "@/data";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { ThemeToggleButton } from "@/components/ThemeToggleButton";
import { useAppTheme } from "@/hooks/useAppTheme";
import { featureFlags } from "@/config/featureFlags";
import { InsightsCard } from "@/components/home/InsightsCard";
import { AlertsCard } from "@/components/home/AlertsCard";
import { PortfolioValueHeader } from "@/components/home/PortfolioValueHeader";
import { ChartRangeSelector } from "@/components/home/ChartRangeSelector";
import { CategoryBreakdownSection, type CategoryBreakdownItem } from "@/components/home/CategoryBreakdownSection";
import { getCategoryByName, getCategoryById } from "@/data/categories";
import { TopItemsList, type ItemRow } from "@/components/home/TopItemsList";
import { FollowedCategoriesCarousel } from "@/components/home/FollowedCategoriesCarousel";
import { usePortfolioInsights } from "@/hooks/usePortfolioInsights";
import { useAlertsFeed } from "@/hooks/useAlertsFeed";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { formatPrice } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { useBillingLimits } from "@/hooks/useBillingLimits";
import { collectorsApi, getNotificationHistory } from "@/api/collectorsApi";
import logger from "@/utils/logger";
import { useStoreReview } from "@/hooks/useStoreReview";
import AsyncStorage from "@react-native-async-storage/async-storage";

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

type RangeKey = "1D" | "7D" | "30D" | "90D" | "1Y" | "ALL";



// ─────────────────────────────────────────────────────────────────────────────
// Formatting helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatPct(p?: number): string {
  if (p === undefined || p === null || Number.isNaN(p)) return "—";
  const sign = p > 0 ? "+" : "";
  return `${sign}${(p * 100).toFixed(2)}%`;
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
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tierSummary, setTierSummary] = useState<{ tier: 'Diamond' | 'Gold' | 'Silver' | 'Unranked'; rarityScore: number; completenessScore: number; diversificationScore: number } | null>(null);

  // Store review prompt (criteria: 10+ items, 3+ days, 90-day cooldown)
  useStoreReview(items.length);

  // Category breakdown state
  const [categoryBreakdown, setCategoryBreakdown] = useState<CategoryBreakdownItem[]>([]);
  const [breakdownLoading, setBreakdownLoading] = useState(false);

  // Followed/personalized categories from onboarding
  const [followedCategories, setFollowedCategories] = useState<string[]>([]);

  // Notification unread badge
  const [unreadNotifCount, setUnreadNotifCount] = useState(0);
  useEffect(() => {
    getNotificationHistory({ limit: 1, offset: 0 })
      .then((data) => setUnreadNotifCount(data.unread_count))
      .catch(() => {});
  }, []);

  // Data insights & alerts (feature flagged)
  const { insights } = usePortfolioInsights({
    period: range.toLowerCase() as '7d' | '30d',
    enabled: featureFlags.FEATURE_DATA_INSIGHTS_ALERTS
  });
  const { alerts, markAsRead } = useAlertsFeed({
    limit: 5,
    enabled: featureFlags.FEATURE_DATA_INSIGHTS_ALERTS
  });


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
          const rangeParam = range.toLowerCase() as "1d" | "7d" | "30d" | "90d" | "1y" | "all";
          const timeseriesData = await (collectorsClient as any).getPortfolioTimeseries(rangeParam);
          const extractedSeries = extractSeries(timeseriesData);
          if (extractedSeries.length) {
            setSeries(extractedSeries);
          } else {
            setSeries([]);
          }

          if (collectorsClient?.getPortfolioItems) {
            const itemsData = await (collectorsClient as any).getPortfolioItems();
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
            const snap = await (analyticsApi as any).fetchPortfolioSnapshot();
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
        const RANGE_DAYS: Record<RangeKey, number> = { "1D": 1, "7D": 7, "30D": 30, "90D": 90, "1Y": 365, "ALL": 9999 };
        const rangeDays = RANGE_DAYS[range] ?? 30;
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
        // Backend returns "breakdown", also check "categories" for compat
        const cats = Array.isArray(data?.breakdown)
          ? (data.breakdown as Array<Record<string, unknown>>).map((b) => ({
              category: String(b.category ?? ''),
              item_count: Number(b.item_count ?? 0),
              total_value: Number(b.total_value ?? 0),
              percentage: Number(b.pct_of_portfolio ?? b.percentage ?? 0),
            }))
          : Array.isArray(data?.categories)
          ? data.categories as CategoryBreakdownItem[]
          : [];
        setCategoryBreakdown(cats);
      })
      .catch((err: unknown) => {
        logger.warn('[Portfolio] category breakdown fetch failed, using mock data:', err);
        // Mock data for development/testing
        setCategoryBreakdown([
          { category: 'pokemon', item_count: 47, total_value: 3250, percentage: 35 },
          { category: 'lego', item_count: 12, total_value: 1890, percentage: 20 },
          { category: 'manga', item_count: 86, total_value: 1420, percentage: 15 },
          { category: 'anime_figures', item_count: 8, total_value: 1200, percentage: 13 },
          { category: 'vinyl_records', item_count: 23, total_value: 980, percentage: 11 },
          { category: 'kpop_merch', item_count: 15, total_value: 560, percentage: 6 },
        ]);
      })
      .finally(() => setBreakdownLoading(false));
  }, []);

  // Load followed categories from onboarding
  useEffect(() => {
    // Try local storage first (faster), then backend
    AsyncStorage.getItem('@collectai/followed_categories')
      .then((raw) => {
        if (raw) {
          try {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed) && parsed.length > 0) {
              setFollowedCategories(parsed);
            }
          } catch {}
        }
      })
      .catch(() => {});

    // Also try backend (more authoritative)
    collectorsApi.getFollowedCategories()
      .then((data) => {
        if (data?.followed_categories?.length) {
          setFollowedCategories(data.followed_categories);
        }
      })
      .catch(() => {});
  }, []);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setRefreshing(false);
  }, [loadData, settings.hapticsEnabled]);

  // Determine if positive or negative
  const isPositive = deltaPct >= 0;

  const rangeButtons: RangeKey[] = ["1D", "7D", "30D", "90D", "1Y", "ALL"];

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

  // Navigate to watchlist tab
  const handleWatchlistPress = () => {
    router.push("/(tabs)/wishlist" as any);
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
            <AnimatedPressable
              onPress={() => router.push('/notifications')}
              style={{ padding: 4, position: 'relative' }}
              accessibilityRole="button"
              accessibilityLabel={`Notifications${unreadNotifCount > 0 ? `, ${unreadNotifCount} unread` : ''}`}
            >
              <Ionicons name="notifications-outline" size={22} color={colors.text} />
              {unreadNotifCount > 0 && (
                <View style={[styles.notifBadge, { backgroundColor: colors.error }]}>
                  <Text style={styles.notifBadgeText}>
                    {unreadNotifCount > 99 ? '99+' : unreadNotifCount}
                  </Text>
                </View>
              )}
            </AnimatedPressable>
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

        {/* Empty portfolio state OR Collection value + chart */}
        {items.length === 0 && !loading ? (
          <View style={styles.emptyPortfolio}>
            <View style={[styles.emptyIconCircle, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name="camera-outline" size={64} color={colors.accent} />
            </View>
            <Text style={[styles.emptyHeadline, { color: colors.text }]}>Start Your Collection</Text>
            <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
              Snap a photo of any collectible to get an instant AI valuation
            </Text>
            <AnimatedPressable
              style={[styles.emptyCta, { backgroundColor: colors.accent }]}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                router.push('/quickscan');
              }}
              accessibilityRole="button"
              accessibilityLabel="Open QuickScan AI to scan your first item"
            >
              <Ionicons name="camera" size={20} color="#FFFFFF" style={{ marginRight: 8 }} />
              <Text style={styles.emptyCtaText}>QuickScan AI</Text>
            </AnimatedPressable>
            <AnimatedPressable
              style={styles.emptySecondary}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                router.push('/add-manual');
              }}
              accessibilityRole="button"
              accessibilityLabel="Add an item manually"
            >
              <Text style={[styles.emptySecondaryText, { color: colors.muted }]}>or add manually</Text>
            </AnimatedPressable>
          </View>
        ) : (
          <>
            {/* Collection Value */}
            <PortfolioValueHeader
              theme={colors}
              total={total}
              delta={delta}
              deltaPct={deltaPct}
              currency={settings.currency}
              formatPrice={formatPrice}
              animationsEnabled={settings.animationsEnabled}
            />

            {/* Range Toggles */}
            <ChartRangeSelector
              theme={colors}
              selectedRange={range}
              ranges={rangeButtons}
              onRangeChange={(k) => setRange(k as RangeKey)}
              hapticsEnabled={settings.hapticsEnabled}
            />

            {/* Chart Card with Interactive Line Chart */}
            <View
              style={[styles.chartCard, { backgroundColor: colors.card, borderColor: colors.border }]}
              accessibilityRole="image"
              accessibilityLabel={`Portfolio chart: current value ${formatPrice(total)}, ${isPositive ? 'up' : 'down'} ${formatPct(deltaPct)} over ${range}`}
            >
              {loading ? (
                <SkeletonPortfolioHeader />
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
          </>
        )}

        {/* Error message (if any) */}
        {error && (
          <View style={[styles.errorBanner, { backgroundColor: colors.error + '15' }]}>
            <Ionicons name="warning-outline" size={14} color={colors.error} />
            <Text style={[styles.errorText, { color: colors.error }]}>{error}</Text>
          </View>
        )}

        {/* Add Item Banner */}
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            setAddMenuOpen(true);
          }}
          style={[styles.addBanner, { backgroundColor: colors.accent + '0D', borderColor: colors.accent + '30' }]}
          accessibilityRole="button"
          accessibilityLabel="Add an item to your collection"
        >
          <View style={[styles.addBannerIconWrap, { backgroundColor: colors.accent }]}>
            <Ionicons name="add" size={18} color="#FFFFFF" />
          </View>
          <View style={styles.addBannerText}>
            <Text style={[styles.addBannerTitle, { color: colors.text }]}>Add to Collection</Text>
            <Text style={[styles.addBannerSubtitle, { color: colors.muted }]}>Scan, snap, or enter manually</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.accent} />
        </AnimatedPressable>

        {/* Personalized Categories (from onboarding) */}
        <FollowedCategoriesCarousel
          theme={colors}
          categories={followedCategories}
          onCategoryPress={(catSlug) => router.push({ pathname: '/categories/[categoryId]', params: { categoryId: catSlug } })}
          hapticsEnabled={settings.hapticsEnabled}
        />

        {/* Category Breakdown */}
        <CategoryBreakdownSection
          theme={colors}
          breakdown={categoryBreakdown}
          loading={breakdownLoading}
          formatPrice={(v) => formatPrice(v)}
          resolveCategoryName={(raw) => {
            const cat = getCategoryById(raw) ?? getCategoryByName(raw);
            return cat?.name ?? raw;
          }}
          onCategoryPress={(catRaw) => {
            const cat = getCategoryById(catRaw) ?? getCategoryByName(catRaw);
            const categoryId = cat?.id ?? catRaw;
            router.push({ pathname: '/(tabs)/items', params: { category: categoryId } });
          }}
        />

        {/* Extended Portfolio Insights CTA */}
        <AnimatedPressable
          style={[styles.insightsCta, { backgroundColor: colors.card, borderColor: colors.border }]}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.push(limits.advanced_analytics ? '/analytics' : '/subscription');
          }}
          accessibilityRole="button"
          accessibilityLabel={limits.advanced_analytics ? "View extended portfolio insights" : "Upgrade for extended portfolio insights"}
        >
          <View style={styles.insightsCtaLeft}>
            <View style={[styles.insightsCtaIcon, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name={limits.advanced_analytics ? "analytics" : "lock-closed"} size={18} color={colors.accent} />
            </View>
            <View style={styles.insightsCtaTextBlock}>
              <Text style={[styles.insightsCtaTitle, { color: colors.text }]}>Extended Portfolio Insights</Text>
              <Text style={[styles.insightsCtaSub, { color: colors.muted }]}>
                {limits.advanced_analytics
                  ? "Deep analytics, trend forecasts & price alerts"
                  : "Unlock deep analytics, trend forecasts & price alerts"}
              </Text>
            </View>
          </View>
          <View style={[styles.insightsCtaBtn, { backgroundColor: colors.accent }]}>
            <Text style={styles.insightsCtaBtnText}>{limits.advanced_analytics ? "View" : "Upgrade"}</Text>
          </View>
        </AnimatedPressable>

        {/* Watchlist Card (always show - has empty state) */}
        {featureFlags.FEATURE_DATA_INSIGHTS_ALERTS && (
          <AlertsCard
            alerts={alerts}
            onAlertPress={(alert) => {
              markAsRead(alert.id);
              router.push({
                pathname: '/(tabs)/wishlist',
                params: { highlightId: alert.itemId || alert.id },
              } as any);
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
        <TopItemsList
          theme={colors}
          items={items}
          onItemPress={handleItemPress}
          formatPrice={(v) => formatPrice(v)}
          hapticsEnabled={settings.hapticsEnabled}
        />

        {/* Bottom spacing */}
        <View style={{ height: Platform.OS === "ios" ? 24 : 18 }} />
        </Animated.View>
      </ScrollView>

      {/* Add Item Menu (bottom sheet style) */}
      <Modal
        visible={addMenuOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setAddMenuOpen(false)}
      >
        <TouchableOpacity
          activeOpacity={1}
          onPress={() => setAddMenuOpen(false)}
          style={styles.addMenuOverlay}
          accessibilityRole="button"
          accessibilityLabel="Close add item menu"
        >
          <View style={[styles.addMenuSheet, { backgroundColor: colors.card, borderColor: colors.border }]} accessibilityViewIsModal={true} accessibilityRole="menu" accessibilityLabel="Add item menu">
            <View style={styles.addMenuHandle} />
            <TouchableOpacity
              onPress={() => { setAddMenuOpen(false); router.push('/quickscan'); }}
              style={styles.addMenuItem}
              accessibilityRole="button"
              accessibilityLabel="QuickScan AI"
            >
              <View style={[styles.addMenuIcon, { backgroundColor: colors.accent + '15' }]}>
                <Ionicons name="camera-outline" size={20} color={colors.accent} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.addMenuTitle, { color: colors.text }]}>QuickScan AI</Text>
                <Text style={[styles.addMenuSubtitle, { color: colors.muted }]}>Snap a photo, get instant valuation</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.muted} />
            </TouchableOpacity>
            <View style={[styles.addMenuDivider, { backgroundColor: colors.border }]} />
            <TouchableOpacity
              onPress={() => { setAddMenuOpen(false); router.push('/barcode-scan'); }}
              style={styles.addMenuItem}
              accessibilityRole="button"
              accessibilityLabel="Scan barcode"
            >
              <View style={[styles.addMenuIcon, { backgroundColor: colors.accent + '15' }]}>
                <Ionicons name="barcode-outline" size={20} color={colors.accent} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.addMenuTitle, { color: colors.text }]}>Scan Barcode</Text>
                <Text style={[styles.addMenuSubtitle, { color: colors.muted }]}>ISBN, EAN, or UPC</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.muted} />
            </TouchableOpacity>
            <View style={[styles.addMenuDivider, { backgroundColor: colors.border }]} />
            <TouchableOpacity
              onPress={() => { setAddMenuOpen(false); router.push('/add-manual'); }}
              style={styles.addMenuItem}
              accessibilityRole="button"
              accessibilityLabel="Add manually"
            >
              <View style={[styles.addMenuIcon, { backgroundColor: colors.accent + '15' }]}>
                <Ionicons name="create-outline" size={20} color={colors.accent} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.addMenuTitle, { color: colors.text }]}>Add Manually</Text>
                <Text style={[styles.addMenuSubtitle, { color: colors.muted }]}>Enter item details</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.muted} />
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
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
  notifBadge: {
    position: "absolute",
    top: 0,
    right: 0,
    backgroundColor: "#EF4444",
    borderRadius: 8,
    minWidth: 16,
    height: 16,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
  },
  notifBadgeText: {
    color: "#fff",
    fontSize: 9,
    fontWeight: "700",
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

  // Empty portfolio state
  emptyPortfolio: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 48,
    paddingHorizontal: 24,
  },
  emptyIconCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 24,
  },
  emptyHeadline: {
    fontSize: 24,
    fontWeight: "800",
    marginBottom: 8,
    textAlign: "center",
  },
  emptySubtitle: {
    fontSize: 15,
    lineHeight: 22,
    textAlign: "center",
    marginBottom: 28,
    maxWidth: 280,
  },
  emptyCta: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 16,
    paddingHorizontal: 32,
    borderRadius: 14,
    width: "100%",
    maxWidth: 280,
  },
  emptyCtaText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "700",
  },
  emptySecondary: {
    marginTop: 16,
    paddingVertical: 8,
  },
  emptySecondaryText: {
    fontSize: 15,
    fontWeight: "500",
    textDecorationLine: "underline",
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

  // Extended Portfolio Insights CTA
  insightsCta: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    marginBottom: 20,
  },
  insightsCtaLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
    marginRight: 12,
  },
  insightsCtaIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  insightsCtaTextBlock: {
    flex: 1,
  },
  insightsCtaTitle: {
    fontSize: 14,
    fontWeight: "700",
  },
  insightsCtaSub: {
    fontSize: 12,
    marginTop: 2,
  },
  insightsCtaBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  insightsCtaBtnText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "600",
  },

  // Add Banner (inline, replaces FAB)
  addBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderRadius: 14,
    borderWidth: 1,
    marginTop: 16,
    marginBottom: 4,
  },
  addBannerIconWrap: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addBannerText: {
    flex: 1,
    marginLeft: 12,
  },
  addBannerTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  addBannerSubtitle: {
    fontSize: 12,
    marginTop: 1,
  },

  // Add Menu (bottom sheet)
  addMenuOverlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.35)',
  },
  addMenuSheet: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderWidth: 1,
    borderBottomWidth: 0,
    paddingBottom: Platform.OS === 'ios' ? 34 : 20,
    paddingTop: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 10,
  },
  addMenuHandle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#D1D5DB',
    alignSelf: 'center',
    marginBottom: 16,
  },
  addMenuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  addMenuIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addMenuTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  addMenuSubtitle: {
    fontSize: 13,
    marginTop: 2,
  },
  addMenuDivider: {
    height: 1,
    marginHorizontal: 20,
  },

});

export default function PortfolioScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Portfolio">
      <PortfolioScreen />
    </ScreenErrorBoundary>
  );
}
