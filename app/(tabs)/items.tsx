import type { CollectionItem } from "@/store/collectionStore";
import React, { useEffect, useMemo, useState } from 'react';
import { useAppTheme } from '@/hooks/useAppTheme';
import { Link } from 'expo-router';
import { CategoryPill } from '@/components/CategoryPill';
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
import { useRouter, useLocalSearchParams } from "expo-router";
import { fetchCollectionItems } from "@/store/collectionStore";

type Item = {
  id: string;
  name: string;
  category: string;        // e.g. Pokémon, LEGO
  collectionName: string;  // e.g. "151 Base Set"
  value: number;
  condition?: string;
  notes?: string;
};

const MOCK_ITEMS: CollectionItem[] = [
  {
    id: "1",
    name: "Charizard GX (Alt Art)",
    category: "Pokémon",
    collectionName: "Sun & Moon – Burning Shadows",
    value: 420,
    condition: "PSA 9",
  },
  {
    id: "2",
    name: "Pikachu Illustrator (Proxy)",
    category: "Pokémon",
    collectionName: "Promo / Special",
    value: 999,
    condition: "Proxy",
  },
  {
    id: "3",
    name: "Lego UCS X-Wing",
    category: "LEGO",
    collectionName: "Ultimate Collector Series",
    value: 320,
    condition: "New, sealed",
  },
  {
    id: "4",
    name: "Hot Wheels RLC Skyline",
    category: "Diecast",
    collectionName: "RLC Exclusives",
    value: 160,
    condition: "Loose, mint",
  },
  {
    id: "5",
    name: "Luffy – NYCC Exclusive",
    category: "Funko Pop",
    collectionName: "Convention Exclusives",
    value: 190,
    condition: "Boxed",
  },
];

const LIGHT_COLORS = {
  background: "#FFFFFF",
  text: "#0F172A",
  muted: "#64748B",
  border: "#E2E8F0",
  card: "#F8FAFC",
  accent: "#40C9C6", // Tiffany-ish
};

const DARK_COLORS = {
  background: "#020617",
  text: "#F9FAFB",
  muted: "#9CA3AF",
  border: "#1F2937",
  card: "#020617",
  accent: "#40C9C6",
};


const API_URL =
  process.env.EXPO_PUBLIC_API_URL ?? "http://127.0.0.1:8080";


type SortKey = "value_desc" | "value_asc" | "title";

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);

const ItemsScreen: React.FC = () => {
  const router = useRouter();
  const params = useLocalSearchParams<{ category?: string; collectionName?: string }>();

  const [isDark, setIsDark] = useState(false);
  const colors = isDark ? DARK_COLORS : LIGHT_COLORS;

  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("value_desc");
  const [filterCategory, setFilterCategory] = useState<string | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [sortOpen, setSortOpen] = useState(false);
  const [backendItems, setBackendItems] = useState<CollectionItem[]>([]);
  const [supaItems, setSupaItems] = useState<CollectionItem[]>([]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const res = await fetch(`${API_URL}/items`, {
          method: "GET",
        });
        if (!res.ok) {
          console.log("[Items] backend responded with", res.status);
          return;
        }

        const data: any[] = await res.json();
        if (!Array.isArray(data) || cancelled) return;

        const mapped: CollectionItem[] = data
          .map((it: any) => {
            if (!it || typeof it.id !== "string" || typeof it.name !== "string") {
              return null;
            }

            const value =
              typeof it.estimated_value === "number"
                ? it.estimated_value
                : typeof it.value === "number"
                ? it.value
                : 0;

            const category =
              typeof it.category === "string" && it.category
                ? it.category
                : "Uncategorized";

            const collectionName =
              typeof it.collection_name === "string"
                ? it.collection_name
                : "";

            const condition =
              typeof it.condition === "string"
                ? it.condition
                : undefined;

            const notes =
              typeof it.notes === "string"
                ? it.notes
                : undefined;

            const item: Item = {
              id: it.id,
              name: it.name,
              category,
              collectionName,
              value,
              condition,
              notes,
            };
            return item;
          })
          .filter(Boolean) as CollectionItem[];

        setBackendItems(mapped);
      } catch (e) {
        console.log("[Items] backend fetch failed", e);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadFromSupabase = async () => {
      try {
        const items = await fetchCollectionItems();
        if (!cancelled) {
          setSupaItems(items);
        }
      } catch (e) {
        console.log("[Items] supabase fetch failed", e);
      }
    };

    loadFromSupabase();
    return () => {
      cancelled = false;
    };
  }, []);

  const categoryParam =
    typeof params.category === "string" ? params.category : undefined;
  const collectionParam =
    typeof params.collectionName === "string" ? params.collectionName : undefined;

  const allCategories = useMemo(
    () => Array.from(new Set(MOCK_ITEMS.map((i) => i.category))).sort(),
    []
  );

  const filteredAndSortedByCategory = useMemo(() => {
    const q = query.trim().toLowerCase();
    const source = supaItems.length ? supaItems : (backendItems.length ? backendItems : MOCK_ITEMS);
    let base = [...source];

    if (categoryParam) {
      base = base.filter((item) => item.category === categoryParam);
    }

    if (filterCategory) {
      base = base.filter((item) => item.category === filterCategory);
    }

    if (collectionParam) {
      base = base.filter((item) => item.collectionName === collectionParam);
    }

    if (q) {
      base = base.filter(
        (item) =>
          item.name.toLowerCase().includes(q) ||
          ((item.collectionName ?? "").toLowerCase()).includes(q) ||
          item.category.toLowerCase().includes(q)
      );
    }

    base.sort((a, b) => {
      switch (sortKey) {
        case "value_asc":
          return a.value - b.value;
        case "value_desc":
          return b.value - a.value;
        case "title":
          return a.name.localeCompare(b.name);
        default:
          return 0;
      }
    });

    const groups: { category: string; items: CollectionItem[]; total: number }[] = [];
    for (const item of base) {
      let group = groups.find((g) => g.category === item.category);
      if (!group) {
        group = { category: item.category, items: [], total: 0 };
        groups.push(group);
      }
      group.items.push(item);
      group.total += item.value;
    }

    groups.sort((a, b) => a.category.localeCompare(b.category));

    return groups;
  }, [query, filterCategory, sortKey, categoryParam, collectionParam]);

  const portfolioTotal = useMemo(
    () => MOCK_ITEMS.reduce((sum, item) => sum + item.value, 0),
    []
  );

  const handleOpenItem = (item: CollectionItem) => {
    router.push({
      pathname: "/item/[id]",
      params: {
        id: item.id,
        name: item.name,
        category: item.category,
        collectionName: item.collectionName,
        value: String(item.value),
        condition: item.condition ?? "",
        notes: item.notes ?? "",
      },
    });
  };

  const handleAddForCategory = (category: string) => {
    router.push({
      pathname: "/add",
      params: { categoryHint: category },
    });
  };

  const currentFilterLabel = filterCategory ?? "All categories";
  const currentSortLabel =
    sortKey === "value_desc"
      ? "Value (high → low)"
      : sortKey === "value_asc"
      ? "Value (low → high)"
      : "Title (A → Z)";

  const hasAnyFilter =
    !!categoryParam ||
    !!collectionParam ||
    !!filterCategory ||
    query.trim().length > 0;

  const clearFilters = () => {
    setFilterCategory(null);
    setQuery("");
    try {
      router.setParams({ category: undefined, collectionName: undefined });
    } catch {
      // ignore if not supported
    }
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
        {/* Header row */}
        <View style={styles.headerRow}>
          <View>
            <Text style={[styles.title, { color: colors.text }]}>
              Items
            </Text>
            <Text style={[styles.subtitle, { color: colors.muted }]}>
              Browse and organize your collection.
            </Text>
          </View>

          <View style={styles.headerRight}>
            <View style={{ alignItems: "flex-end", marginRight: 8 }}>
              <Text
                style={[styles.portfolioLabel, { color: colors.muted }]}
              >
                Portfolio total
              </Text>
              <Text
                style={[styles.portfolioValue, { color: colors.text }]}
              >
                {formatCurrency(portfolioTotal)}
              </Text>
            </View>
            <Pressable
              style={styles.iconButton}
              onPress={() => setIsDark((prev) => !prev)}
            >
              <Ionicons
                name={isDark ? "sunny-outline" : "moon-outline"}
                size={18}
                color={colors.muted}
              />
            </Pressable>
          </View>
        </View>

        {/* Search input */}
        <View style={styles.searchContainer}>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Search items"
            placeholderTextColor={colors.muted}
            style={[
              styles.searchInput,
              {
                borderColor: colors.border,
                backgroundColor: colors.card,
                color: colors.text,
              },
            ]}
          />
        </View>

        {/* Filter / Sort dropdown row */}
        <View style={styles.controlsRow}>
          <View style={styles.dropdownWrapper}>
            <Pressable
              style={[
                styles.dropdownButton,
                { borderColor: colors.border, backgroundColor: colors.card },
              ]}
              onPress={() => {
                setFilterOpen((o) => !o);
                setSortOpen(false);
              }}
            >
              <Text
                style={[styles.dropdownLabel, { color: colors.text }]}
                numberOfLines={1}
              >
                {currentFilterLabel}
              </Text>
              <Ionicons
                name={filterOpen ? "chevron-up-outline" : "chevron-down-outline"}
                size={16}
                color={colors.muted}
              />
            </Pressable>
            {filterOpen && (
              <View
                style={[
                  styles.dropdownMenu,
                  { borderColor: colors.border, backgroundColor: colors.card },
                ]}
              >
                <Pressable
                  style={styles.dropdownItem}
                  onPress={() => {
                    setFilterCategory(null);
                    setFilterOpen(false);
                  }}
                >
                  <Text
                    style={[
                      styles.dropdownItemText,
                      { color: colors.text },
                    ]}
                  >
                    All categories
                  </Text>
                </Pressable>
                {allCategories.map((cat) => (
                  <Pressable
                    key={cat}
                    style={styles.dropdownItem}
                    onPress={() => {
                      setFilterCategory(cat);
                      setFilterOpen(false);
                    }}
                  >
                    <Text
                      style={[
                        styles.dropdownItemText,
                        { color: colors.text },
                      ]}
                    >
                      {cat}
                    </Text>
                  </Pressable>
                ))}
              </View>
            )}
          </View>

          <View style={styles.dropdownWrapper}>
            <Pressable
              style={[
                styles.dropdownButton,
                { borderColor: colors.border, backgroundColor: colors.card },
              ]}
              onPress={() => {
                setSortOpen((o) => !o);
                setFilterOpen(false);
              }}
            >
              <Text
                style={[styles.dropdownLabel, { color: colors.text }]}
                numberOfLines={1}
              >
                {currentSortLabel}
              </Text>
              <Ionicons
                name={sortOpen ? "chevron-up-outline" : "chevron-down-outline"}
                size={16}
                color={colors.muted}
              />
            </Pressable>
            {sortOpen && (
              <View
                style={[
                  styles.dropdownMenu,
                  { borderColor: colors.border, backgroundColor: colors.card },
                ]}
              >
                <Pressable
                  style={styles.dropdownItem}
                  onPress={() => {
                    setSortKey("value_desc");
                    setSortOpen(false);
                  }}
                >
                  <Text
                    style={[
                      styles.dropdownItemText,
                      { color: colors.text },
                    ]}
                  >
                    Value (high → low)
                  </Text>
                </Pressable>
                <Pressable
                  style={styles.dropdownItem}
                  onPress={() => {
                    setSortKey("value_asc");
                    setSortOpen(false);
                  }}
                >
                  <Text
                    style={[
                      styles.dropdownItemText,
                      { color: colors.text },
                    ]}
                  >
                    Value (low → high)
                  </Text>
                </Pressable>
                <Pressable
                  style={styles.dropdownItem}
                  onPress={() => {
                    setSortKey("title");
                    setSortOpen(false);
                  }}
                >
                  <Text
                    style={[
                      styles.dropdownItemText,
                      { color: colors.text },
                    ]}
                  >
                    Title (A → Z)
                  </Text>
                </Pressable>
              </View>
            )}
          </View>
        </View>

        {/* Active filter summary */}
        {hasAnyFilter && (
          <View style={styles.filterSummaryRow}>
            <Text style={[styles.filterSummaryText, { color: colors.muted }]}>
              Filtered by:
            </Text>
            <View style={styles.filterChipsRow}>
              {categoryParam && (
                <View style={styles.filterChip}>
                  <Text
                    style={[
                      styles.filterChipText,
                      { color: colors.text },
                    ]}
                  >
                    Category: {categoryParam}
                  </Text>
                </View>
              )}
              {collectionParam && (
                <View style={styles.filterChip}>
                  <Text
                    style={[
                      styles.filterChipText,
                      { color: colors.text },
                    ]}
                  >
                    Collection: {collectionParam}
                  </Text>
                </View>
              )}
              {filterCategory && !categoryParam && (
                <View style={styles.filterChip}>
                  <Text
                    style={[
                      styles.filterChipText,
                      { color: colors.text },
                    ]}
                  >
                    Category: {filterCategory}
                  </Text>
                </View>
              )}
              {query.trim().length > 0 && (
                <View style={styles.filterChip}>
                  <Text
                    style={[
                      styles.filterChipText,
                      { color: colors.text },
                    ]}
                  >
                    Search: "{query.trim()}"
                  </Text>
                </View>
              )}
            </View>
            <Pressable
              onPress={clearFilters}
              style={styles.filterClearButton}
            >
              <Text
                style={[styles.filterClearText, { color: colors.muted }]}
              >
                Clear
              </Text>
            </Pressable>
          </View>
        )}

        {/* Grouped list by category */}
        {filteredAndSortedByCategory.length === 0 ? (
          <Text style={[styles.emptyText, { color: colors.muted }]}>
            No items match your filters yet.
          </Text>
        ) : (
          filteredAndSortedByCategory.map((group) => (
            <View key={group.category} style={styles.categoryBlock}>
              {/* Category header with inline add button */}
              <View style={styles.categoryHeaderRow}>
                <Text
                  style={[
                    styles.categoryTitle,
                    { color: colors.text },
                  ]}
                >
                  {group.category}
                </Text>
                <Pressable
                  style={[
                    styles.categoryAddButton,
                    { borderColor: colors.accent },
                  ]}
                  onPress={() => handleAddForCategory(group.category)}
                >
                  <Ionicons
                    name="add-outline"
                    size={14}
                    color={colors.accent}
                    style={{ marginRight: 4 }}
                  />
                  <Text
                    style={[
                      styles.categoryAddText,
                      { color: colors.accent },
                    ]}
                  >
                    Add
                  </Text>
                </Pressable>
              </View>

              {/* Items in category */}
              {group.items.map((item) => (
                <Pressable
                  key={item.id}
                  style={[
                    styles.itemRow,
                    { borderColor: colors.border },
                  ]}
                  onPress={() => handleOpenItem(item)}
                >
                  <View style={{ flex: 1 }}>
                    <Text
                      style={[
                        styles.itemName,
                        { color: colors.text },
                      ]}
                    >
                      {item.name}
                    </Text>
                    <Text
                      style={[
                        styles.itemMeta,
                        { color: colors.muted },
                      ]}
                    >
                      <CategoryPill id={item.category} label={item.category} /> – {item.collectionName}
                    </Text>
                    {item.condition ? (
                      <Text
                        style={[
                          styles.itemCondition,
                          { color: colors.muted },
                        ]}
                      >
                        {item.condition}
                      </Text>
                    ) : null}
                  </View>
                  <View style={styles.itemRight}>
                    <Text
                      style={[
                        styles.itemValue,
                        { color: colors.text },
                      ]}
                    >
                      {formatCurrency(item.value)}
                    </Text>
                  </View>
                </Pressable>
              ))}

              {/* Category total bottom-right */}
              <View style={styles.categoryFooterRow}>
                <View style={{ flex: 1 }} />
                <View style={{ alignItems: "flex-end" }}>
                  <Text
                    style={[
                      styles.categoryTotalLabel,
                      { color: colors.muted },
                    ]}
                  >
                    Collection total
                  </Text>
                  <Text
                    style={[
                      styles.categoryTotalValue,
                      { color: colors.text },
                    ]}
                  >
                    {formatCurrency(group.total)}
                  </Text>
                </View>
              </View>
            </View>
          ))
        )}
      
        {/* Projects ingress (pro) */}
        <Link href="/build-paint-projects" asChild>
          <Pressable
            accessibilityRole="button"
            style={[
              styles.projectsIngress,
              {
                borderColor: "#D6E4EC",
                backgroundColor: "#FFFFFF",
                marginTop: 12,
                marginBottom: 24,
              },
            ]}
          >
            <View style={styles.projectsIngressLeft}>
              <View
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 10,
                  alignItems: "center",
                  justifyContent: "center",
                  backgroundColor: "rgba(56,214,199,0.18)",
                }}
              >
                <Ionicons name="brush-outline" size={18} color="#0C2233" />
              </View>

              <View style={{ flex: 1 }}>
                <Text style={[styles.projectsIngressText, { color: "#0C2233" }]} numberOfLines={1}>
                  Track build & paint projects
                </Text>
                <Text style={{ marginTop: 4, fontSize: 12, color: "#647589" }} numberOfLines={2}>
                  Steps, notes, % completion — ongoing & finished projects in one place
                </Text>
              </View>
            </View>

            <Ionicons name="chevron-forward" size={18} color="#647589" />
          </Pressable>
        </Link>

</ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  
  projectsIngress: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderRadius: 12,
  },
  projectsIngressLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  projectsIngressText: {
    fontSize: 14,
    fontWeight: "800",
  },

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
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 12,
  },
  title: {
    fontSize: 22,
    fontWeight: "700",
  },
  subtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  headerRight: {
    flexDirection: "row",
    alignItems: "center",
  },
  portfolioLabel: {
    fontSize: 11,
    fontWeight: "500",
  },
  portfolioValue: {
    fontSize: 14,
    fontWeight: "700",
  },
  iconButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
  },
  searchContainer: {
    marginBottom: 10,
  },
  searchInput: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
    fontSize: 13,
  },
  controlsRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 8,
  },
  dropdownWrapper: {
    flex: 1,
    position: "relative",
  },
  dropdownButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  dropdownLabel: {
    fontSize: 12,
    maxWidth: "80%",
  },
  dropdownMenu: {
    position: "absolute",
    top: 38,
    left: 0,
    right: 0,
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 4,
    zIndex: 20,
  },
  dropdownItem: {
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  dropdownItemText: {
    fontSize: 12,
  },
  filterSummaryRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 4,
    marginBottom: 6,
  },
  filterSummaryText: {
    fontSize: 11,
    fontWeight: "500",
  },
  filterChipsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 4,
    flex: 1,
    paddingHorizontal: 4,
  },
  filterChip: {
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "#CBD5F5",
    backgroundColor: "#EFF6FF",
  },
  filterChipText: {
    fontSize: 10,
  },
  filterClearButton: {
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  filterClearText: {
    fontSize: 11,
    textDecorationLine: "underline",
  },
  emptyText: {
    fontSize: 13,
    marginTop: 16,
  },
  categoryBlock: {
    marginTop: 10,
    paddingVertical: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#E2E8F0",
  },
  categoryHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 4,
  },
  categoryTitle: {
    fontSize: 16,
    fontWeight: "700",
  },
  categoryAddButton: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  categoryAddText: {
    fontSize: 11,
    fontWeight: "600",
  },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginTop: 6,
  },
  itemName: {
    fontSize: 14,
    fontWeight: "600",
  },
  itemMeta: {
    fontSize: 12,
    marginTop: 2,
  },
  itemCondition: {
    fontSize: 11,
    marginTop: 2,
  },
  itemRight: {
    marginLeft: 12,
    alignItems: "flex-end",
  },
  itemValue: {
    fontSize: 13,
    fontWeight: "700",
  },
  categoryFooterRow: {
    flexDirection: "row",
    marginTop: 6,
  },
  categoryTotalLabel: {
    fontSize: 11,
    fontWeight: "500",
  },
  categoryTotalValue: {
    fontSize: 13,
    fontWeight: "700",
  },
});

export default ItemsScreen;
