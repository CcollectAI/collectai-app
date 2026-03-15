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
import { useRouter } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { formatPrice, formatDualPrice } from "@/lib/format";
import { useSettings as useSettingsHook } from "@/lib/settings";
// InboxHeaderButton and ThemeToggleButton moved to MarketplacePageHeader
import { CATEGORIES } from "@/data/categories";
import { collectorsApi } from "@/api/collectorsApi";
import { dataProvider, type Item as DataItem, type PublicUserProfile } from "@/data";
import { getJSON, setJSON } from "@/lib/storage";
import { useToast } from "@/components/Toast";
import { fireHaptic, HapticIntent } from "@/haptics";
import logger from "@/utils/logger";
import { track } from '@/analytics/track';
import { MarketplaceSearchBar } from '@/components/MarketplaceSearchBar';
import { MarketplaceFilterPanel } from '@/components/MarketplaceFilterPanel';
import { RecentSearchesSection } from '@/components/RecentSearchesSection';
import type { TrendingCategory } from '@/components/TrendingCategoriesGrid';
import { SearchResultQuickView } from '@/components/SearchResultQuickView';
import { SkeletonList } from '@/components/Skeleton';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { MarketplacePageHeader } from '@/components/marketplace/MarketplacePageHeader';
import { MarketplaceResultCard, type MarketplaceResultItem } from '@/components/marketplace/MarketplaceResultCard';
import { MarketplaceEmptyState } from '@/components/marketplace/MarketplaceEmptyState';
import { DemandHeatBanner } from '@/components/marketplace/DemandHeatBanner';
import { RegionalInsightsSection } from '@/components/marketplace/RegionalInsightsSection';

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
}));

const FALLBACK_TRENDING = [
  { id: 'lorcana', name: 'Disney Lorcana', meta: 'Hot right now' },
  { id: 'pokemon', name: 'Pok\u00e9mon Cards', meta: 'Always popular' },
  { id: 'lego', name: 'LEGO', meta: 'Growing fast' },
  { id: 'one_piece', name: 'One Piece', meta: 'Rising demand' },
  { id: 'kpop_merch', name: 'K-pop Merch', meta: 'Surging' },
  { id: 'gunpla', name: 'Gunpla & Model Kits', meta: 'Steady growth' },
];

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
  const { showToast } = useToast();
  const [query, setQuery] = useState("");
  const [recent, setRecent] = useState<string[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [marketplaceResults, setMarketplaceResults] = useState<SearchResult[]>([]);
  const [collectionResults, setCollectionResults] = useState<SearchResult[]>([]);
  const searchIdRef = useRef(0);

  // User search state
  const [userSearchVisible, openUserSearch, closeUserSearch] = useModal();
  const [userSearchQuery, setUserSearchQuery] = useState("");
  const [userSearchResults, setUserSearchResults] = useState<PublicUserProfile[]>([]);
  const [userSearchLoading, setUserSearchLoading] = useState(false);
  const [quickViewItem, setQuickViewItem] = useState<SearchResult | null>(null);
  const [quickViewVisible, openQuickView, closeQuickView] = useModal();
  const [demandHeat, setDemandHeat] = useState<Array<{ item_key: string; title: string; category: string; demand_score: number; search_count: number }>>([]);
  const [regionalDemand, setRegionalDemand] = useState<Array<{ item_key: string; category: string; signal_count: number; region: string }>>([]);
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
        const resp = data as { items?: Array<{ item_key: string; title: string; category: string; demand_score: number; search_count: number }> } | undefined;
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
        const resp = data as { items?: Array<{ item_key: string; category: string; signal_count: number; region: string }> } | undefined;
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

  // Trending categories — fetch from backend, fall back to hardcoded
  const [trendingCategories, setTrendingCategories] = useState<TrendingCategory[]>(FALLBACK_TRENDING);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await collectorsApi.fetchInsights() as { trending_items?: Array<{ category?: string; change_pct?: number }> };
        if (cancelled || !resp?.trending_items?.length) return;
        const catMap = CATEGORIES.reduce<Record<string, string>>((m, c) => { m[c.id] = c.name; return m; }, {});
        const seen = new Set<string>();
        const items: TrendingCategory[] = [];
        for (const t of resp.trending_items) {
          if (!t.category || seen.has(t.category)) continue;
          seen.add(t.category);
          const name = catMap[t.category] ?? t.category;
          const pct = Math.round((t.change_pct ?? 0) * 100);
          items.push({ id: t.category, name, meta: pct > 0 ? `+${pct}% this month` : 'Popular' });
        }
        if (items.length >= 3) setTrendingCategories(items.slice(0, 6));
      } catch (err) {
        logger.warn('[Marketplace] trending categories error:', err);
      }
    })();
    return () => { cancelled = true; };
  }, []);

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

  const allResults = useMemo(
    () => [...marketplaceResults, ...collectionResults],
    [marketplaceResults, collectionResults]
  );

  const topResult = allResults[0] ?? null;
  const otherResults = topResult ? allResults.slice(1) : allResults;

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

    // Run marketplace API + local collection search in parallel
    const [mktResult, colResult] = await Promise.allSettled([
      collectorsApi.marketplaceSearch(q.trim(), searchOpts).catch((err: unknown) => {
        logger.warn("[Search] marketplace search error:", err);
        return null;
      }),
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

  const hasResults = trimmedQuery && (allResults.length > 0 || searchLoading);

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

        {/* Find Collectors button */}
        {!trimmedQuery && (
          <AnimatedPressable
            style={[styles.findCollectorsButton, { borderColor: colors.accent, backgroundColor: colors.accent + '10' }]}
            onPress={openUserSearch}
            accessibilityRole="button"
            accessibilityLabel="Find collectors"
          >
            <Ionicons name="people-outline" size={18} color={colors.accent} />
            <Text style={[styles.findCollectorsText, { color: colors.accent }]}>Find Collectors</Text>
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
            <Text style={[styles.sectionTitle, { color: colors.text }]}>Popular searches</Text>
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
                  const textColor = isDark
                    ? colors.accentText
                    : ci >= 2 ? colors.accentText : colors.text;
                  return (
                    <AnimatedPressable
                      style={[styles.categoryTile, { backgroundColor: bg }]}
                      onPress={() => handleOpenCategory(cat.id)}
                      accessibilityRole="button"
                      accessibilityLabel={`Browse ${cat.name}`}
                    >
                      <Text
                        style={[styles.categoryTileText, { color: textColor }]}
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
              />
            </View>

            {/* Market Pulse — demand heat */}
            <DemandHeatBanner items={demandHeat} onSearchItem={handleChipPress} />

            {/* Regional demand insights */}
            <RegionalInsightsSection items={regionalDemand} onSearchItem={handleChipPress} />

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
          onApply={() => {
            closeFilter();
            if (trimmedQuery) executeSearch(trimmedQuery);
          }}
          onClose={closeFilter}
          onReset={() => {
            setFilterSources([]);
            setFilterConditions([]);
            setFilterMinPrice("");
            setFilterMaxPrice("");
            setFilterSort("relevance");
          }}
        />

        {/* User Search Modal */}
        <Modal
          visible={userSearchVisible}
          animationType="slide"
          presentationStyle="pageSheet"
          onRequestClose={() => {
            closeUserSearch();
            setUserSearchQuery("");
            setUserSearchResults([]);
          }}
        >
          <SafeAreaView style={[styles.filterModal, { backgroundColor: colors.background }]}>
            {/* Header */}
            <View style={[styles.filterHeader, { borderBottomColor: colors.border }]}>
              <TouchableOpacity
                onPress={() => {
                  closeUserSearch();
                  setUserSearchQuery("");
                  setUserSearchResults([]);
                }}
                accessibilityRole="button"
                accessibilityLabel="Close user search"
              >
                <Ionicons name="close" size={24} color={colors.text} />
              </TouchableOpacity>
              <Text style={[styles.filterHeaderTitle, { color: colors.text }]}>Find Collectors</Text>
              <View style={{ width: 24 }} />
            </View>

            {/* Search input */}
            <View style={{ paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8 }}>
              <View style={[styles.searchRow, { borderColor: colors.border }]}>
                <Ionicons name="search-outline" size={18} color={colors.muted} style={{ marginRight: 8 }} />
                <TextInput
                  value={userSearchQuery}
                  onChangeText={setUserSearchQuery}
                  placeholder="Search by name or handle..."
                  placeholderTextColor={colors.muted}
                  autoFocus
                  style={[styles.searchInput, { color: colors.text }]}
                  accessibilityLabel="Search users by name or handle"
                  returnKeyType="search"
                />
                {userSearchQuery.length > 0 && (
                  <TouchableOpacity
                    onPress={() => {
                      setUserSearchQuery("");
                      setUserSearchResults([]);
                    }}
                    accessibilityRole="button"
                    accessibilityLabel="Clear search"
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
            {searchLoading ? (
              <SkeletonList count={6} type="card" />
            ) : (
              <>
                <Text style={[styles.sectionTitle, { color: colors.text }]}>
                  Top result
                </Text>
                {topResult ? (
                  <MarketplaceResultCard
                    item={topResult}
                    onPress={handleOpenResult}
                    isTopResult
                  />
                ) : (
                  <MarketplaceEmptyState />
                )}

                {otherResults.length > 0 && (
                  <>
                    <Text
                      style={[
                        styles.sectionTitle,
                        { color: colors.text, marginTop: 16 },
                      ]}
                    >
                      More results
                    </Text>
                    {otherResults.map((item) => (
                      <MarketplaceResultCard
                        key={item.id}
                        item={item}
                        onPress={handleOpenResult}
                      />
                    ))}
                  </>
                )}

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
  },
  categoryTileText: {
    fontSize: 14,
    fontWeight: "700",
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
