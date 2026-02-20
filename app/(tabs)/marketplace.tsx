import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { formatPrice } from "@/lib/format";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { ThemeToggleButton } from "@/components/ThemeToggleButton";
import { CATEGORIES } from "@/data/categories";
import { collectorsApi } from "@/api/collectorsApi";
import { dataProvider, type Item as DataItem } from "@/data";
import { getJSON, setJSON } from "@/lib/storage";
import logger from "@/utils/logger";

// --- Types for marketplace API results ---
type MarketplaceHit = {
  source: string;
  title: string;
  price: number | null;
  currency: string;
  url: string;
  affiliate_url: string | null;
  affiliate_source: string | null;
  image_url: string | null;
  condition: string | null;
  is_sold: boolean;
  provenance_score: number;
  source_reliability: number;
  recency_score: number;
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
};

const RECENT_SEARCHES_KEY = "collectai_recent_searches";

// Use category data from the data layer - get all categories for browsing
const BROWSE_CATEGORIES = CATEGORIES.map((cat) => ({
  id: cat.id,
  name: cat.name,
}));

const TRENDING_CATEGORIES = [
  { id: 'lorcana', name: 'Disney Lorcana', meta: 'Hot right now' },
  { id: 'pokemon', name: 'Pok\u00e9mon Cards', meta: 'Always popular' },
  { id: 'lego', name: 'LEGO', meta: 'Growing fast' },
  { id: 'one_piece', name: 'One Piece', meta: 'Rising demand' },
  { id: 'kpop_merch', name: 'K-pop Merch', meta: 'Surging' },
  { id: 'gunpla', name: 'Gunpla & Model Kits', meta: 'Steady growth' },
] as const;

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
  const [query, setQuery] = useState("");
  const [recent, setRecent] = useState<string[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [marketplaceResults, setMarketplaceResults] = useState<SearchResult[]>([]);
  const [collectionResults, setCollectionResults] = useState<SearchResult[]>([]);
  const searchIdRef = useRef(0);

  // Load persisted recent searches on mount
  useEffect(() => {
    getJSON<string[]>(RECENT_SEARCHES_KEY, []).then(setRecent);
  }, []);

  const trimmedQuery = query.trim();
  const debouncedQuery = useDebounce(trimmedQuery, 350);

  // Auto-search when debounced query changes (avoids firing on every keystroke)
  useEffect(() => {
    if (debouncedQuery) {
      executeSearch(debouncedQuery);
    } else {
      setMarketplaceResults([]);
      setCollectionResults([]);
    }
  }, [debouncedQuery, executeSearch]);

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

    // Run marketplace API + local collection search in parallel
    const [mktResult, colResult] = await Promise.allSettled([
      collectorsApi.marketplaceSearch(q.trim()).catch((err: unknown) => {
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
    const mktData = mktResult.status === "fulfilled" ? mktResult.value : null;
    const hits: MarketplaceHit[] = mktData?.hits ?? [];
    const mktResults: SearchResult[] = hits
      .filter((h) => !h.is_sold)
      .slice(0, 10)
      .map((h, i) => ({
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
      }));

    // Map collection items
    const colData = colResult.status === "fulfilled" ? colResult.value : [];
    const colResults: SearchResult[] = (colData ?? []).slice(0, 10).map((item) => ({
      id: item.id,
      name: item.name,
      category: item.category,
      collectionName: (item.collections ?? [])[0] ?? "-",
      value: item.price ?? item.priceBand?.q50 ?? 0,
    }));

    // Notify user if both searches failed
    if (mktResult.status === 'rejected' && colResult.status === 'rejected') {
      Alert.alert('Search Error', 'Could not reach the marketplace. Check your connection and try again.');
    }

    setMarketplaceResults(mktResults);
    setCollectionResults(colResults);
    setSearchLoading(false);
    setRefreshing(false);
  }, []);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    if (trimmedQuery) {
      executeSearch(trimmedQuery);
    } else {
      setRefreshing(false);
    }
  }, [trimmedQuery, executeSearch]);

  const handleSubmitSearch = useCallback(() => {
    if (!trimmedQuery) return;
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
  }, [trimmedQuery, executeSearch]);

  // Also trigger search when tapping a recent search chip
  const handleChipPress = useCallback((term: string) => {
    setQuery(term);
    executeSearch(term);
  }, [executeSearch]);

  const handleOpenResult = useCallback((item: SearchResult) => {
    if (item.isMarketplace) {
      const openUrl = item.affiliateUrl || item.externalUrl;
      if (openUrl) Linking.openURL(openUrl).catch((err) => {
        logger.warn('[Marketplace] Failed to open URL', err);
      });
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
  }, [router]);

  const handleOpenCategory = (categoryId: string) => {
    router.push(`/categories/${encodeURIComponent(categoryId)}`);
  };

  const handleOpenCollection = (collectionName: string) => {
    router.push({
      pathname: "/(tabs)/items",
      params: { collectionName },
    });
  };

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
        <View style={styles.headerRow}>
          <View style={styles.headerLeft}>
            <Text style={[styles.headerTitle, { color: colors.text }]}>
              Search
            </Text>
            <Text style={[styles.headerSubtitle, { color: colors.muted }]}>
              Find items, collections, and categories.
            </Text>
          </View>
          <View style={styles.headerIcons}>
            <InboxHeaderButton color={colors.text} size={22} />
            <ThemeToggleButton size={22} />
          </View>
        </View>

        {/* Search input */}
        <View style={[styles.searchRow, { borderColor: colors.border }]}>
          <Ionicons
            name="search-outline"
            size={18}
            color={colors.muted}
            style={{ marginRight: 8 }}
          />
          <TextInput
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={handleSubmitSearch}
            placeholder="Search items & collections"
            placeholderTextColor={colors.muted}
            accessibilityLabel="Search items and collections"
            style={[styles.searchInput, { color: colors.text }]}
          />
        </View>

        {/* Recent searches */}
        {recent.length > 0 && !trimmedQuery && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.text }]}>
              Recent searches
            </Text>
            <View style={styles.chipRow}>
              {recent.map((term) => (
                <AnimatedPressable
                  key={term}
                  style={[styles.chip, { backgroundColor: colors.accent + '15' }]}
                  onPress={() => handleChipPress(term)}
                  accessibilityRole="button"
                  accessibilityLabel={`Search for ${term}`}
                >
                  <Text style={[styles.chipText, { color: colors.text }]}>
                    {term}
                  </Text>
                </AnimatedPressable>
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
              <View style={styles.categoryGrid}>
                {BROWSE_CATEGORIES.map((cat, index) => {
                  // Checkerboard pattern: alternates light/dark per row
                  const row = Math.floor(index / 2);
                  const col = index % 2;
                  const ci = (row + col) % 2 === 0
                    ? (row % 2 === 0 ? 0 : 1)   // even diagonal: lightest ↔ medium
                    : (row % 2 === 0 ? 2 : 3);   // odd diagonal: dark ↔ darkest
                  const darkTileColors = [colors.accent + '70', colors.accent + '90', colors.accent + 'B0', colors.accent + 'D0'];
                  const bg = isDark
                    ? darkTileColors[ci]
                    : colors.tileScale[ci];
                  const textColor = isDark
                    ? '#FFFFFF'
                    : ci >= 2 ? '#FFFFFF' : colors.text;
                  return (
                    <AnimatedPressable
                      key={cat.id}
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
                })}
              </View>
            </View>

            {/* Trending categories */}
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>
                Trending categories
              </Text>
              <View style={styles.trendingList}>
                {TRENDING_CATEGORIES.map((cat, index) => (
                  <AnimatedPressable
                    key={cat.id}
                    style={[styles.trendingRow, { borderColor: colors.border }]}
                    onPress={() => handleOpenCategory(cat.id)}
                    accessibilityRole="button"
                    accessibilityLabel={`${cat.name}, ${cat.meta}`}
                  >
                    <View style={[styles.trendingRank, { backgroundColor: colors.accent + '20' }]}>
                      <Text style={[styles.trendingRankText, { color: colors.accent }]}>
                        {index + 1}
                      </Text>
                    </View>
                    <View style={styles.trendingInfo}>
                      <Text style={[styles.trendingName, { color: colors.text }]}>{cat.name}</Text>
                      <Text style={[styles.trendingMeta, { color: colors.muted }]}>
                        {cat.meta}
                      </Text>
                    </View>
                    <Ionicons name="trending-up" size={18} color={colors.accent} />
                  </AnimatedPressable>
                ))}
              </View>
            </View>
          </>
        )}

        {/* Results when searching */}
        {trimmedQuery ? (
          <View style={styles.section}>
            {searchLoading ? (
              <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 24 }} />
            ) : (
              <>
                <Text style={[styles.sectionTitle, { color: colors.text }]}>
                  Top result
                </Text>
                {topResult ? (
                  <AnimatedPressable
                    style={[styles.resultRow, { borderBottomColor: colors.border }]}
                    onPress={() => handleOpenResult(topResult)}
                    accessibilityRole={topResult.isMarketplace ? "link" : "button"}
                    accessibilityLabel={`${topResult.name}, ${formatPrice(topResult.value)}`}
                  >
                    <View style={[styles.resultIcon, { backgroundColor: colors.accent + '15' }]}>
                      <Ionicons
                        name={topResult.isMarketplace ? "cart-outline" : "star-outline"}
                        size={18}
                        color={colors.accent}
                      />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.resultTitle, { color: colors.text }]}>
                        {topResult.name}
                      </Text>
                      <Text style={[styles.resultMeta, { color: colors.muted }]}>
                        {topResult.isMarketplace
                          ? `${topResult.source || "Marketplace"}${topResult.condition ? ` \u00B7 ${topResult.condition}` : ""}`
                          : `${topResult.category} \u2022 ${topResult.collectionName}`}
                      </Text>
                    </View>
                    <Text style={[styles.resultValue, { color: colors.text }]}>
                      {formatPrice(topResult.value)}
                    </Text>
                  </AnimatedPressable>
                ) : (
                  <View style={styles.noResultsBlock}>
                    <Ionicons name="search-outline" size={32} color={colors.muted} style={{ marginBottom: 8 }} />
                    <Text style={[styles.noResultsTitle, { color: colors.text }]}>
                      No results found
                    </Text>
                    <Text style={[styles.emptyText, { color: colors.muted }]}>
                      Try a different search term or browse by category below.
                    </Text>
                  </View>
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
                      <AnimatedPressable
                        key={item.id}
                        style={[styles.resultRow, { borderBottomColor: colors.border }]}
                        onPress={() => handleOpenResult(item)}
                        accessibilityRole={item.isMarketplace ? "link" : "button"}
                        accessibilityLabel={`${item.name}, ${formatPrice(item.value)}`}
                      >
                        <View style={[styles.resultIcon, { backgroundColor: colors.accent + '15' }]}>
                          <Ionicons
                            name={item.isMarketplace ? "cart-outline" : "card-outline"}
                            size={18}
                            color={item.isMarketplace ? colors.accent : colors.muted}
                          />
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={[styles.resultTitle, { color: colors.text }]}>
                            {item.name}
                          </Text>
                          <Text style={[styles.resultMeta, { color: colors.muted }]}>
                            {item.isMarketplace
                              ? `${item.source || "Marketplace"}${item.condition ? ` \u00B7 ${item.condition}` : ""}`
                              : `${item.category} \u2022 ${item.collectionName}`}
                          </Text>
                        </View>
                        <Text style={[styles.resultValue, { color: colors.text }]}>
                          {formatPrice(item.value)}
                        </Text>
                      </AnimatedPressable>
                    ))}
                  </>
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
  headerRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
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
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 999,
    borderWidth: 1,
    borderColor: undefined,
    paddingHorizontal: 12,
    paddingVertical: 6,
    marginBottom: 12,
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
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  chip: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
    backgroundColor: undefined,
  },
  chipText: {
    fontSize: 12,
    fontWeight: "500",
  },
  categoryGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: TILE_GAP,
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
  resultRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: undefined,
  },
  resultIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 8,
    backgroundColor: undefined,
  },
  resultTitle: {
    fontSize: 14,
    fontWeight: "600",
  },
  resultMeta: {
    fontSize: 12,
    marginTop: 2,
  },
  resultValue: {
    fontSize: 13,
    fontWeight: "700",
    marginLeft: 8,
  },
  emptyText: {
    fontSize: 13,
    marginTop: 4,
    textAlign: "center",
  },
  noResultsBlock: {
    alignItems: "center",
    paddingVertical: 24,
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
    backgroundColor: undefined,
  },
  collectionTitle: {
    fontSize: 13,
    fontWeight: "600",
  },
  collectionMeta: {
    fontSize: 11,
    marginTop: 2,
  },
  trendingList: {
    gap: 8,
  },
  trendingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
  },
  trendingRank: {
    width: 28,
    height: 28,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  trendingRankText: {
    fontSize: 14,
    fontWeight: '700',
  },
  trendingInfo: {
    flex: 1,
  },
  trendingName: {
    fontSize: 14,
    fontWeight: '600',
  },
  trendingMeta: {
    fontSize: 11,
    marginTop: 2,
  },
});

function SearchScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Search">
      <SearchScreen />
    </ScreenErrorBoundary>
  );
}

export default SearchScreenWithBoundary;
