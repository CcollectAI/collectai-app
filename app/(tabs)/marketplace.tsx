import React, { useMemo, useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  Animated,
  Dimensions,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { ThemeToggleButton } from "@/components/ThemeToggleButton";
import { CATEGORIES } from "@/data/categories";

type Item = {
  id: string;
  name: string;
  category: string;
  collectionName: string;
  value: number;
};

const MOCK_ITEMS: Item[] = [
  {
    id: "1",
    name: "Charizard GX (Alt Art)",
    category: "Pokémon",
    collectionName: "Sun & Moon – Burning Shadows",
    value: 420,
  },
  {
    id: "2",
    name: "Pikachu Illustrator (Proxy)",
    category: "Pokémon",
    collectionName: "Promo / Special",
    value: 999,
  },
  {
    id: "3",
    name: "Lego UCS X-Wing",
    category: "LEGO",
    collectionName: "Ultimate Collector Series",
    value: 320,
  },
  {
    id: "4",
    name: "Hot Wheels RLC Skyline",
    category: "Diecast",
    collectionName: "RLC Exclusives",
    value: 160,
  },
  {
    id: "5",
    name: "Luffy – NYCC Exclusive",
    category: "Funko Pop",
    collectionName: "Convention Exclusives",
    value: 190,
  },
];

// Use category data from the data layer - get all categories for browsing
const BROWSE_CATEGORIES = CATEGORIES.map((cat) => ({
  id: cat.id,
  name: cat.name,
}));

// Tile colors now come from theme.tileScale (Tiffany → cobalt brand scale)

// Compute uniform tile dimensions for 2-col grid
const SCREEN_WIDTH = Dimensions.get("window").width;
const TILE_PAD = 16; // matches content paddingHorizontal
const TILE_GAP = 12;
const TILE_WIDTH = Math.floor((SCREEN_WIDTH - TILE_PAD * 2 - TILE_GAP) / 2);
const TILE_HEIGHT = Math.floor(TILE_WIDTH * 0.62); // ~110-120px for consistent aspect

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);

const SearchScreen: React.FC = () => {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const [query, setQuery] = useState("");
  const [recent, setRecent] = useState<string[]>([
    "Charizard",
    "UCS X-Wing",
    "Lorcana Elsa",
  ]);

  const trimmedQuery = query.trim();

  const filteredItems = useMemo(() => {
    if (!trimmedQuery) return [];
    const q = trimmedQuery.toLowerCase();
    return MOCK_ITEMS.filter(
      (item) =>
        item.name.toLowerCase().includes(q) ||
        item.collectionName.toLowerCase().includes(q) ||
        item.category.toLowerCase().includes(q)
    );
  }, [trimmedQuery]);

  const topResult = filteredItems[0] ?? null;
  const otherResults = topResult ? filteredItems.slice(1) : filteredItems;

  const uniqueCollections = useMemo(
    () =>
      Array.from(
        new Map(
          MOCK_ITEMS.map((item) => [item.collectionName, item])
        ).values()
      ),
    []
  );

  const handleSubmitSearch = () => {
    if (!trimmedQuery) return;
    setRecent((prev) => {
      const existing = prev.filter(
        (term) => term.toLowerCase() !== trimmedQuery.toLowerCase()
      );
      return [trimmedQuery, ...existing].slice(0, 6);
    });
  };

  const handleOpenItem = (item: Item) => {
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
  };

  const handleOpenCategory = (categoryId: string) => {
    router.push(`/categories/${encodeURIComponent(categoryId)}`);
  };

  const handleOpenCollection = (collectionName: string) => {
    router.push({
      pathname: "/items",
      params: { collectionName },
    });
  };

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[
          styles.content,
          { backgroundColor: colors.background },
        ]}
        keyboardShouldPersistTaps="handled"
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
        <View style={styles.searchRow}>
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
                  style={styles.chip}
                  onPress={() => {
                    setQuery(term);
                  }}
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
                  const bg = colors.tileScale[index % colors.tileScale.length];
                  // Use white text on darker tiles (indices 2, 3)
                  const textColor = index % 4 >= 2 ? '#FFFFFF' : colors.text;
                  return (
                    <AnimatedPressable
                      key={cat.id}
                      style={[styles.categoryTile, { backgroundColor: bg }]}
                      onPress={() => handleOpenCategory(cat.id)}
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
                {[
                  { id: 'lorcana', name: 'Disney Lorcana', meta: 'Hot right now' },
                  { id: 'pokemon', name: 'Pokémon Cards', meta: 'Always popular' },
                  { id: 'lego', name: 'LEGO', meta: 'Growing fast' },
                  { id: 'one_piece', name: 'One Piece', meta: 'Rising demand' },
                  { id: 'kpop_merch', name: 'K-pop Merch', meta: 'Surging' },
                  { id: 'gunpla', name: 'Gunpla & Model Kits', meta: 'Steady growth' },
                ].map((cat, index) => (
                  <AnimatedPressable
                    key={cat.id}
                    style={[styles.trendingRow, { borderColor: colors.border }]}
                    onPress={() => handleOpenCategory(cat.id)}
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
            <Text style={[styles.sectionTitle, { color: colors.text }]}>
              Top result
            </Text>
            {topResult ? (
              <AnimatedPressable
                style={styles.resultRow}
                onPress={() => handleOpenItem(topResult)}
              >
                <View style={styles.resultIcon}>
                  <Ionicons name="star-outline" size={18} color={colors.accent} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.resultTitle, { color: colors.text }]}>
                    {topResult.name}
                  </Text>
                  <Text style={[styles.resultMeta, { color: colors.muted }]}>
                    {topResult.category} • {topResult.collectionName}
                  </Text>
                </View>
                <Text style={[styles.resultValue, { color: colors.text }]}>
                  {formatCurrency(topResult.value)}
                </Text>
              </AnimatedPressable>
            ) : (
              <Text style={[styles.emptyText, { color: colors.muted }]}>
                No results yet. Try another search.
              </Text>
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
                    style={styles.resultRow}
                    onPress={() => handleOpenItem(item)}
                  >
                    <View style={styles.resultIcon}>
                      <Ionicons name="card-outline" size={18} color={colors.muted} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.resultTitle, { color: colors.text }]}>
                        {item.name}
                      </Text>
                      <Text style={[styles.resultMeta, { color: colors.muted }]}>
                        {item.category} • {item.collectionName}
                      </Text>
                    </View>
                    <Text style={[styles.resultValue, { color: colors.text }]}>
                      {formatCurrency(item.value)}
                    </Text>
                  </AnimatedPressable>
                ))}
              </>
            )}

            {/* Collections section */}
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
              >
                <View style={styles.collectionIcon}>
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
          </View>
        ) : null}
        </Animated.View>
      </ScrollView>
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
    borderColor: "#E2E8F0",
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
    backgroundColor: "#EFF6FF",
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
    borderBottomColor: "#E2E8F0",
  },
  resultIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 8,
    backgroundColor: "#EFF6FF",
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
    backgroundColor: "#ECFEFF",
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

export default SearchScreen;
