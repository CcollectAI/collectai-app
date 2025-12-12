import React, { useMemo, useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  Pressable,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

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

const CATEGORIES = [
  "Pokémon",
  "Magic: The Gathering",
  "Disney Lorcana",
  "Funko Pop",
  "Diecast",
  "LEGO",
  "Warhammer",
];

const COLORS = {
  background: "#FFFFFF",
  text: "#0F172A",
  muted: "#64748B",
  border: "#E2E8F0",
  accent: "#40C9C6",
  tile1: "#E0F7F9",
  tile2: "#FDE68A",
  tile3: "#FECACA",
  tile4: "#C7D2FE",
};

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);

const SearchScreen: React.FC = () => {
  const router = useRouter();
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

  const handleOpenCategory = (category: string) => {
    router.push({
      pathname: "/items",
      params: { category },
    });
  };

  const handleOpenCollection = (collectionName: string) => {
    router.push({
      pathname: "/items",
      params: { collectionName },
    });
  };

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: COLORS.background }]}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[
          styles.content,
          { backgroundColor: COLORS.background },
        ]}
        keyboardShouldPersistTaps="handled"
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <Text style={[styles.headerTitle, { color: COLORS.text }]}>
            Search
          </Text>
        </View>

        {/* Search input */}
        <View style={styles.searchRow}>
          <Ionicons
            name="search-outline"
            size={18}
            color={COLORS.muted}
            style={{ marginRight: 8 }}
          />
          <TextInput
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={handleSubmitSearch}
            placeholder="Search items & collections"
            placeholderTextColor={COLORS.muted}
            style={[styles.searchInput, { color: COLORS.text }]}
          />
        </View>

        {/* Recent searches */}
        {recent.length > 0 && !trimmedQuery && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: COLORS.text }]}>
              Recent searches
            </Text>
            <View style={styles.chipRow}>
              {recent.map((term) => (
                <Pressable
                  key={term}
                  style={styles.chip}
                  onPress={() => {
                    setQuery(term);
                  }}
                >
                  <Text style={[styles.chipText, { color: COLORS.text }]}>
                    {term}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
        )}

        {/* Browse by category (Spotify-style grid) */}
        {!trimmedQuery && (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: COLORS.text }]}>
              Browse by category
            </Text>
            <View style={styles.categoryGrid}>
              {CATEGORIES.map((cat, index) => {
                const bg =
                  index % 4 === 0
                    ? COLORS.tile1
                    : index % 4 === 1
                    ? COLORS.tile2
                    : index % 4 === 2
                    ? COLORS.tile3
                    : COLORS.tile4;
                return (
                  <Pressable
                    key={cat}
                    style={[styles.categoryTile, { backgroundColor: bg }]}
                    onPress={() => handleOpenCategory(cat)}
                  >
                    <Text style={[styles.categoryTileText, { color: COLORS.text }]}>
                      {cat}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>
        )}

        {/* Results when searching */}
        {trimmedQuery ? (
          <View style={styles.section}>
            <Text style={[styles.sectionTitle, { color: COLORS.text }]}>
              Top result
            </Text>
            {topResult ? (
              <Pressable
                style={styles.resultRow}
                onPress={() => handleOpenItem(topResult)}
              >
                <View style={styles.resultIcon}>
                  <Ionicons name="star-outline" size={18} color={COLORS.accent} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.resultTitle, { color: COLORS.text }]}>
                    {topResult.name}
                  </Text>
                  <Text style={[styles.resultMeta, { color: COLORS.muted }]}>
                    {topResult.category} • {topResult.collectionName}
                  </Text>
                </View>
                <Text style={[styles.resultValue, { color: COLORS.text }]}>
                  {formatCurrency(topResult.value)}
                </Text>
              </Pressable>
            ) : (
              <Text style={[styles.emptyText, { color: COLORS.muted }]}>
                No results yet. Try another search.
              </Text>
            )}

            {otherResults.length > 0 && (
              <>
                <Text
                  style={[
                    styles.sectionTitle,
                    { color: COLORS.text, marginTop: 16 },
                  ]}
                >
                  More results
                </Text>
                {otherResults.map((item) => (
                  <Pressable
                    key={item.id}
                    style={styles.resultRow}
                    onPress={() => handleOpenItem(item)}
                  >
                    <View style={styles.resultIcon}>
                      <Ionicons name="card-outline" size={18} color={COLORS.muted} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.resultTitle, { color: COLORS.text }]}>
                        {item.name}
                      </Text>
                      <Text style={[styles.resultMeta, { color: COLORS.muted }]}>
                        {item.category} • {item.collectionName}
                      </Text>
                    </View>
                    <Text style={[styles.resultValue, { color: COLORS.text }]}>
                      {formatCurrency(item.value)}
                    </Text>
                  </Pressable>
                ))}
              </>
            )}

            {/* Collections section */}
            <Text
              style={[
                styles.sectionTitle,
                { color: COLORS.text, marginTop: 16 },
              ]}
            >
              Collections
            </Text>
            {uniqueCollections.map((item) => (
              <Pressable
                key={item.collectionName}
                style={styles.collectionRow}
                onPress={() => handleOpenCollection(item.collectionName)}
              >
                <View style={styles.collectionIcon}>
                  <Ionicons name="albums-outline" size={18} color={COLORS.accent} />
                </View>
                <View>
                  <Text
                    style={[styles.collectionTitle, { color: COLORS.text }]}
                  >
                    {item.collectionName}
                  </Text>
                  <Text
                    style={[styles.collectionMeta, { color: COLORS.muted }]}
                  >
                    {item.category}
                  </Text>
                </View>
              </Pressable>
            ))}
          </View>
        ) : null}
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
    marginBottom: 12,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: "700",
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
    gap: 8,
  },
  categoryTile: {
    width: "47%",
    borderRadius: 12,
    padding: 12,
    justifyContent: "flex-end",
    minHeight: 80,
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
});

export default SearchScreen;
