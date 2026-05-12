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
import { SkeletonPortfolioHeader } from "@/components/Skeleton";
import { dataProvider } from "@/data";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { ThemeToggleButton } from "@/components/ThemeToggleButton";
import { useAppTheme } from "@/hooks/useAppTheme";
import { featureFlags } from "@/config/featureFlags";
import { InsightsCard } from "@/components/home/InsightsCard";
import { AdBanner } from "@/components/ads/AdBanner";
import { AutoSetProgressList } from "@/components/AutoSetProgressList";
import { AlertsCard } from "@/components/home/AlertsCard";
import { PortfolioValueHeader } from "@/components/home/PortfolioValueHeader";
import { ChartRangeSelector } from "@/components/home/ChartRangeSelector";
import { type CategoryBreakdownItem } from "@/components/home/CategoryBreakdownSection";
import { getCategoryByName, getCategoryById } from "@/data/categories";
import { TopItemsList, type ItemRow } from "@/components/home/TopItemsList";
import { FollowedCategoriesCarousel } from "@/components/home/FollowedCategoriesCarousel";
import { usePortfolioInsights } from "@/hooks/usePortfolioInsights";
import { useAlertsFeed } from "@/hooks/useAlertsFeed";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useTranslation } from "react-i18next";
import { formatPrice } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { useBillingLimits } from "@/hooks/useBillingLimits";
import { collectorsApi, getNotificationHistory } from "@/api/collectorsApi";
import logger from "@/utils/logger";
import { useStoreReview } from "@/hooks/useStoreReview";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { AddMenuModal } from "@/components/home/AddMenuModal";
import { ValueSavedBanner } from "@/components/ValueSavedBanner";
import { useValueSummary } from "@/hooks/useValueSummary";
import { radius, spacing, text, fontWeight, gap, shadow } from '@/theme/tokens';

// Feature flag check: real mode when EXPO_PUBLIC_SUPABASE_MODE=real
const SUPABASE_MODE = process.env.EXPO_PUBLIC_SUPABASE_MODE ?? "mock";
const USE_REAL_BACKEND = SUPABASE_MODE === "real";

// Keep imports conservative and optional.
let analyticsApi: { fetchPortfolioSnapshot?: () => Promise<unknown>; [k: string]: unknown } | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  analyticsApi = require("@/store/portfolioAnalyticsStore");
} catch {
  analyticsApi = null;
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
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { limits } = useBillingLimits();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const valueSummary = useValueSummary();
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
    let cancelled = false;
    getNotificationHistory({ limit: 1, offset: 0 })
      .then((data) => { if (!cancelled) setUnreadNotifCount(data.unread_count); })
      .catch((err) => logger.warn('[Home] notification count fetch error:', err));
    return () => { cancelled = true; };
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
      if (USE_REAL_BACKEND) {
        try {
          const rangeParam = range.toLowerCase() as "1d" | "7d" | "30d" | "90d" | "1y" | "all";
          const timeseriesData = await collectorsApi.getPortfolioTimeseries(rangeParam);
          const extractedSeries = extractSeries(timeseriesData);
          if (extractedSeries.length) {
            setSeries(extractedSeries);
          } else {
            setSeries([]);
          }

          const overviewData = await collectorsApi.getPortfolioOverview();
          const extractedItems = extractItems(overviewData);
          if (extractedItems.length) {
            setItems(extractedItems.sort((a, b) => b.value - a.value));
          } else {
            setItems([]);
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
            const snap = await analyticsApi.fetchPortfolioSnapshot() as Record<string, unknown> | undefined;
            const extractedSeries = extractSeries((snap as Record<string, unknown>)?.series || snap);
            const extractedItems = extractItems(snap);

            baseSeries = extractedSeries.length ? extractedSeries : [];
            baseItems = extractedItems.length
              ? extractedItems.sort((a, b) => b.value - a.value)
              : [];
            if ((snap as Record<string, unknown>)?.tierSummary) setTierSummary((snap as Record<string, unknown>).tierSummary as typeof tierSummary);
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
    let cancelled = false;
    setBreakdownLoading(true);
    collectorsApi.getPortfolioCategoryBreakdown()
      .then((res: unknown) => {
        if (cancelled) return;
        const data = res as Record<string, unknown>;
        // Backend returns "breakdown", also check "categories" for compat
        const cats = Array.isArray(data?.breakdown)
          ? (data.breakdown as Record<string, unknown>[]).map((b) => ({
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
        logger.warn('[Portfolio] category breakdown fetch failed:', err);
        if (!cancelled) setCategoryBreakdown([]);
      })
      .finally(() => { if (!cancelled) setBreakdownLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // Load followed categories from onboarding
  useEffect(() => {
    let cancelled = false;
    // Try local storage first (faster), then backend
    AsyncStorage.getItem('@sparrowcollect/followed_categories')
      .then((raw) => {
        if (cancelled) return;
        if (raw) {
          try {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed) && parsed.length > 0) {
              setFollowedCategories(parsed);
            }
          } catch {}
        }
      })
      .catch((err) => logger.warn('[Home] followed categories local fetch error:', err));

    // Also try backend (more authoritative)
    collectorsApi.getFollowedCategories()
      .then((data) => {
        if (!cancelled && data?.followed_categories?.length) {
          setFollowedCategories(data.followed_categories);
        }
      })
      .catch((err) => logger.warn('[Home] followed categories backend fetch error:', err));
    return () => { cancelled = true; };
  }, []);

  // Memoize global stats derived from category breakdown
  const globalStatsTotalItems = useMemo(
    () => categoryBreakdown.reduce((sum, c) => sum + c.item_count, 0),
    [categoryBreakdown],
  );
  const globalStatsTotalValue = useMemo(
    () => categoryBreakdown.reduce((sum, c) => sum + c.total_value, 0),
    [categoryBreakdown],
  );

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setRefreshing(false);
  }, [loadData, settings.hapticsEnabled]);

  // Determine if positive or negative
  const isPositive = deltaPct >= 0;

  const rangeButtons: RangeKey[] = ["1D", "7D", "30D", "90D", "1Y", "ALL"];

  // Navigation handlers (useCallback to prevent re-renders in child components)
  const handleOpenNotifications = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push('/notifications');
  }, [router, settings.hapticsEnabled]);

  const handleOpenSettings = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push('/settings');
  }, [router, settings.hapticsEnabled]);

  const handleOpenAddMenu = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setAddMenuOpen(true);
  }, [settings.hapticsEnabled]);

  const handleOpenQuickScan = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push('/quickscan');
  }, [router, settings.hapticsEnabled]);

  const handleOpenManualAdd = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push('/add-manual');
  }, [router, settings.hapticsEnabled]);

  const handleCategoryPress = useCallback((catSlug: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push({ pathname: '/categories/[categoryId]', params: { categoryId: catSlug } });
  }, [router, settings.hapticsEnabled]);

  const handleBreakdownCategoryPress = useCallback((catRaw: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const cat = getCategoryById(catRaw) ?? getCategoryByName(catRaw);
    const categoryId = cat?.id ?? catRaw;
    router.push({ pathname: '/(tabs)/items', params: { category: categoryId } });
  }, [router, settings.hapticsEnabled]);

  const handleInsightsCtaPress = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push('/analytics');
  }, [router, settings.hapticsEnabled]);

  const handleAlertPress = useCallback((alert: { id: string; itemId?: string }) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    markAsRead(alert.id);
    router.push({
      pathname: '/(tabs)/wishlist',
      params: { highlightId: alert.itemId || alert.id },
    });
  }, [router, markAsRead, settings.hapticsEnabled]);

  const handleDealAgentPress = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push(limits.deal_discovery ? "/purchase" : "/subscription");
  }, [router, settings.hapticsEnabled, limits.deal_discovery]);

  // Navigate to item detail
  const handleItemPress = useCallback((item: ItemRow) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push({
      pathname: "/item/[id]",
      params: {
        id: item.id,
        name: item.name,
        category: item.category ?? "",
        value: String(item.value),
      },
    });
  }, [router, settings.hapticsEnabled]);

  // Navigate to analytics
  const handleAnalyticsPress = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push("/analytics");
  }, [router, settings.hapticsEnabled]);

  // Navigate to watchlist tab
  const handleWatchlistPress = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push("/(tabs)/wishlist");
  }, [router, settings.hapticsEnabled]);

  return (
    <>
    {valueSummary.data && (
      <ValueSavedBanner
        data={valueSummary.data}
        visible={valueSummary.visible}
        trigger={valueSummary.trigger}
        onDismiss={valueSummary.dismiss}
      />
    )}
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
            <Text style={[styles.headerTitle, { color: colors.text }]}>{t('home.portfolio_title')}</Text>
            <Text style={[styles.headerSubtitle, { color: colors.muted }]}>{t('home.portfolio_subtitle')}</Text>
          </View>
          <View style={styles.headerIcons}>
            <AnimatedPressable
              onPress={handleOpenNotifications}
              style={styles.iconBtnRelative}
              accessibilityRole="button"
              accessibilityLabel={`Notifications${unreadNotifCount > 0 ? `, ${unreadNotifCount} unread` : ''}`}
            >
              <Ionicons name="notifications-outline" size={22} color={colors.text} />
              {unreadNotifCount > 0 && (
                <View style={[styles.notifBadge, { backgroundColor: colors.error }]}>
                  <Text style={[styles.notifBadgeText, { color: colors.accentText }]}>
                    {unreadNotifCount > 99 ? '99+' : unreadNotifCount}
                  </Text>
                </View>
              )}
            </AnimatedPressable>
            <InboxHeaderButton color={colors.text} size={22} />
            <ThemeToggleButton size={22} />
            <AnimatedPressable
              testID="open-settings-btn"
              onPress={handleOpenSettings}
              style={styles.iconBtn}
              accessibilityRole="button"
              accessibilityLabel={t('home.open_settings_a11y')}
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
            <Text style={[styles.emptyHeadline, { color: colors.text }]}>{t('home.start_collection')}</Text>
            <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
              {t('home.start_collection_subtitle')}
            </Text>
            <AnimatedPressable
              style={[styles.emptyCta, { backgroundColor: colors.accent }]}
              onPress={handleOpenQuickScan}
              accessibilityRole="button"
              accessibilityLabel={t('home.open_quickscan_a11y')}
            >
              <Ionicons name="camera" size={20} color={colors.accentText} style={styles.iconMarginRight} />
              <Text style={[styles.emptyCtaText, { color: colors.accentText }]}>{t('home.quickscan_ai')}</Text>
            </AnimatedPressable>
            <AnimatedPressable
              style={styles.emptySecondary}
              onPress={handleOpenManualAdd}
              accessibilityRole="button"
              accessibilityLabel={t('home.add_manually_a11y')}
            >
              <Text style={[styles.emptySecondaryText, { color: colors.muted }]}>{t('home.or_add_manually')}</Text>
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
              tier={tierSummary?.tier}
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
          onPress={handleOpenAddMenu}
          style={[styles.addBanner, { backgroundColor: colors.accent + '0D', borderColor: colors.accent + '30' }]}
          accessibilityRole="button"
          accessibilityLabel={t('home.add_to_collection_a11y')}
        >
          <View style={[styles.addBannerIconWrap, { backgroundColor: colors.accent }]}>
            <Ionicons name="add" size={18} color={colors.accentText} />
          </View>
          <View style={styles.addBannerText}>
            <Text style={[styles.addBannerTitle, { color: colors.text }]}>{t('home.add_to_collection')}</Text>
            <Text style={[styles.addBannerSubtitle, { color: colors.muted }]}>{t('home.add_to_collection_subtitle')}</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.accent} />
        </AnimatedPressable>

        {/* Personalized Categories (from onboarding) */}
        <FollowedCategoriesCarousel
          theme={colors}
          categories={followedCategories}
          onCategoryPress={handleCategoryPress}
          hapticsEnabled={settings.hapticsEnabled}
        />

        {/* Category Breakdown lives on the items tab (moved 2026-04-18). */}

        {/* Global Collection Stats */}
        {categoryBreakdown.length > 0 && (
          <View style={[styles.globalStats, { borderColor: colors.border }]}>
            <View style={styles.globalStatItem}>
              <Text style={[styles.globalStatValue, { color: colors.text }]}>{categoryBreakdown.length}</Text>
              <Text style={[styles.globalStatLabel, { color: colors.muted }]}>{t('home.categories')}</Text>
            </View>
            <View style={[styles.globalStatDivider, { backgroundColor: colors.border }]} />
            <View style={styles.globalStatItem}>
              <Text style={[styles.globalStatValue, { color: colors.text }]}>
                {globalStatsTotalItems}
              </Text>
              <Text style={[styles.globalStatLabel, { color: colors.muted }]}>{t('home.total_items')}</Text>
            </View>
            <View style={[styles.globalStatDivider, { backgroundColor: colors.border }]} />
            <View style={styles.globalStatItem}>
              <Text style={[styles.globalStatValue, { color: colors.accent }]}>
                {formatPrice(globalStatsTotalValue)}
              </Text>
              <Text style={[styles.globalStatLabel, { color: colors.muted }]}>{t('home.portfolio')}</Text>
            </View>
          </View>
        )}

        {/* Extended Portfolio Insights CTA */}
        <AnimatedPressable
          style={[styles.insightsCta, { backgroundColor: colors.card, borderColor: colors.border }]}
          onPress={handleInsightsCtaPress}
          accessibilityRole="button"
          accessibilityLabel={limits.advanced_analytics ? t('home.insights_view_a11y') : t('home.insights_upgrade_a11y')}
        >
          <View style={styles.insightsCtaLeft}>
            <View style={[styles.insightsCtaIcon, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name={limits.advanced_analytics ? "analytics" : "lock-closed"} size={18} color={colors.accent} />
            </View>
            <View style={styles.insightsCtaTextBlock}>
              <Text style={[styles.insightsCtaTitle, { color: colors.text }]}>{t('home.extended_insights')}</Text>
              <Text style={[styles.insightsCtaSub, { color: colors.muted }]}>
                {limits.advanced_analytics
                  ? t('home.extended_insights_active')
                  : t('home.extended_insights_locked')}
              </Text>
            </View>
          </View>
          <View style={[styles.insightsCtaBtn, { backgroundColor: colors.accent }]}>
            <Text style={[styles.insightsCtaBtnText, { color: colors.accentText }]}>{limits.advanced_analytics ? t('home.view') : t('home.upgrade')}</Text>
          </View>
        </AnimatedPressable>

        {/* Watchlist Card (always show - has empty state) */}
        {featureFlags.FEATURE_DATA_INSIGHTS_ALERTS && (
          <AlertsCard
            alerts={alerts}
            onAlertPress={handleAlertPress}
            onStartWatchlist={handleWatchlistPress}
            showEmptyState={true}
          />
        )}

        {/* Deal Agent Summary Card */}
        <AnimatedPressable
          style={[styles.analyticsBanner, { backgroundColor: colors.card, borderColor: colors.border }]}
          onPress={handleDealAgentPress}
          accessibilityRole="button"
          accessibilityLabel={limits.deal_discovery ? t('home.deal_agent_open_a11y') : t('home.deal_agent_upgrade_a11y')}
        >
          <View style={styles.analyticsBannerLeft}>
            <View style={[styles.analyticsIconWrap, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name={limits.deal_discovery ? "flash" : "lock-closed"} size={18} color={colors.accent} />
            </View>
            <View style={styles.analyticsBannerText}>
              <Text style={[styles.analyticsBannerTitle, { color: colors.text }]}>{t('home.deal_agent')}</Text>
              <Text style={[styles.analyticsBannerSubtitle, { color: colors.muted }]}>
                {limits.deal_discovery ? t('home.deal_agent_active') : t('home.deal_agent_locked')}
              </Text>
            </View>
          </View>
          <View style={[styles.analyticsBannerBtn, { backgroundColor: colors.accent }]}>
            <Text style={[styles.analyticsBannerBtnText, { color: colors.accentText }]}>{limits.deal_discovery ? t('home.view') : t('home.upgrade')}</Text>
          </View>
        </AnimatedPressable>

        {/* Hot Right Now moved to Analytics (paywall-gated) 2026-04-18. */}

        {/* Auto-detected set completion (uses structured attributes_json) */}
        <AutoSetProgressList limit={5} />

        {/* Ad slot — invisible until FEATURE_ADS is enabled */}
        <AdBanner placement="portfolio_banner" />

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

      <AddMenuModal visible={addMenuOpen} onClose={() => setAddMenuOpen(false)} />
    </SafeAreaView>
    </>
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
    fontSize: text['2xl'],
    fontWeight: fontWeight.bold,
  },
  headerSubtitle: {
    fontSize: text.sm,
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
    borderRadius: radius.xs,
    minWidth: 16,
    height: 16,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 3,
  },
  notifBadgeText: {
    fontSize: 9,
    fontWeight: fontWeight.bold,
  },
  // Chart card
  chartCard: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 16,
    marginBottom: 16,
    minHeight: 220,
    ...shadow.card,
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 190,
  },
  loadingText: {
    fontSize: text.sm,
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
    fontSize: text['2xl'],
    fontWeight: fontWeight.extrabold,
    marginBottom: 8,
    textAlign: "center",
  },
  emptySubtitle: {
    fontSize: text.lg,
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
    borderRadius: radius.lg,
    width: "100%",
    maxWidth: 280,
  },
  emptyCtaText: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
  },
  emptySecondary: {
    marginTop: 16,
    paddingVertical: 8,
  },
  emptySecondaryText: {
    fontSize: text.lg,
    fontWeight: fontWeight.medium,
    textDecorationLine: "underline",
  },

  // Error
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: radius.xs,
    marginBottom: 12,
  },
  errorText: {
    fontSize: text.sm,
    fontWeight: fontWeight.medium,
  },

  // Mode indicator (dev)
  modeIndicator: {
    fontSize: text.xs,
    textAlign: "center",
    marginBottom: 8,
  },

  // Analytics Banner
  analyticsBanner: {
    borderWidth: 1,
    borderRadius: radius.md,
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
    borderRadius: radius.xs,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  analyticsBannerText: {
    flex: 1,
  },
  analyticsBannerTitle: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    marginBottom: 2,
  },
  analyticsBannerSubtitle: {
    fontSize: text.sm,
  },
  analyticsBannerBtn: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: radius.xs,
    marginLeft: 12,
  },
  analyticsBannerBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },

  // Section header
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: text.xl,
    fontWeight: fontWeight.extrabold,
  },

  // Global Collection Stats
  globalStats: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingVertical: 12,
    marginBottom: 16,
  },
  globalStatItem: {
    alignItems: "center",
  },
  globalStatValue: {
    fontSize: text.xl,
    fontWeight: fontWeight.extrabold,
  },
  globalStatLabel: {
    fontSize: text.sm,
    marginTop: 2,
  },
  globalStatDivider: {
    width: 1,
    height: 28,
  },

  // Extended Portfolio Insights CTA
  insightsCta: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderWidth: 1,
    borderRadius: radius.md,
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
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  insightsCtaTextBlock: {
    flex: 1,
  },
  insightsCtaTitle: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
  },
  insightsCtaSub: {
    fontSize: text.sm,
    marginTop: 2,
  },
  insightsCtaBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: radius.xs,
  },
  insightsCtaBtnText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },

  // Add Banner (inline, replaces FAB)
  addBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderRadius: radius.lg,
    borderWidth: 1,
    marginTop: 16,
    marginBottom: 4,
  },
  addBannerIconWrap: {
    width: 34,
    height: 34,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addBannerText: {
    flex: 1,
    marginLeft: 12,
  },
  addBannerTitle: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
  },
  addBannerSubtitle: {
    fontSize: text.sm,
    marginTop: 1,
  },

  // Extracted inline styles
  iconBtn: {
    padding: 4,
  },
  iconBtnRelative: {
    padding: 4,
    position: "relative",
  },
  iconMarginRight: {
    marginRight: 8,
  },
});

export default function PortfolioScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Portfolio" fallbackMessage="Your portfolio data could not be displayed. Check your connection and try again.">
      <PortfolioScreen />
    </ScreenErrorBoundary>
  );
}
