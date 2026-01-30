import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useAppTheme } from '@/hooks/useAppTheme';
import { Link } from 'expo-router';
import { CategoryPill } from '@/components/CategoryPill';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
  Animated,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useLocalSearchParams } from "expo-router";
import { dataProvider, type Item as DataItem } from "@/data";
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { AnimatedPressable, useEnterReveal } from "@/motion";

type Item = {
  id: string;
  name: string;
  category: string;        // e.g. Pokémon, LEGO
  collectionName: string;  // e.g. "151 Base Set"
  value: number;
  condition?: string;
  notes?: string;
};

const MOCK_ITEMS: Item[] = [
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
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });

  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("value_desc");
  const [filterCategory, setFilterCategory] = useState<string | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);
  const [sortOpen, setSortOpen] = useState(false);
  const [providerItems, setProviderItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState<string | null>(null);

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const items = await dataProvider.listItems();
      // Map DataProvider items to screen Item shape
      const mapped: Item[] = items.map((it: DataItem) => ({
        id: it.id,
        name: it.name,
        category: it.category,
        collectionName: "", // DataProvider doesn't have this yet
        value: it.price,
        condition: undefined,
        notes: undefined,
      }));
      setProviderItems(mapped);
    } catch (e: any) {
      console.warn("[Items] dataProvider.listItems failed", e);
      setError(e?.message || "Failed to load items");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  // Export all items to CSV
  const handleExportCSV = useCallback(async () => {
    setExporting(true);
    setExportStatus(null);

    try {
      // Fetch all items via DataProvider
      const items = await dataProvider.listItems();

      if (items.length === 0) {
        setExportStatus('No items to export');
        setExporting(false);
        return;
      }

      // Generate CSV content
      const headers = ['id', 'name', 'category', 'price', 'imageUrl'];
      const csvRows = [
        headers.join(','),
        ...items.map((item) => {
          const row = [
            `"${(item.id || '').replace(/"/g, '""')}"`,
            `"${(item.name || '').replace(/"/g, '""')}"`,
            `"${(item.category || '').replace(/"/g, '""')}"`,
            item.price?.toString() || '0',
            `"${(item.imageUrl || '').replace(/"/g, '""')}"`,
          ];
          return row.join(',');
        }),
      ];
      const csvContent = csvRows.join('\n');

      // Generate filename with date
      const dateStr = new Date().toISOString().split('T')[0];
      const filename = `CollectAI_Collection_${dateStr}.csv`;
      const filePath = `${FileSystem.documentDirectory}${filename}`;

      // Write file (use string 'utf8' for encoding)
      await FileSystem.writeAsStringAsync(filePath, csvContent);

      // Check if sharing is available
      const sharingAvailable = await Sharing.isAvailableAsync();
      if (sharingAvailable) {
        await Sharing.shareAsync(filePath, {
          mimeType: 'text/csv',
          dialogTitle: 'Export Collection',
          UTI: 'public.comma-separated-values-text',
        });
        setExportStatus('Exported successfully');
      } else {
        Alert.alert(
          'Export Complete',
          `File saved to: ${filename}\n\nSharing is not available on this device.`
        );
        setExportStatus('Saved (sharing unavailable)');
      }
    } catch (err: any) {
      console.warn('[Items] export error:', err);
      setExportStatus('Export failed');
      Alert.alert('Export Error', err?.message || 'Failed to export items');
    } finally {
      setExporting(false);
      // Clear status after 3 seconds
      setTimeout(() => setExportStatus(null), 3000);
    }
  }, []);

  const categoryParam =
    typeof params.category === "string" ? params.category : undefined;
  const collectionParam =
    typeof params.collectionName === "string" ? params.collectionName : undefined;

  // Use providerItems if available, otherwise fall back to MOCK_ITEMS
  const dataSource = providerItems.length > 0 ? providerItems : MOCK_ITEMS;

  const allCategories = useMemo(
    () => Array.from(new Set(dataSource.map((i) => i.category))).sort(),
    [dataSource]
  );

  const filteredAndSortedByCategory = useMemo(() => {
    const q = query.trim().toLowerCase();
    let base = [...dataSource];

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
          item.collectionName.toLowerCase().includes(q) ||
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

    const groups: { category: string; items: Item[]; total: number }[] = [];
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
  }, [query, filterCategory, sortKey, categoryParam, collectionParam, dataSource]);

  const portfolioTotal = useMemo(
    () => dataSource.reduce((sum, item) => sum + item.value, 0),
    [dataSource]
  );

  const handleOpenItem = (item: Item) => {
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

  // Loading state
  if (loading) {
    return (
      <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
          <Text style={[styles.loadingText, { color: colors.muted }]}>Loading items...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Error state
  if (error) {
    return (
      <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
        <View style={styles.centerContainer}>
          <Ionicons name="alert-circle-outline" size={48} color="#B42318" />
          <Text style={[styles.errorText, { color: "#B42318" }]}>{error}</Text>
          <AnimatedPressable style={[styles.retryBtn, { backgroundColor: colors.accent }]} onPress={loadItems}>
            <Text style={styles.retryText}>Retry</Text>
          </AnimatedPressable>
        </View>
      </SafeAreaView>
    );
  }

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

          <View style={{ alignItems: "flex-end" }}>
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
            <AnimatedPressable
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
            </AnimatedPressable>
            {filterOpen && (
              <View
                style={[
                  styles.dropdownMenu,
                  { borderColor: colors.border, backgroundColor: colors.card },
                ]}
              >
                <AnimatedPressable
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
                </AnimatedPressable>
                {allCategories.map((cat) => (
                  <AnimatedPressable
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
                  </AnimatedPressable>
                ))}
              </View>
            )}
          </View>

          <View style={styles.dropdownWrapper}>
            <AnimatedPressable
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
            </AnimatedPressable>
            {sortOpen && (
              <View
                style={[
                  styles.dropdownMenu,
                  { borderColor: colors.border, backgroundColor: colors.card },
                ]}
              >
                <AnimatedPressable
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
                </AnimatedPressable>
                <AnimatedPressable
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
                </AnimatedPressable>
                <AnimatedPressable
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
                </AnimatedPressable>
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
            <AnimatedPressable
              onPress={clearFilters}
              style={styles.filterClearButton}
            >
              <Text
                style={[styles.filterClearText, { color: colors.muted }]}
              >
                Clear
              </Text>
            </AnimatedPressable>
          </View>
        )}

        {/* Grouped list by category */}
        {filteredAndSortedByCategory.length === 0 ? (
          <Text style={[styles.emptyText, { color: colors.muted }]}>
            No items match your filters yet.
          </Text>
        ) : (
          filteredAndSortedByCategory.map((group) => (
            <View key={group.category} style={[styles.categoryBlock, { borderTopColor: colors.border }]}>
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
                <AnimatedPressable
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
                </AnimatedPressable>
              </View>

              {/* Items in category */}
              {group.items.map((item) => (
                <AnimatedPressable
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
                </AnimatedPressable>
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

        {/* Bottom Action Bar */}
        <View style={[styles.bottomActionBar, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <Text style={[styles.bottomActionTitle, { color: colors.text }]}>
            Actions
          </Text>

          <View style={styles.bottomActionButtons}>
            {/* Download Overview (Export CSV) */}
            <AnimatedPressable
              style={[
                styles.actionButton,
                {
                  backgroundColor: colors.card,
                  borderColor: colors.accent,
                },
                exporting && styles.actionButtonDisabled,
              ]}
              onPress={handleExportCSV}
              disabled={exporting}
            >
              {exporting ? (
                <ActivityIndicator size="small" color={colors.accent} />
              ) : (
                <Ionicons
                  name="download-outline"
                  size={18}
                  color={colors.accent}
                />
              )}
              <Text
                style={[
                  styles.actionButtonText,
                  { color: colors.accent },
                ]}
              >
                {exporting ? 'Exporting...' : 'Download overview'}
              </Text>
            </AnimatedPressable>

            {/* Build & Paint Projects */}
            <AnimatedPressable
              style={[
                styles.actionButton,
                {
                  backgroundColor: colors.card,
                  borderColor: colors.accent,
                },
              ]}
              onPress={() => router.push('/build-paint-projects')}
            >
              <Ionicons
                name="color-palette-outline"
                size={18}
                color={colors.accent}
              />
              <Text
                style={[
                  styles.actionButtonText,
                  { color: colors.accent },
                ]}
              >
                Build & Paint Projects
              </Text>
            </AnimatedPressable>
          </View>

          {/* Export status feedback */}
          {exportStatus && (
            <Text style={[styles.exportStatus, { color: colors.muted }]}>
              {exportStatus}
            </Text>
          )}
        </View>
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
  // Loading/Error states
  centerContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 24,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    fontWeight: "600",
  },
  errorText: {
    marginTop: 12,
    fontSize: 14,
    fontWeight: "600",
    textAlign: "center",
  },
  retryBtn: {
    marginTop: 16,
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 6,
  },
  retryText: {
    color: "#FFFFFF",
    fontWeight: "700",
    fontSize: 14,
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
  // Bottom action bar
  bottomActionBar: {
    marginTop: 8,
    marginBottom: 24,
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#D6E4EC",
    backgroundColor: "#FFFFFF",
  },
  bottomActionTitle: {
    fontSize: 15,
    fontWeight: "600",
    marginBottom: 12,
  },
  bottomActionButtons: {
    flexDirection: "row",
    gap: 10,
  },
  actionButton: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 10,
    borderWidth: 1,
    gap: 6,
  },
  actionButtonDisabled: {
    opacity: 0.6,
  },
  actionButtonText: {
    fontSize: 12,
    fontWeight: "600",
  },
  exportStatus: {
    marginTop: 8,
    fontSize: 11,
    textAlign: "center",
  },
});

export default ItemsScreen;
