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
import { useRouter, useFocusEffect } from "expo-router";
import { useAuthContext } from "@/providers/useAuthContext";
import { PortfolioLineChart, type TimeSeriesPoint } from "@/components/PortfolioLineChart";
import { SkeletonPortfolioHeader } from "@/components/Skeleton";
import { dataProvider } from "@/data";
import { HeaderActions } from '@/components/HeaderActions';
import { useAppTheme } from "@/hooks/useAppTheme";
import { useTabBarInset } from "@/hooks/useTabBarInset";
import { featureFlags } from "@/config/featureFlags";
import { AdBanner } from "@/components/ads/AdBanner";
import { AutoSetProgressList } from "@/components/AutoSetProgressList";
import { AlertsCard } from "@/components/home/AlertsCard";
import { PortfolioValueHeader } from "@/components/home/PortfolioValueHeader";
import { ChartRangeSelector } from "@/components/home/ChartRangeSelector";
import { CategoryBreakdownSection, type CategoryBreakdownItem } from "@/components/home/CategoryBreakdownSection";
import { mapCategoryBreakdown } from "@/lib/categoryBreakdown";
import { OpenBidsRow } from "@/components/home/OpenBidsRow";
import { formatCategoryName } from "@/constants/categories";
import { getCategoryByName, getCategoryById } from "@/data/categories";
// The Collection block (header + Top Movers list) was removed from Portfolio
// 2026-08-11. `ItemRow` stays: it types loadItemsFromCollection, extractItems
// and the `items` state that still drives the value chart and stats tile.
import { type ItemRow } from "@/components/home/TopItemsList";
import { useHasEverHadItems } from "@/hooks/useHasEverHadItems";
import { StartCollectingCard } from "@/components/home/StartCollectingCard";
import { useAlertsFeed } from "@/hooks/useAlertsFeed";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useTranslation } from "react-i18next";
import { formatPrice } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { useBillingLimits } from "@/hooks/useBillingLimits";
import { collectorsApi } from "@/api/collectorsApi";
import logger from "@/utils/logger";
import { useStoreReview } from "@/hooks/useStoreReview";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { AddMenuModal } from "@/components/home/AddMenuModal";
import { ValueSavedBanner } from "@/components/ValueSavedBanner";
import { useValueSummary } from "@/hooks/useValueSummary";
import { radius, spacing, text, fontWeight, gap, shadow } from '@/theme/tokens';

// Real backend whenever mode is not "mock" / "off". `eas.json` ships
// production builds with mode=`strict` (per src/api/config.ts guidance);
// the old `=== "real"` check silently dropped them onto MockDataProvider.
const SUPABASE_MODE = (process.env.EXPO_PUBLIC_SUPABASE_MODE ?? "mock").toLowerCase();
const USE_REAL_BACKEND = SUPABASE_MODE !== "mock" && SUPABASE_MODE !== "off";

// Keep imports conservative and optional.
let analyticsApi: { fetchPortfolioSnapshot?: () => Promise<unknown>; [k: string]: unknown } | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  analyticsApi = require("@/store/portfolioAnalyticsStore");
} catch (e) {
  logger.error('[silent-catch] index.tsx:73:', e);
  analyticsApi = null;
}

type RangeKey = "1D" | "7D" | "30D" | "90D" | "1Y" | "ALL";

/** Above this item count the "Add to Collection" banner stops rendering — see
 *  the comment at its call site. The Add tab remains the permanent entry point. */
const ADD_BANNER_MAX_ITEMS = 3;



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
          : // Backend /portfolio/overview returns snake_case current_value.
          typeof it?.current_value === "number"
          ? it.current_value
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
          : // Backend /portfolio/overview returns snake_case change_1d_pct.
          typeof it?.change_1d_pct === "number"
          ? it.change_1d_pct
          : typeof it?.pctChange === "number"
          ? it.pctChange
          : undefined;

      const category = it?.category ? String(it.category) : undefined;

      if (!Number.isFinite(value)) return null;
      return { id, name, category, value, changePct };
    })
    .filter(Boolean) as ItemRow[];
}

/**
 * Load the collection from the SAME source the Items tab uses.
 *
 * Home and Items read from two different places: Home calls the EC2 API
 * (/portfolio/overview, which needs a JWT and reads items.name), while the
 * Items tab reads Supabase directly through dataProvider.listItems() under RLS.
 * So the two tabs can — and did — disagree: items added manually showed up on
 * Items while Home said the collection was empty.
 *
 * The API path fails empty in several ordinary situations: a request that goes
 * out before the auth token has hydrated (401), a cold EC2, or any network
 * blip. Every one of those hit `setItems([])`, which renders as "no items"
 * rather than as an error — indistinguishable, to the user, from an empty
 * collection.
 *
 * `listItems` is already withTimeout-bounded internally (itemsProvider.ts:144),
 * so this cannot hang the screen.
 */
/** The page Home reads. ONE constant, because the estimated-share caption is
 *  only honest while this many rows is the whole collection — two literals
 *  that must agree is how a capped aggregate comes back. */
export const HOME_ITEMS_PAGE = 50;

async function loadItemsFromCollection(): Promise<ItemRow[]> {
  try {
    const items = await dataProvider.listItems({ limit: HOME_ITEMS_PAGE, offset: 0 });
    return (items ?? [])
      .map((it) => ({
        id: String(it.id),
        name: it.name || 'Untitled',
        category: it.category || undefined,
        value: Number(it.price ?? 0),
        changePct: undefined,
        valueSource: it.valueSource ?? undefined,
      }))
      .filter((r) => Number.isFinite(r.value));
  } catch (e) {
    logger.error('[Portfolio] Items-tab fallback failed:', e);
    return [];
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

function PortfolioScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  // ExternalTabBar is absolute at the root stack and reserves no layout space,
  // so a literal paddingBottom here draws the last row under the bar. Derive it.
  const bottomInset = useTabBarInset();
  const { settings } = useSettings();
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { limits } = useBillingLimits();
  // useEnterReveal removed 2026-05-25 — its translateY animation with
  // useNativeDriver:true was leaving the home tab's hit area desynced from
  // the rendered position on first mount, blocking taps on the bottom tab
  // bar until the user scrolled (which forced a re-layout). Symptom only
  // showed on the Portfolio tab because it was the only one using this hook
  // with a translateY. Pure cosmetic loss, no functional impact.

  const valueSummary = useValueSummary();
  const [range, setRange] = useState<RangeKey>("7D");
  const [series, setSeries] = useState<TimeSeriesPoint[]>([]);
  // Why the series is empty. The chart renders "No history yet" for an empty
  // array, so without this a failed request (classically a cold-start 401 —
  // see project_2026_07_14_401_root_cause_tokenless) is displayed as "you have
  // no history", which is a different and wrong statement. VERIFIED 2026-08-05:
  // the API returns points for every range (1d=2 … all=3651), so an empty
  // series on this screen is a transport failure, not absent data.
  const [seriesFailed, setSeriesFailed] = useState(false);
  const [items, setItems] = useState<ItemRow[]>([]);
  /**
   * How much of the headline is NOT comp-backed (decided 2026-08-19:
   * include-and-mark, never hide).
   *
   * ⚠️ CAPPED-AGGREGATE GUARD. `loadItemsFromCollection` asks for 50 items, so
   * on a larger collection this list is a PAGE, not the portfolio. Printing a
   * money figure from it would report a partial number as the whole truth —
   * the exact class `npm run verify:silent` names. So the caption renders only
   * when we can prove we hold everything: fewer rows came back than we asked
   * for. At exactly the page size there may be one more, and we say nothing.
   */
  // Persisted "has ever had items" flag. Drives the first-item hero: it shows
  // ONLY for a genuinely-new collection and is replaced by the graph the moment
  // the first item is added — and never comes back, even if a later portfolio
  // fetch transiently returns empty (a token cold-start / network blip must not
  // resurrect "add your first item" for an established collection).
  const { hasEverHadItems, markHasItems } = useHasEverHadItems();
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tierSummary, setTierSummary] = useState<{ tier: 'Diamond' | 'Gold' | 'Silver' | 'Unranked'; rarityScore: number; completenessScore: number; diversificationScore: number } | null>(null);

  // Store review prompt (criteria: 10+ items, 3+ days, 90-day cooldown)
  useStoreReview(items.length);

  // Once the portfolio has ever shown items, remember it permanently so the
  // first-item hero never resurfaces on a later empty fetch.
  useEffect(() => {
    if (items.length > 0) markHasItems();
  }, [items.length, markHasItems]);

  // Category breakdown state
  const [categoryBreakdown, setCategoryBreakdown] = useState<CategoryBreakdownItem[]>([]);
  const [breakdownLoading, setBreakdownLoading] = useState(false);


  // Point under the user's finger on the chart. Drives the big COLLECTION VALUE
  // figure so it moves with the scrubber; null means "not scrubbing", and the
  // header falls back to the portfolio total.
  const [scrubPoint, setScrubPoint] = useState<TimeSeriesPoint | null>(null);


  // `usePortfolioInsights` went with the card on 2026-08-27. Its ONLY reader
  // was <InsightsCard/>; keeping the call would leave a fetch on every Home
  // open whose result nothing renders, which is the dead-path shape this
  // codebase keeps rediscovering. `useAlertsFeed` below is separate and stays.

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

  const { loading: authLoading } = useAuthContext();


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
          setSeries(extractedSeries);
          // The call succeeded. An empty result here really is "no history".
          setSeriesFailed(false);

          const overviewData = await collectorsApi.getPortfolioOverview();
          const extractedItems = extractItems(overviewData);
          if (extractedItems.length) {
            setItems(extractedItems.sort((a, b) => b.value - a.value));
          } else {
            // The API said "no items". Before believing it, ask the source the
            // Items tab uses — an empty answer here is far more often a
            // tokenless/cold-start 401 than an actually empty collection, and
            // the two are indistinguishable on screen.
            const fallback = await loadItemsFromCollection();
            setItems(fallback.sort((a, b) => b.value - a.value));
          }
        } catch (realErr: unknown) {
          logger.error("[Portfolio] Real backend error, falling back:", realErr);
          setSeries([]);
          setSeriesFailed(true);
          // Same fallback on a hard failure. Only surface an error if the
          // collection genuinely cannot be read either way — otherwise Home
          // showed "Could not load portfolio data" over a collection the Items
          // tab was displaying perfectly well.
          const fallback = await loadItemsFromCollection();
          setItems(fallback.sort((a, b) => b.value - a.value));
          if (!fallback.length) setError("Could not load portfolio data.");
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
            logger.error("[Portfolio] Mock store error:", mockErr);
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
      logger.error("[Portfolio] Unexpected error:", err);
      setError("Failed to load portfolio data.");
      setSeries([]);
      setSeriesFailed(true);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [range]);

  // Refetch on FOCUS, not just mount. The first mount fires during the
  // post-login tokenless cold-start window, when the EC2 portfolio endpoints
  // (getPortfolioTimeseries/getPortfolioOverview) return empty because
  // getAuthHeaders has no token yet → Home would otherwise show
  // "add your first item" + no graph permanently, diverging from the Items tab
  // (which reads Supabase directly AND already refetches on focus via
  // useFocusEffect). Refetching on focus repopulates Home once the token lands.
  useFocusEffect(
    useCallback(() => {
      // Wait for the session to hydrate before the first load. Firing during the
      // tokenless cold-start window does not fail fast: getAuthHeaders burns its
      // 6s refresh window, the request then goes out unauthenticated and 401s,
      // and `loading` — and therefore the chart skeleton — stays up for the whole
      // round. Measured on the simulator 2026-07-25: still skeletonised 30s
      // after launch. useFocusEffect re-runs when authLoading flips, so the load
      // fires as soon as the session lands.
      if (authLoading) return;
      loadData();
    }, [loadData, authLoading]),
  );

  // Category breakdown. Extracted from the focus effect so pull-to-refresh can
  // fire it too: it used to refresh ONLY on focus while the header + chart came
  // from loadData(), so any path that updated the portfolio without blurring
  // Home left the two showing different totals. Observed 2026-08-03 — the
  // header read EUR 8.070 while the summary strip below it still read EUR 55,
  // and the backend was innocent: /portfolio/overview and
  // /portfolio/category-stats both returned 8,070.04 when queried directly.
  const loadCategoryBreakdown = useCallback(async () => {
    setBreakdownLoading(true);
    try {
      const res: unknown = await collectorsApi.getPortfolioCategoryBreakdown();
      const cats = mapCategoryBreakdown(res);
      setCategoryBreakdown(cats);
    } catch (err: unknown) {
      // logger.error, not warn — warn is stripped in release builds, so this
      // failure was invisible on exactly the builds where it matters. The
      // catch also resets the breakdown to [], which renders as "no
      // categories" and is indistinguishable from a genuinely empty
      // portfolio; without a surviving trace there is nothing to tell them
      // apart after the fact.
      logger.error('[Portfolio] category breakdown fetch failed:', err);
      setCategoryBreakdown([]);
    } finally {
      setBreakdownLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadCategoryBreakdown();
    }, [loadCategoryBreakdown]),
  );

  // The followed-categories carousel was removed from Portfolio 2026-08-11.
  // Its loader went with it: an AsyncStorage read plus a
  // collectorsApi.getFollowedCategories() call on every Portfolio mount, whose
  // result nothing rendered any more. Onboarding still WRITES the preference —
  // this screen just no longer reads it.

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
    // Both, together. Refreshing only loadData() updated the header and chart
    // while leaving the summary strip on its last focus-time value, which is
    // how one screen came to show two different portfolio totals.
    await Promise.all([loadData(), loadCategoryBreakdown()]);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setRefreshing(false);
  }, [loadData, loadCategoryBreakdown, settings.hapticsEnabled]);

  // Determine if positive or negative
  const isPositive = deltaPct >= 0;

  // The not-comp-backed share of the collection. See HOME_ITEMS_PAGE above for
  // why this is suppressed on a collection larger than one page.
  const estimatedShare = useMemo(() => {
    if (items.length === 0 || items.length >= HOME_ITEMS_PAGE) return null;
    // "We do not know" is not "it is all estimated". If NOT ONE item carries a
    // provenance — the view read failed, or a caller mapped its own item shape
    // — every row would look unbacked and the caption would claim the whole
    // portfolio is guesswork. Say nothing instead.
    if (!items.some((it) => typeof it.valueSource === 'string' && it.valueSource)) {
      return null;
    }
    const MARKET = new Set(['catalog_daily', 'catalog_model', 'quick_scan']);
    let total = 0;
    let count = 0;
    for (const it of items) {
      if (MARKET.has(it.valueSource ?? '')) continue;
      total += Number(it.value ?? 0);
      count += 1;
    }
    if (count === 0 || total <= 0) return null;
    return { total, count };
  }, [items]);

  const rangeButtons: RangeKey[] = ["1D", "7D", "30D", "90D", "1Y", "ALL"];

  // Navigation handlers (useCallback to prevent re-renders in child components)

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

  const handleBreakdownCategoryPress = useCallback((catRaw: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    const cat = getCategoryById(catRaw) ?? getCategoryByName(catRaw);
    const categoryId = cat?.id ?? catRaw;
    router.push({ pathname: '/(tabs)/items', params: { category: categoryId } });
  }, [router, settings.hapticsEnabled]);

  /*
   * The whole collection, unfiltered, A-Z.
   *
   * `sort: 'name_asc'` is a real contract, not decoration: the items screen
   * defaults to `value_desc`, and "scroll through the collection" is an
   * alphabetical act, not a rich-first one. The destination READS this param
   * (see the lazy initialiser in items.tsx) — `npm run check:params` compares
   * against the target's declared params, so a param the screen ignored would
   * fail the build rather than be silently dropped.
   */
  const handleAllItemsPress = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push({ pathname: '/(tabs)/items', params: { sort: 'name_asc' } });
  }, [router, settings.hapticsEnabled]);

  const handleAlertPress = useCallback((alert: { id: string; itemId?: string }) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    markAsRead(alert.id);
    router.push({
      pathname: '/(tabs)/wishlist',
      params: { highlightId: alert.itemId || alert.id },
    });
  }, [router, markAsRead, settings.hapticsEnabled]);

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
        contentContainerStyle={[styles.container, { backgroundColor: colors.background, paddingBottom: bottomInset }]}
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
        <View>
        {/* Header */}
        <View style={styles.headerRow}>
          <View style={styles.headerLeft}>
            <Text style={[styles.headerTitle, { color: colors.text }]}>{t('home.portfolio_title')}</Text>
            <Text style={[styles.headerSubtitle, { color: colors.muted }]}>{t('home.portfolio_subtitle')}</Text>
          </View>
          <HeaderActions />
        </View>

        {/* "3 bids need you →", and nothing at all otherwise.

            `countOffersNeedingAction` had ONE caller — the badge on
            app/listings.tsx — so a bid waiting on an answer was invisible
            unless you opened the Marketplace tab. It sits ABOVE the chart
            rather than at the bottom of the scroll: the bottom of Home is
            where the set-progress list and the ad slot live, and the most
            time-sensitive thing in the app does not belong where nobody
            scrolls. See the component for why it is a row and not a card. */}
        <OpenBidsRow />

        {/* Beginner entry point. Renders itself away unless skill_level is
            literally 'beginner' and a guide exists to open — see the component.
            Above the first-item hero because "what should I even buy" comes
            before "photograph the thing you bought". */}
        <StartCollectingCard />

        {/* First-item hero ONLY for a genuinely-new collection (confirmed never
            had items), else the Collection value + chart. Keyed on the persisted
            hasEverHadItems===false rather than the live items array so a token
            cold-start / transient empty fetch can't resurrect the hero for an
            established portfolio — and the hero is replaced by the graph the
            instant the first item is added. */}
        {items.length === 0 && hasEverHadItems === false ? (
          <View style={styles.emptyPortfolio}>
            <View style={[styles.emptyIconCircle, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name="camera-outline" size={64} color={colors.accent} />
            </View>
            <Text style={[styles.emptyHeadline, { color: colors.text }]}>
              {t('home.add_first_item', { defaultValue: 'Add your first item' })}
            </Text>
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
              total={scrubPoint ? scrubPoint.v : total}
              delta={delta}
              deltaPct={deltaPct}
              currency={settings.currency}
              formatPrice={formatPrice}
              // Counter animation is a tween to a target; while scrubbing the
              // target changes every few ms, so it lags the finger. Snap instead.
              animationsEnabled={settings.animationsEnabled && !scrubPoint}
              tier={tierSummary?.tier}
            />

            {/* Include AND mark. The headline sums comp-backed values and
                members' own estimates together, which is right — for the 40+
                categories with no sold-comp source the estimate is all anyone
                has, and dropping it would show a collection worth less than
                the member knows it is. What was missing was saying so. */}
            {estimatedShare ? (
              <Text style={[styles.estimatedNote, { color: colors.muted }]}>
                {formatPrice(estimatedShare.total, settings.currency)} of this is
                estimated — {estimatedShare.count} item
                {estimatedShare.count === 1 ? '' : 's'} we have no market comps for
              </Text>
            ) : null}

            {/* Range Toggles */}
            <ChartRangeSelector
              theme={colors}
              selectedRange={range}
              ranges={rangeButtons}
              onRangeChange={(k) => setRange(k as RangeKey)}
              hapticsEnabled={settings.hapticsEnabled}
            />

            {/* Chart Card with Interactive Line Chart */}
            <View style={[styles.chartCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            {/* The image role stays scoped to the CHART. It used to wrap the
                whole card; with a button inside the card, that would have
                announced an interactive control as part of an image. */}
            <View
              accessibilityRole="image"
              accessibilityLabel={`Portfolio chart: current value ${formatPrice(total)}, ${isPositive ? 'up' : 'down'} ${formatPct(deltaPct)} over ${range}`}
            >
              {loading ? (
                <SkeletonPortfolioHeader />
              ) : (
                <PortfolioLineChart
                  series={series}
                  loadFailed={seriesFailed}
                  onRetry={loadData}
                  accentColor={colors.accent}
                  showValueHeader={true}
                  showAxisLabels={true}
                  axisLabelColor={colors.muted}
                  gridColor={colors.border}
                  textColor={colors.text}
                  dotFillColor={colors.card}
                  onScrubChange={setScrubPoint}
                />
              )}
            </View>

            {/* Analytics entry point, INSIDE the chart area rather than as its
                own card. The chart is the analytics surface on this screen, so
                the way deeper into it belongs on the chart — not in a competing
                block further down. Replaces the standalone "Extended Portfolio
                Insights" CTA (removed 2026-08-11).

                No plan check here on purpose: /analytics does its own gating
                with UpgradePrompt per section, so a free member lands on the
                page and meets the paywall there. Gating the entry point too
                would mean two places to keep in step. */}
            <AnimatedPressable
              style={[styles.chartAnalyticsBtn, { borderTopColor: colors.border }]}
              onPress={handleAnalyticsPress}
              accessibilityRole="button"
              accessibilityLabel={t('home.insights_view_a11y')}
            >
              <Ionicons name="analytics-outline" size={16} color={colors.accent} />
              <Text style={[styles.chartAnalyticsBtnText, { color: colors.accent }]}>
                {t('home.analytics')}
              </Text>
              <Ionicons name="chevron-forward" size={14} color={colors.accent} />
            </AnimatedPressable>
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

        {/* Global Collection Stats — the summary tile. */}
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

        {/* Add Item Banner — an onboarding affordance, not a permanent control.
            Once the collection is past a few items the user knows where Add is
            (the centre tab, always visible), so the banner is just a large card
            pushing real content down. Hidden past ADD_BANNER_MAX_ITEMS.

            Sits BELOW the summary tile (moved 2026-08-11): it disappears once
            the collection grows, and anything above the tile would have left a
            gap at the top of the screen for every established user. */}
        {items.length <= ADD_BANNER_MAX_ITEMS && (
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
        )}

        {/* Category Breakdown — returned here from the items tab (2026-08-11,
            reversing the 2026-04-18 move), directly under the tile it breaks
            down, and now PRESSABLE: each card opens that category's own items.
            Rendered in ONE place only; the items-tab copy is removed in the
            same change, because two instances of the same section drift.

            The values here and inside the list agree by construction as of
            2026-08-11 — both resolve through `v_item_values_v1`. Before that
            they did not, and this tile is exactly where it showed: a card
            reading EUR 80.64 opening a list that summed to EUR 0.00. */}
        <CategoryBreakdownSection
          theme={colors}
          breakdown={categoryBreakdown}
          loading={breakdownLoading}
          formatPrice={(v) => formatPrice(v)}
          resolveCategoryName={(raw) => {
            // Same resolution the items-tab copy used: the registry name when
            // it is a real category, else formatCategoryName — never the raw
            // slug, which rendered "uncategorized" lowercase and unsplit.
            const cat = getCategoryById(raw) ?? getCategoryByName(raw);
            return cat?.name ?? formatCategoryName(raw);
          }}
          onCategoryPress={handleBreakdownCategoryPress}
          onAllItemsPress={handleAllItemsPress}
        />

        {/* The standalone "Extended Portfolio Insights" CTA was removed
            2026-08-11 — its job is now the Analytics button inside the chart
            card above, so Home has ONE route to /analytics instead of a card
            competing with the chart it summarises. */}

        {/* Watchlist Card (always show - has empty state) */}
        {featureFlags.FEATURE_DATA_INSIGHTS_ALERTS && (
          <AlertsCard
            alerts={alerts}
            onAlertPress={handleAlertPress}
            onStartWatchlist={handleWatchlistPress}
            showEmptyState={true}
          />
        )}

        {/* The Deal Agent card moved to the Watchlist tab 2026-08-11: it is a
            watchlist feature (deal discovery against your targets), and it now
            sits with the list it acts on rather than on Portfolio. */}

        {/* Hot Right Now moved to Analytics (paywall-gated) 2026-04-18. */}

        {/* Auto-detected set completion (uses structured attributes_json) */}
        <AutoSetProgressList limit={5} />

        {/* Ad slot — invisible until FEATURE_ADS is enabled */}
        <AdBanner placement="portfolio_banner" />

        {/* The "Portfolio Insights" card was REMOVED here on 2026-08-27.
            It was gated on `limits.advanced_analytics`, so it was never a free
            surface — it was a PAID card re-rendering the paid analytics screen:
            total value, period change, top movers and a "View Full Insights"
            link, all of which /analytics answers properly and in more depth
            (Performance, Positions, Allocations, Category Performance).
            Paying twice for the same four numbers is not value, it is clutter
            on the one screen a member opens most.

            The route survives, ungated: the chart's "Analytics" button above
            (`handleAnalyticsPress`, ~line 741) has no plan check on purpose, so
            a free member still lands on /analytics and meets the paywall there
            rather than at the door. That is the entry point; this was a second
            rendering of the destination. */}

        {/* No spacer: `bottomInset` on contentContainerStyle now reserves the
            bar's real height. The 100/80 literal that used to live here was a
            guess at "~88px on iPhone", and keeping both double-padded the
            scroll by ~190pt. */}
        </View>
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
  // Chart card
  chartAnalyticsBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingTop: 12,
    marginTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  chartAnalyticsBtnText: {
    fontSize: text.sm,
    fontWeight: fontWeight.bold,
  },
  // Caption under the headline, not a card: it qualifies the number above it
  // and a bordered block would read as a separate fact.
  estimatedNote: {
    fontSize: 12,
    paddingHorizontal: 16,
    marginTop: -4,
    marginBottom: 8,
  },
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

  // sectionHeader / sectionTitle / sectionSubtitle removed 2026-08-11 with the
  // Collection block — they had no other consumer on this screen.
  categoriesHeading: {
    fontSize: text.xl,
    fontWeight: fontWeight.extrabold,
    marginTop: 8,
    marginBottom: 12,
  },
  sectionSubtitle: {
    fontSize: text.sm,
    marginTop: -4,
    marginBottom: 12,
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
