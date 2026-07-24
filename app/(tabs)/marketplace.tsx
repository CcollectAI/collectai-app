import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useModal } from '@/hooks/useModal';
import { useDebounce } from "@/hooks/useDebounce";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import {
  SafeAreaView,
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  Animated,
  Dimensions,
  ActivityIndicator,
  Linking,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  Modal,
  TouchableOpacity,
  Share,
  FlatList,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { formatPrice, formatDualPrice } from "@/lib/format";
import { useSettings as useSettingsHook } from "@/lib/settings";
import { useTranslation } from "react-i18next";
// InboxHeaderButton and ThemeToggleButton moved to MarketplacePageHeader
import { CATEGORIES } from "@/data/categories";
import { collectorsApi } from "@/api/collectorsApi";
import { dataProvider, type Item as DataItem, type PublicUserProfile } from "@/data";
import { COMMUNITY_GATED } from "@/config/featureFlags";
import { getJSON, setJSON } from "@/lib/storage";
import { useToast } from "@/components/Toast";
import { fireHaptic, HapticIntent } from "@/haptics";
import logger from "@/utils/logger";
import { track } from '@/analytics/track';
import { MarketplaceSearchBar } from '@/components/MarketplaceSearchBar';
import { MarketplaceFilterPanel } from '@/components/MarketplaceFilterPanel';
import { RecentSearchesSection } from '@/components/RecentSearchesSection';
import { SearchResultQuickView } from '@/components/SearchResultQuickView';
import { SkeletonList } from '@/components/Skeleton';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { MarketplacePageHeader } from '@/components/marketplace/MarketplacePageHeader';
import { MarketplaceResultCard, type MarketplaceResultItem } from '@/components/marketplace/MarketplaceResultCard';
import { MarketplaceEmptyState } from '@/components/marketplace/MarketplaceEmptyState';
import { DemandHeatBanner } from '@/components/marketplace/DemandHeatBanner';
import { AdBanner } from '@/components/ads/AdBanner';
import { RegionalInsightsSection } from '@/components/marketplace/RegionalInsightsSection';
import { MarketMoversSection } from '@/components/marketplace/MarketMoversSection';

// --- Types for marketplace API results ---
type MarketplaceHit = {
  source: string;
  title: string;
  price: number | null;
  currency: string;
  source_price: number | null;
  source_currency: string | null;
  url: string;
  affiliate_url: string | null;
  affiliate_source: string | null;
  image_url: string | null;
  condition: string | null;
  is_sold: boolean;
  provenance_score: number;
  source_reliability: number;
  recency_score: number;
  shipping_cost: number | null;
  ships_from: string | null;
  domestic_only: boolean;
  listing_region: string | null;
  shipping_estimate: {
    min_eur: number;
    max_eur: number;
    exact_eur: number | null;
    is_domestic: boolean;
    disclaimer: string | null;
  } | null;
};

// Unified result type for rendering (same visual as before)
type SearchResult = {
  id: string;
  name: string;
  category: string;
  collectionName: string;
  value: number;
  // External marketplace data (when result is from API)
  isMarketplace?: boolean;
  externalUrl?: string;
  affiliateUrl?: string;
  source?: string;
  condition?: string;
  // Image
  image_url?: string | null;
  // Shipping & cross-border
  domesticOnly?: boolean;
  shippingHint?: string;
  secondaryPrice?: string | null;
  sourceCurrency?: string | null;
};

const RECENT_SEARCHES_KEY = "collectai_recent_searches";

// Use category data from the data layer - get all categories for browsing
const BROWSE_CATEGORIES = CATEGORIES.map((cat) => ({
  id: cat.id,
  name: cat.name,
  imageUrl: cat.bannerImageUrl,
}));

// Filter options (constants moved to MarketplaceFilterPanel component)

// Tile colors now come from theme.tileScale (Tiffany brand scale)

// Compute uniform tile dimensions for 2-col grid
const SCREEN_WIDTH = Dimensions.get("window").width;
const TILE_PAD = 16; // matches content paddingHorizontal
const TILE_GAP = 12;
const TILE_WIDTH = Math.floor((SCREEN_WIDTH - TILE_PAD * 2 - TILE_GAP) / 2);
const TILE_HEIGHT = Math.floor(TILE_WIDTH * 0.62); // ~110-120px for consistent aspect

const SearchScreen: React.FC = () => {
  const router = useRouter();
  const { colors, isDark } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettingsHook();
  const { t } = useTranslation();
  const { showToast } = useToast();
  const [query, setQuery] = useState("");
  const [recent, setRecent] = useState<string[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  // Escalating status copy for the live aggregation. Marketplace search
  // hits 44 adapters server-side and can legitimately take 30-60 s. A
  // silent skeleton at that length feels broken, so the status text
  // updates at 0 / 6 / 20 / 45 s.
  const [searchStatus, setSearchStatus] = useState<string>('');
  const [refreshing, setRefreshing] = useState(false);
  const [marketplaceResults, setMarketplaceResults] = useState<SearchResult[]>([]);
  const [collectionResults, setCollectionResults] = useState<SearchResult[]>([]);
  // DISABLED pre-launch: the external "Buy externally" search does a live scrape
  // across 44 marketplace adapters, which can take up to 90s for rare items and
  // reads as broken. Only the instant local sections (Your items + Categories)
  // run while this is false. Flip to true once the scrape budget is fast enough.
  const EXTERNAL_MARKETPLACE_SEARCH_ENABLED = false;
  const searchIdRef = useRef(0);

  // Escalating status copy while marketplace search is running. The server
  // live-aggregates across 44 adapters; 30-60s is common for rare items.
  // We update the visible status text at 0 / 6 / 20 / 45 s so the spinner
  // never feels frozen. Timers are cleared as soon as `searchLoading` flips
  // back to false.
  useEffect(() => {
    if (!searchLoading) {
      setSearchStatus('');
      return;
    }
    // External scrape disabled → only the fast local search runs; show a brief
    // neutral status and skip the long-wait ("up to 90s") escalation entirely.
    if (!EXTERNAL_MARKETPLACE_SEARCH_ENABLED) {
      setSearchStatus('Searching…');
      return;
    }
    setSearchStatus('Searching marketplaces…');
    const t1 = setTimeout(() => setSearchStatus('Aggregating across 44 sources…'), 6_000);
    const t2 = setTimeout(() => setSearchStatus('Still searching — this can take up to 90s for rare items.'), 20_000);
    const t3 = setTimeout(() => setSearchStatus('Almost there…'), 45_000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [searchLoading, EXTERNAL_MARKETPLACE_SEARCH_ENABLED]);

  // User search state
  const [userSearchVisible, openUserSearch, closeUserSearch] = useModal();
  const [userSearchQuery, setUserSearchQuery] = useState("");
  const [userSearchResults, setUserSearchResults] = useState<PublicUserProfile[]>([]);
  const [userSearchLoading, setUserSearchLoading] = useState(false);
  const [quickViewItem, setQuickViewItem] = useState<SearchResult | null>(null);
  const [quickViewVisible, openQuickView, closeQuickView] = useModal();
  const [demandHeat, setDemandHeat] = useState<{ item_key: string; title: string; category: string; demand_score: number; search_count: number }[]>([]);
  const [regionalDemand, setRegionalDemand] = useState<{ item_key: string; category: string; signal_count: number; region: string }[]>([]);
  const debouncedUserQuery = useDebounce(userSearchQuery.trim(), 350);

  useEffect(() => {
    let cancelled = false;
    const DEMAND_HEAT_CACHE_KEY = '@demand_heat_cache';
    const REGIONAL_DEMAND_CACHE_KEY = '@regional_demand_cache';
    const CACHE_TTL = 15 * 60 * 1000; // 15 minutes

    async function fetchDemandHeat() {
      try {
        const cached = await AsyncStorage.getItem(DEMAND_HEAT_CACHE_KEY);
        if (cached) {
          const { data, ts } = JSON.parse(cached);
          if (Date.now() - ts < CACHE_TTL) {
            if (!cancelled && Array.isArray(data) && data.length) setDemandHeat(data);
            return;
          }
        }
      } catch { /* cache miss, proceed to fetch */ }
      try {
        const data = await collectorsApi.getDemandHeat();
        if (cancelled) return;
        const resp = data as { items?: { item_key: string; title: string; category: string; demand_score: number; search_count: number }[] } | undefined;
        const items = resp?.items;
        if (Array.isArray(items) && items.length) {
          const sliced = items.slice(0, 6);
          setDemandHeat(sliced);
          AsyncStorage.setItem(DEMAND_HEAT_CACHE_KEY, JSON.stringify({ data: sliced, ts: Date.now() })).catch(() => {});
        }
      } catch (err) { logger.warn('[Marketplace] getDemandHeat error:', err); }
    }

    async function fetchRegionalDemand() {
      try {
        const cached = await AsyncStorage.getItem(REGIONAL_DEMAND_CACHE_KEY);
        if (cached) {
          const { data, ts } = JSON.parse(cached);
          if (Date.now() - ts < CACHE_TTL) {
            if (!cancelled && Array.isArray(data)) setRegionalDemand(data);
            return;
          }
        }
      } catch { /* cache miss, proceed to fetch */ }
      try {
        const data = await collectorsApi.getDemandHeatByRegion();
        if (cancelled) return;
        const resp = data as { items?: { item_key: string; category: string; signal_count: number; region: string }[] } | undefined;
        if (Array.isArray(resp?.items)) {
          const sliced = resp!.items.slice(0, 5);
          setRegionalDemand(sliced);
          AsyncStorage.setItem(REGIONAL_DEMAND_CACHE_KEY, JSON.stringify({ data: sliced, ts: Date.now() })).catch(() => {});
        }
      } catch (err) { logger.warn('[Marketplace] getDemandHeatByRegion error:', err); }
    }

    fetchDemandHeat();
    fetchRegionalDemand();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!debouncedUserQuery) {
      setUserSearchResults([]);
      setUserSearchLoading(false);
      return;
    }
    let cancelled = false;
    setUserSearchLoading(true);
    dataProvider.searchUsers(debouncedUserQuery).then((results) => {
      if (!cancelled) {
        setUserSearchResults(results);
        setUserSearchLoading(false);
      }
    }).catch((err) => {
      logger.warn("[UserSearch] error:", err);
      if (!cancelled) {
        setUserSearchResults([]);
        setUserSearchLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [debouncedUserQuery]);

  const handleOpenUserProfile = useCallback((userId: string) => {
    closeUserSearch();
    setUserSearchQuery("");
    setUserSearchResults([]);
    router.push(`/users/${userId}`);
  }, [router, closeUserSearch]);

  // Filter state
  const [filterVisible, openFilter, closeFilter] = useModal();
  const [filterSources, setFilterSources] = useState<string[]>([]);
  const [filterConditions, setFilterConditions] = useState<string[]>([]);
  const [filterMinPrice, setFilterMinPrice] = useState("");
  const [filterMaxPrice, setFilterMaxPrice] = useState("");
  const [filterSort, setFilterSort] = useState("relevance");

  // Trending-categories fetch removed 2026-07-24. The rail it fed was deleted
  // from the render (see "Trending categories removed" below), so this effect
  // called /insights/personalized on every mount and wrote the result into
  // state no JSX read — the endpoint's four computed arrays were all discarded.
  // The concentration/diversification half of that payload now renders on the
  // analytics screen; see app/analytics.tsx "Concentration & Balance" and the
  // seam fn in src/data/personalizedInsights.ts. Restore a call here only
  // alongside a rail that actually renders it.

  // Count of active filters for badge
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filterSources.length > 0) count++;
    if (filterConditions.length > 0) count++;
    if (filterMinPrice || filterMaxPrice) count++;
    if (filterSort !== "relevance") count++;
    return count;
  }, [filterSources, filterConditions, filterMinPrice, filterMaxPrice, filterSort]);

  // Load persisted recent searches on mount
  useEffect(() => {
    let cancelled = false;
    getJSON<string[]>(RECENT_SEARCHES_KEY, []).then((v) => { if (!cancelled) setRecent(v); });
    return () => { cancelled = true; };
  }, []);

  const trimmedQuery = query.trim();
  const debouncedQuery = useDebounce(trimmedQuery, 350);

  // Category matches — instant, local (CATEGORIES is static), so searching
  // "taylor swift" surfaces the category immediately even before the
  // marketplace/collection network searches return. Matches name, id (with
  // underscores treated as spaces), and tagline.
  const categoryResults = useMemo(() => {
    if (!trimmedQuery) return [];
    const q = trimmedQuery.toLowerCase();
    return CATEGORIES.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.id.replace(/_/g, ' ').toLowerCase().includes(q) ||
        (c.tagline ?? '').toLowerCase().includes(q),
    ).slice(0, 6);
  }, [trimmedQuery]);


  // Unique collections from collection results only
  const uniqueCollections = useMemo(
    () =>
      Array.from(
        new Map(
          collectionResults
            .filter((r) => r.collectionName && r.collectionName !== "-")
            .map((item) => [item.collectionName, item])
        ).values()
      ),
    [collectionResults]
  );

  // Run the actual search against marketplace API + local collection
  const executeSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setMarketplaceResults([]);
      setCollectionResults([]);
      return;
    }

    const searchId = ++searchIdRef.current;
    setSearchLoading(true);

    // Build filter options for marketplace API
    const searchOpts: Parameters<typeof collectorsApi.marketplaceSearch>[1] = {};
    if (filterSources.length > 0) searchOpts.source = filterSources;
    if (filterConditions.length > 0) searchOpts.condition = filterConditions;
    if (filterMinPrice) {
      const val = parseFloat(filterMinPrice);
      if (!isNaN(val)) searchOpts.min_price = val;
    }
    if (filterMaxPrice) {
      const val = parseFloat(filterMaxPrice);
      if (!isNaN(val)) searchOpts.max_price = val;
    }
    if (filterSort && filterSort !== "relevance") searchOpts.sort = filterSort;
    if (settings.region) searchOpts.region = settings.region;

    // Run marketplace API + local collection search in parallel. The external
    // marketplace scrape is gated off pre-launch (see flag above) — when
    // disabled it resolves to null instantly so only the fast local "Your items"
    // + instant "Categories" sections populate.
    const [mktResult, colResult] = await Promise.allSettled([
      EXTERNAL_MARKETPLACE_SEARCH_ENABLED
        ? collectorsApi.marketplaceSearch(q.trim(), searchOpts).catch((err: unknown) => {
            logger.warn("[Search] marketplace search error:", err);
            return null;
          })
        : Promise.resolve(null),
      dataProvider.searchItems(q.trim()).catch((err: unknown) => {
        logger.warn("[Search] collection search error:", err);
        return [] as DataItem[];
      }),
    ]);

    // Stale response guard
    if (searchId !== searchIdRef.current) return;

    // Map marketplace hits
    const mktData = (mktResult.status === "fulfilled" ? mktResult.value : null) as { hits?: MarketplaceHit[] } | null;
    const hits: MarketplaceHit[] = mktData?.hits ?? [];
    const mktResults: SearchResult[] = hits
      .filter((h) => !h.is_sold)
      .slice(0, 10)
      .map((h, i) => {
        // Build shipping hint
        let shippingHint: string | undefined;
        const est = h.shipping_estimate;
        if (est) {
          if (est.exact_eur != null) {
            shippingHint = est.exact_eur === 0
              ? "+Free shipping"
              : `+${formatPrice(est.exact_eur)} shipping`;
          } else {
            shippingHint = `+${formatPrice(est.min_eur)}-${formatPrice(est.max_eur)} est. shipping`;
          }
        }

        // Build secondary price (original currency)
        let secondaryPrice: string | null = null;
        if (h.price != null && h.source_currency && h.source_currency !== settings.currency) {
          const dual = formatDualPrice(h.price, h.source_currency, settings);
          secondaryPrice = dual.secondary;
        }

        return {
          id: `mkt_${i}_${h.url}`,
          name: h.title || "Untitled",
          category: h.source || "",
          collectionName: h.condition || "-",
          value: h.price ?? 0,
          isMarketplace: true,
          externalUrl: h.url,
          affiliateUrl: h.affiliate_url ?? undefined,
          source: h.source,
          condition: h.condition ?? undefined,
          image_url: h.image_url,
          domesticOnly: h.domestic_only,
          shippingHint,
          secondaryPrice,
          sourceCurrency: h.source_currency,
        };
      });

    // Map collection items
    const colData = colResult.status === "fulfilled" ? colResult.value : [];
    const colResults: SearchResult[] = (colData ?? []).slice(0, 10).map((item) => ({
      id: item.id,
      name: item.name,
      category: item.category,
      collectionName: (item.collections ?? [])[0] ?? "-",
      value: item.price ?? item.priceBand?.q50 ?? 0,
    }));

    // Notify user about search failures
    if (mktResult.status === 'rejected' && colResult.status === 'rejected') {
      showToast({ message: 'Could not reach the marketplace. Check your connection and try again.', type: 'error' });
    } else if (mktResult.status === 'rejected') {
      showToast({ message: 'Marketplace search failed — showing collection results only.', type: 'info' });
    } else if (colResult.status === 'rejected') {
      showToast({ message: 'Collection search failed — showing marketplace results only.', type: 'info' });
    }

    setMarketplaceResults(mktResults);
    setCollectionResults(colResults);
    setSearchLoading(false);
    track({ name: 'marketplace_search', properties: { query: q, result_count: mktResults.length } });
    setRefreshing(false);
  }, [filterSources, filterConditions, filterMinPrice, filterMaxPrice, filterSort, settings]);

  // Auto-search when debounced query changes (avoids firing on every keystroke)
  useEffect(() => {
    if (debouncedQuery) {
      executeSearch(debouncedQuery);
    } else {
      setMarketplaceResults([]);
      setCollectionResults([]);
    }
  }, [debouncedQuery, executeSearch]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    if (trimmedQuery) {
      executeSearch(trimmedQuery);
    } else {
      setRefreshing(false);
    }
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
  }, [trimmedQuery, executeSearch, settings.hapticsEnabled]);

  const handleSubmitSearch = useCallback(() => {
    if (!trimmedQuery) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    // Persist recent search
    setRecent((prev) => {
      const existing = prev.filter(
        (term) => term.toLowerCase() !== trimmedQuery.toLowerCase()
      );
      const updated = [trimmedQuery, ...existing].slice(0, 6);
      setJSON(RECENT_SEARCHES_KEY, updated);
      return updated;
    });
    executeSearch(trimmedQuery);
  }, [trimmedQuery, executeSearch, settings.hapticsEnabled]);

  // Also trigger search when tapping a recent search chip
  const handleChipPress = useCallback((term: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setQuery(term);
    executeSearch(term);
  }, [executeSearch, settings.hapticsEnabled]);

  const handleOpenResult = useCallback((item: SearchResult) => {
    if (item.domesticOnly) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    if (item.isMarketplace) {
      setQuickViewItem(item);
      openQuickView();
    } else {
      router.push({
        pathname: "/item/[id]",
        params: {
          id: item.id,
          name: item.name,
          category: item.category,
          collectionName: item.collectionName,
          value: String(item.value),
        },
      });
    }
  }, [router, settings.hapticsEnabled]);

  const handleQuickViewOpen = useCallback(() => {
    if (!quickViewItem) return;
    const openUrl = quickViewItem.affiliateUrl || quickViewItem.externalUrl;
    if (openUrl) {
      Linking.openURL(openUrl).catch((err) => {
        logger.warn('[Marketplace] Failed to open URL', err);
      });
    }
    closeQuickView();
    setQuickViewItem(null);
  }, [quickViewItem, closeQuickView]);

  const handleQuickViewShare = useCallback(async () => {
    if (!quickViewItem) return;
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    try {
      await Share.share({
        message: `${quickViewItem.name} - ${formatPrice(quickViewItem.value)} on ${quickViewItem.source || 'Marketplace'}`,
        url: quickViewItem.externalUrl,
      });
    } catch (err) {
      logger.warn('[Marketplace] share error:', err);
    }
  }, [quickViewItem, settings.hapticsEnabled]);

  const handleOpenCategory = useCallback((categoryId: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push(`/categories/${encodeURIComponent(categoryId)}`);
  }, [router, settings.hapticsEnabled]);

  const handleOpenCollection = useCallback((collectionName: string) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    router.push({
      pathname: "/(tabs)/items",
      params: { collectionName },
    });
  }, [router, settings.hapticsEnabled]);

  const handleFilterApply = useCallback(() => {
    closeFilter();
    if (trimmedQuery) executeSearch(trimmedQuery);
  }, [closeFilter, trimmedQuery, executeSearch]);

  const handleFilterReset = useCallback(() => {
    setFilterSources([]);
    setFilterConditions([]);
    setFilterMinPrice("");
    setFilterMaxPrice("");
    setFilterSort("relevance");
  }, []);

  const handleCloseUserSearch = useCallback(() => {
    closeUserSearch();
    setUserSearchQuery("");
    setUserSearchResults([]);
  }, [closeUserSearch]);

  const handleClearUserSearch = useCallback(() => {
    setUserSearchQuery("");
    setUserSearchResults([]);
  }, []);

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={{ flex: 1 }}
        keyboardVerticalOffset={Platform.OS === "ios" ? 50 : 0}
      >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[
          styles.content,
          { backgroundColor: colors.background },
        ]}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            tintColor={colors.accent}
            colors={[colors.accent]}
          />
        }
      >
        <Animated.View style={animatedStyle}>
        {/* Header */}
        <MarketplacePageHeader />

        {/* Search input + filter button */}
        <MarketplaceSearchBar
          theme={colors}
          query={query}
          onQueryChange={setQuery}
          onSubmit={handleSubmitSearch}
          onOpenFilter={openFilter}
          activeFilterCount={activeFilterCount}
        />

        {/* Ad slot — invisible until FEATURE_ADS is enabled */}
        <AdBanner placement="marketplace_banner" />

        {/* Find Collectors button — gated until community has density.
            With <50 public profiles, the modal returns 0 results for any
            non-trivial query and looks broken. Hidden via COMMUNITY_GATED;
            modal still mounts via deep-link if a future entry surfaces it. */}
        {!trimmedQuery && !COMMUNITY_GATED && (
          <AnimatedPressable
            style={[styles.findCollectorsButton, { borderColor: colors.accent, backgroundColor: colors.accent + '10' }]}
            onPress={openUserSearch}
            accessibilityRole="button"
            accessibilityLabel={t('marketplace.find_collectors_a11y')}
          >
            <Ionicons name="people-outline" size={18} color={colors.accent} />
            <Text style={[styles.findCollectorsText, { color: colors.accent }]}>{t('marketplace.find_collectors')}</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.accent} />
          </AnimatedPressable>
        )}

        {/* Recent searches */}
        {!trimmedQuery && (
          <RecentSearchesSection
            theme={colors}
            recentSearches={recent}
            onChipPress={handleChipPress}
          />
        )}

        {/* Popular searches (preset chips) */}
        {!trimmedQuery && (
          <View style={styles.presetChipsSection}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>{t('marketplace.popular_searches')}</Text>
            <View style={styles.presetChipsRow}>
              {['Charizard', 'Black Lotus', 'Funko Pop', 'Jordan 1', 'LEGO Star Wars', 'Pikachu'].map((term) => (
                <TouchableOpacity
                  key={term}
                  onPress={() => handleChipPress(term)}
                  style={[styles.presetChip, { borderColor: colors.border, backgroundColor: colors.card }]}
                  accessibilityRole="button"
                  accessibilityLabel={`Search for ${term}`}
                >
                  <Ionicons name="search-outline" size={12} color={colors.muted} />
                  <Text style={[styles.presetChipText, { color: colors.text }]}>{term}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}

        {/* Browse by category (Spotify-style grid) */}
        {!trimmedQuery && (
          <>
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>
                Browse by category
              </Text>
              <FlatList
                data={BROWSE_CATEGORIES}
                keyExtractor={(cat) => cat.id}
                numColumns={2}
                scrollEnabled={false}
                columnWrapperStyle={styles.categoryGridRow}
                renderItem={({ item: cat, index }) => {
                  const row = Math.floor(index / 2);
                  const col = index % 2;
                  const ci = (row + col) % 2 === 0
                    ? (row % 2 === 0 ? 0 : 1)
                    : (row % 2 === 0 ? 2 : 3);
                  const darkTileColors = [colors.accent + '70', colors.accent + '90', colors.accent + 'B0', colors.accent + 'D0'];
                  const bg = isDark
                    ? darkTileColors[ci]
                    : colors.tileScale[ci];
                  return (
                    <AnimatedPressable
                      style={[styles.categoryTile, { backgroundColor: bg }]}
                      onPress={() => handleOpenCategory(cat.id)}
                      accessibilityRole="button"
                      accessibilityLabel={`Browse ${cat.name}`}
                    >
                      {cat.imageUrl ? (
                        <Image
                          source={{ uri: cat.imageUrl }}
                          style={styles.categoryTileImage}
                          contentFit="cover"
                          cachePolicy="memory-disk"
                          transition={150}
                        />
                      ) : null}
                      <View style={styles.categoryTileOverlay} />
                      <Text
                        style={styles.categoryTileText}
                        numberOfLines={2}
                        ellipsizeMode="tail"
                      >
                        {cat.name}
                      </Text>
                    </AnimatedPressable>
                  );
                }}
                initialNumToRender={10}
                maxToRenderPerBatch={10}
                windowSize={3}
                removeClippedSubviews={true}
              />
            </View>

            {/* Market Pulse — demand heat */}
            <DemandHeatBanner items={demandHeat} onSearchItem={handleChipPress} />

            {/* Regional demand insights */}
            <RegionalInsightsSection items={regionalDemand} onSearchItem={handleChipPress} />

            {/* Market Movers — biggest 7d price gainers/losers (followed cats + see-all) */}
            <MarketMoversSection />

            {/* Trending categories removed */}
          </>
        )}

        {/* Filter bottom sheet */}
        <MarketplaceFilterPanel
          theme={colors}
          visible={filterVisible}
          filterSources={filterSources}
          filterConditions={filterConditions}
          filterMinPrice={filterMinPrice}
          filterMaxPrice={filterMaxPrice}
          filterSort={filterSort}
          onSetFilterSources={setFilterSources}
          onSetFilterConditions={setFilterConditions}
          onSetFilterMinPrice={setFilterMinPrice}
          onSetFilterMaxPrice={setFilterMaxPrice}
          onSetFilterSort={setFilterSort}
          onApply={handleFilterApply}
          onClose={closeFilter}
          onReset={handleFilterReset}
        />

        {/* User Search Modal */}
        <Modal
          visible={userSearchVisible}
          animationType="slide"
          presentationStyle="pageSheet"
          onRequestClose={handleCloseUserSearch}
        >
          <SafeAreaView style={[styles.filterModal, { backgroundColor: colors.background }]}>
            {/* Header */}
            <View style={[styles.filterHeader, { borderBottomColor: colors.border }]}>
              <TouchableOpacity
                onPress={handleCloseUserSearch}
                accessibilityRole="button"
                accessibilityLabel={t('marketplace.close_user_search_a11y')}
              >
                <Ionicons name="close" size={24} color={colors.text} />
              </TouchableOpacity>
              <Text style={[styles.filterHeaderTitle, { color: colors.text }]}>{t('marketplace.find_collectors')}</Text>
              <View style={{ width: 24 }} />
            </View>

            {/* Search input */}
            <View style={{ paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8 }}>
              <View style={[styles.searchRow, { borderColor: colors.border }]}>
                <Ionicons name="search-outline" size={18} color={colors.muted} style={{ marginRight: 8 }} />
                <TextInput
                  value={userSearchQuery}
                  onChangeText={setUserSearchQuery}
                  placeholder={t('marketplace.search_users_placeholder')}
                  placeholderTextColor={colors.muted}
                  autoFocus
                  style={[styles.searchInput, { color: colors.text }]}
                  accessibilityLabel={t('marketplace.search_users_a11y')}
                  returnKeyType="search"
                />
                {userSearchQuery.length > 0 && (
                  <TouchableOpacity
                    onPress={handleClearUserSearch}
                    accessibilityRole="button"
                    accessibilityLabel={t('common.clear_search')}
                  >
                    <Ionicons name="close-circle" size={18} color={colors.muted} />
                  </TouchableOpacity>
                )}
              </View>
            </View>

            {/* Results */}
            <ScrollView
              style={{ flex: 1 }}
              contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 32 }}
              keyboardShouldPersistTaps="handled"
            >
              {userSearchLoading && (
                <ActivityIndicator
                  size="small"
                  color={colors.accent}
                  style={{ marginTop: 24 }}
                />
              )}

              {!userSearchLoading && debouncedUserQuery.length > 0 && userSearchResults.length === 0 && (
                <View style={{ alignItems: "center", paddingTop: 32 }}>
                  <Ionicons name="people-outline" size={36} color={colors.muted} />
                  <Text style={[styles.noResultsTitle, { color: colors.text, marginTop: 12 }]}>
                    No collectors found
                  </Text>
                  <Text style={[styles.emptyText, { color: colors.muted }]}>
                    Try a different name or handle.
                  </Text>
                </View>
              )}

              {!userSearchLoading && userSearchResults.length > 0 && (
                <View style={{ marginTop: 8 }}>
                  <Text style={[styles.sectionTitle, { color: colors.muted, marginBottom: 8 }]}>
                    {userSearchResults.length} {userSearchResults.length === 1 ? "collector" : "collectors"} found
                  </Text>
                  {userSearchResults.map((user) => {
                    const initials = user.displayName
                      .split(" ")
                      .map((part) => part[0])
                      .join("")
                      .slice(0, 2)
                      .toUpperCase() || "?";
                    return (
                      <AnimatedPressable
                        key={user.id}
                        style={[styles.userResultRow, { borderBottomColor: colors.border }]}
                        onPress={() => handleOpenUserProfile(user.id)}
                        accessibilityRole="button"
                        accessibilityLabel={`View profile of ${user.displayName}`}
                      >
                        {user.avatarUrl ? (
                          <View style={[styles.userAvatar, { backgroundColor: colors.accent + "20" }]}>
                            <Text style={[styles.userAvatarText, { color: colors.accent }]}>
                              {initials}
                            </Text>
                          </View>
                        ) : (
                          <View style={[styles.userAvatar, { backgroundColor: colors.accent + "20" }]}>
                            <Text style={[styles.userAvatarText, { color: colors.accent }]}>
                              {initials}
                            </Text>
                          </View>
                        )}
                        <View style={{ flex: 1 }}>
                          <Text style={[styles.userResultName, { color: colors.text }]}>
                            {user.displayName}
                          </Text>
                          {user.handle && (
                            <Text style={[styles.userResultHandle, { color: colors.muted }]}>
                              @{user.handle}
                            </Text>
                          )}
                        </View>
                        <Ionicons name="chevron-forward" size={16} color={colors.muted} />
                      </AnimatedPressable>
                    );
                  })}
                </View>
              )}

              {!userSearchLoading && !debouncedUserQuery && (
                <View style={{ alignItems: "center", paddingTop: 40 }}>
                  <Ionicons name="people-outline" size={40} color={colors.muted + "60"} />
                  <Text style={[styles.emptyText, { color: colors.muted, marginTop: 12 }]}>
                    Search for collectors by name or handle
                  </Text>
                </View>
              )}
            </ScrollView>
          </SafeAreaView>
        </Modal>

        {/* Results when searching */}
        {trimmedQuery ? (
          <View style={styles.section}>
            {/* Categories — instant local matches, shown above network results */}
            {categoryResults.length > 0 && (
              <>
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Categories</Text>
                {categoryResults.map((cat) => (
                  <AnimatedPressable
                    key={cat.id}
                    style={[styles.catResultRow, { backgroundColor: colors.card, borderColor: colors.border }]}
                    onPress={() => handleOpenCategory(cat.id)}
                    accessibilityRole="button"
                    accessibilityLabel={`Open ${cat.name} category`}
                  >
                    <Ionicons name="grid-outline" size={18} color={colors.accent} />
                    <Text style={[styles.catResultName, { color: colors.text }]} numberOfLines={1}>{cat.name}</Text>
                    <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                  </AnimatedPressable>
                ))}
              </>
            )}
            {searchLoading ? (
              <>
                {searchStatus ? (
                  <View style={styles.searchStatusRow}>
                    <ActivityIndicator size="small" color={colors.accent} />
                    <Text style={[styles.searchStatusText, { color: colors.muted }]}>
                      {searchStatus}
                    </Text>
                  </View>
                ) : null}
                <SkeletonList count={6} type="card" />
              </>
            ) : (
              <>
                {/* Your items — the user's own collection (internal) */}
                {collectionResults.length > 0 && (
                  <>
                    <Text style={[styles.sectionTitle, { color: colors.text }]}>Your items</Text>
                    {collectionResults.map((item) => (
                      <MarketplaceResultCard key={item.id} item={item} onPress={handleOpenResult} />
                    ))}
                  </>
                )}

                {/* Buy externally — live marketplace listings (external) */}
                {marketplaceResults.length > 0 && (
                  <>
                    <Text
                      style={[
                        styles.sectionTitle,
                        { color: colors.text, marginTop: collectionResults.length > 0 ? 16 : 0 },
                      ]}
                    >
                      Buy externally
                    </Text>
                    {marketplaceResults.map((item) => (
                      <MarketplaceResultCard key={item.id} item={item} onPress={handleOpenResult} />
                    ))}
                  </>
                )}

                {/* Nothing matched in any of the three sections */}
                {categoryResults.length === 0 &&
                  collectionResults.length === 0 &&
                  marketplaceResults.length === 0 && <MarketplaceEmptyState />}

                {/* Cross-border disclaimer */}
                {marketplaceResults.some((r) => r.shippingHint || r.secondaryPrice) && (
                  <Text style={[styles.crossBorderDisclaimer, { color: colors.muted }]}>
                    Customs/duties may apply for international purchases
                  </Text>
                )}

                {/* Collections section */}
                {uniqueCollections.length > 0 && (
                  <>
                    <Text
                      style={[
                        styles.sectionTitle,
                        { color: colors.text, marginTop: 16 },
                      ]}
                    >
                      Collections
                    </Text>
                    {uniqueCollections.map((item) => (
                      <AnimatedPressable
                        key={item.collectionName}
                        style={styles.collectionRow}
                        onPress={() => handleOpenCollection(item.collectionName)}
                        accessibilityRole="button"
                        accessibilityLabel={`View ${item.collectionName} collection`}
                      >
                        <View style={[styles.collectionIcon, { backgroundColor: colors.accent + '10' }]}>
                          <Ionicons name="albums-outline" size={18} color={colors.accent} />
                        </View>
                        <View>
                          <Text
                            style={[styles.collectionTitle, { color: colors.text }]}
                          >
                            {item.collectionName}
                          </Text>
                          <Text
                            style={[styles.collectionMeta, { color: colors.muted }]}
                          >
                            {item.category}
                          </Text>
                        </View>
                      </AnimatedPressable>
                    ))}
                  </>
                )}
              </>
            )}
          </View>
        ) : null}
        </Animated.View>
      </ScrollView>
      </KeyboardAvoidingView>

      {/* Quick View Sheet */}
      <SearchResultQuickView
        theme={colors}
        visible={quickViewVisible}
        item={quickViewItem}
        onClose={() => { closeQuickView(); setQuickViewItem(null); }}
        onOpenUrl={handleQuickViewOpen}
        onShare={handleQuickViewShare}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  scroll: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 32,
  },
  // (headerRow, headerLeft, headerTitle, headerSubtitle, headerIcons moved to MarketplacePageHeader)
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  searchInput: {
    flex: 1,
    fontSize: 14,
    paddingVertical: 4,
  },
  section: {
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 6,
  },
  catResultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderRadius: 12,
    borderWidth: 1,
    paddingVertical: 12,
    paddingHorizontal: 14,
    marginBottom: 8,
  },
  catResultName: {
    flex: 1,
    fontSize: 15,
    fontWeight: '600',
  },
  searchStatusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 12,
    paddingHorizontal: 4,
    marginBottom: 4,
  },
  searchStatusText: {
    fontSize: 13,
    fontWeight: '600',
    flex: 1,
  },
  // (chip styles moved to RecentSearchesSection component)
  categoryGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: TILE_GAP,
  },
  categoryGridRow: {
    gap: TILE_GAP,
    marginBottom: TILE_GAP,
  },
  categoryTile: {
    width: TILE_WIDTH,
    height: TILE_HEIGHT,
    borderRadius: 12,
    padding: 12,
    justifyContent: "flex-end",
    overflow: "hidden",
  },
  categoryTileImage: {
    ...StyleSheet.absoluteFillObject,
  },
  categoryTileOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.42)",
  },
  categoryTileText: {
    fontSize: 14,
    fontWeight: "800",
    color: "#FFFFFF",
    textShadowColor: "rgba(0,0,0,0.6)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  // (resultRow, resultIcon, resultTitle, resultMeta, resultValue, resultSecondary, resultShipping, domesticBadge, domesticBadgeText moved to MarketplaceResultCard)
  crossBorderDisclaimer: {
    fontSize: 11,
    textAlign: "center",
    marginTop: 12,
    marginBottom: 4,
    fontStyle: "italic",
  },
  // (noResultsBlock moved to MarketplaceEmptyState)
  emptyText: {
    fontSize: 13,
    marginTop: 4,
    textAlign: "center",
  },
  noResultsTitle: {
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 4,
  },
  collectionRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
  },
  collectionIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 8,
  },
  collectionTitle: {
    fontSize: 13,
    fontWeight: "600",
  },
  collectionMeta: {
    fontSize: 11,
    marginTop: 2,
  },
  // (trending styles moved to TrendingCategoriesGrid component)
  // (search bar + filter button styles moved to MarketplaceSearchBar component)
  // (resultThumbnail, resultThumbnailPlaceholder moved to MarketplaceResultCard)
  filterModal: {
    flex: 1,
  },
  filterHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  filterHeaderTitle: {
    fontSize: 17,
    fontWeight: "700",
  },
  // (filter panel styles moved to MarketplaceFilterPanel component)
  // Find Collectors styles
  findCollectorsButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1.5,
    marginBottom: 4,
  },
  findCollectorsText: {
    fontSize: 14,
    fontWeight: "700",
  },
  userResultRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  userAvatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 12,
  },
  userAvatarText: {
    fontSize: 15,
    fontWeight: "700",
  },
  userResultName: {
    fontSize: 15,
    fontWeight: "600",
  },
  userResultHandle: {
    fontSize: 12,
    marginTop: 2,
  },
  // (quick view styles moved to SearchResultQuickView component)
  presetChipsSection: {
    marginBottom: 16,
  },
  presetChipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 8,
  },
  presetChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
  },
  presetChipText: {
    fontSize: 13,
    fontWeight: '500',
  },
  // (sectionSubtitle, demandCard, demandRank, demandRankText, demandTitle, demandMeta, demandScore, demandScoreText moved to DemandHeatBanner + RegionalInsightsSection)
});

function SearchScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Search">
      <SearchScreen />
    </ScreenErrorBoundary>
  );
}

export default SearchScreenWithBoundary;
