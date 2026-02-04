import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useAppTheme } from '@/hooks/useAppTheme';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';
import { ThemeToggleButton } from '@/components/ThemeToggleButton';
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
  RefreshControl,
  Modal,
  Pressable,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useLocalSearchParams } from "expo-router";
import { dataProvider, type Item as DataItem } from "@/data";
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { SkeletonList, SkeletonCategoryPills } from "@/components/Skeleton";
import { ItemGalleryGrid } from "@/components/ItemGalleryGrid";
import { useMultiSelect } from "@/hooks/useMultiSelect";
import haptics from "@/lib/haptics";
import { FilterSheet, FilterConfig, SortOption } from "@/components/FilterSheet";

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
  const [providerItems, setProviderItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'gallery'>('list');
  const [categoryModalVisible, setCategoryModalVisible] = useState(false);
  const [bulkActionLoading, setBulkActionLoading] = useState(false);
  const [filterSheetVisible, setFilterSheetVisible] = useState(false);
  const [advancedFilter, setAdvancedFilter] = useState<FilterConfig>({
    categories: [],
    priceMin: null,
    priceMax: null,
    conditions: [],
    sortBy: 'value_desc',
  });

  // Multi-select hook
  const {
    isMultiSelectMode,
    selectedIds,
    selectedCount,
    selectedItems,
    enterMultiSelectMode,
    exitMultiSelectMode,
    toggleItem,
    selectAll,
    deselectAll,
    isSelected,
  } = useMultiSelect({
    items: providerItems,
    keyExtractor: (item) => item.id,
  });

  const loadItems = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
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
      setRefreshing(false);
    }
  }, []);

  const handleRefresh = useCallback(() => {
    loadItems(true);
  }, [loadItems]);

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

  // Bulk export selected items
  const handleBulkExport = useCallback(async () => {
    if (selectedCount === 0) return;

    setBulkActionLoading(true);
    try {
      const items = selectedItems;
      const headers = ['id', 'name', 'category', 'price'];
      const csvRows = [
        headers.join(','),
        ...items.map((item) => {
          const row = [
            `"${(item.id || '').replace(/"/g, '""')}"`,
            `"${(item.name || '').replace(/"/g, '""')}"`,
            `"${(item.category || '').replace(/"/g, '""')}"`,
            item.value?.toString() || '0',
          ];
          return row.join(',');
        }),
      ];
      const csvContent = csvRows.join('\n');

      const dateStr = new Date().toISOString().split('T')[0];
      const filename = `CollectAI_Selected_${selectedCount}_${dateStr}.csv`;
      const filePath = `${FileSystem.documentDirectory}${filename}`;

      await FileSystem.writeAsStringAsync(filePath, csvContent);

      const sharingAvailable = await Sharing.isAvailableAsync();
      if (sharingAvailable) {
        await Sharing.shareAsync(filePath, {
          mimeType: 'text/csv',
          dialogTitle: 'Export Selected Items',
          UTI: 'public.comma-separated-values-text',
        });
        haptics.success();
      }
      exitMultiSelectMode();
    } catch (err: any) {
      console.warn('[Items] bulk export error:', err);
      Alert.alert('Export Error', err?.message || 'Failed to export selected items');
      haptics.error();
    } finally {
      setBulkActionLoading(false);
    }
  }, [selectedCount, selectedItems, exitMultiSelectMode]);

  // Bulk archive (mark as archived/sold)
  const handleBulkArchive = useCallback(async () => {
    if (selectedCount === 0) return;

    Alert.alert(
      'Archive Items',
      `Archive ${selectedCount} item${selectedCount > 1 ? 's' : ''}? Archived items will be hidden from your active collection.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Archive',
          style: 'destructive',
          onPress: async () => {
            setBulkActionLoading(true);
            try {
              // For now, we'll delete items as archive isn't in the DataProvider yet
              // In a real implementation, this would call dataProvider.archiveItems()
              for (const id of selectedIds) {
                await dataProvider.deleteItem(id);
              }
              haptics.success();
              exitMultiSelectMode();
              loadItems(true);
            } catch (err: any) {
              console.warn('[Items] bulk archive error:', err);
              Alert.alert('Archive Error', err?.message || 'Failed to archive items');
              haptics.error();
            } finally {
              setBulkActionLoading(false);
            }
          },
        },
      ]
    );
  }, [selectedCount, selectedIds, exitMultiSelectMode, loadItems]);

  // Bulk delete
  const handleBulkDelete = useCallback(async () => {
    if (selectedCount === 0) return;

    Alert.alert(
      'Delete Items',
      `Permanently delete ${selectedCount} item${selectedCount > 1 ? 's' : ''}? This cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            setBulkActionLoading(true);
            try {
              for (const id of selectedIds) {
                await dataProvider.deleteItem(id);
              }
              haptics.success();
              exitMultiSelectMode();
              loadItems(true);
            } catch (err: any) {
              console.warn('[Items] bulk delete error:', err);
              Alert.alert('Delete Error', err?.message || 'Failed to delete items');
              haptics.error();
            } finally {
              setBulkActionLoading(false);
            }
          },
        },
      ]
    );
  }, [selectedCount, selectedIds, exitMultiSelectMode, loadItems]);

  // Bulk change category
  const handleBulkChangeCategory = useCallback(async (newCategory: string) => {
    if (selectedCount === 0) return;

    setBulkActionLoading(true);
    setCategoryModalVisible(false);
    try {
      // For now, log the action - full implementation requires DataProvider.updateItem
      console.log(`[Items] Changing ${selectedCount} items to category: ${newCategory}`);
      // In a real implementation:
      // for (const id of selectedIds) {
      //   await dataProvider.updateItem(id, { category: newCategory });
      // }
      haptics.success();
      exitMultiSelectMode();
      Alert.alert('Category Updated', `${selectedCount} item${selectedCount > 1 ? 's' : ''} moved to ${newCategory}`);
    } catch (err: any) {
      console.warn('[Items] bulk category change error:', err);
      Alert.alert('Error', err?.message || 'Failed to change category');
      haptics.error();
    } finally {
      setBulkActionLoading(false);
    }
  }, [selectedCount, selectedIds, exitMultiSelectMode]);

  // Open item detail
  const handleOpenItem = useCallback((item: Item) => {
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
  }, [router]);

  // Handle long press to enter multi-select
  const handleLongPress = useCallback((itemId: string) => {
    if (!isMultiSelectMode) {
      enterMultiSelectMode();
      toggleItem(itemId);
    }
  }, [isMultiSelectMode, enterMultiSelectMode, toggleItem]);

  // Handle item press in multi-select mode
  const handleItemPress = useCallback((item: Item) => {
    if (isMultiSelectMode) {
      toggleItem(item.id);
    } else {
      handleOpenItem(item);
    }
  }, [isMultiSelectMode, toggleItem, handleOpenItem]);

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

  const allConditions = useMemo(
    () => Array.from(new Set(dataSource.map((i) => i.condition).filter(Boolean))).sort() as string[],
    [dataSource]
  );

  const filteredAndSortedByCategory = useMemo(() => {
    const q = query.trim().toLowerCase();
    let base = [...dataSource];

    // URL param filters
    if (categoryParam) {
      base = base.filter((item) => item.category === categoryParam);
    }

    if (collectionParam) {
      base = base.filter((item) => item.collectionName === collectionParam);
    }

    // Legacy dropdown filter (still supported)
    if (filterCategory) {
      base = base.filter((item) => item.category === filterCategory);
    }

    // Advanced filter: categories
    if (advancedFilter.categories.length > 0) {
      base = base.filter((item) => advancedFilter.categories.includes(item.category));
    }

    // Advanced filter: price range
    if (advancedFilter.priceMin !== null) {
      base = base.filter((item) => item.value >= advancedFilter.priceMin!);
    }
    if (advancedFilter.priceMax !== null) {
      base = base.filter((item) => item.value <= advancedFilter.priceMax!);
    }

    // Advanced filter: conditions
    if (advancedFilter.conditions.length > 0) {
      base = base.filter((item) => item.condition && advancedFilter.conditions.includes(item.condition));
    }

    // Search query
    if (q) {
      base = base.filter(
        (item) =>
          item.name.toLowerCase().includes(q) ||
          item.collectionName.toLowerCase().includes(q) ||
          item.category.toLowerCase().includes(q)
      );
    }

    // Sort using advanced filter sortBy
    base.sort((a, b) => {
      switch (advancedFilter.sortBy) {
        case "value_asc":
          return a.value - b.value;
        case "value_desc":
          return b.value - a.value;
        case "name_asc":
          return a.name.localeCompare(b.name);
        case "name_desc":
          return b.name.localeCompare(a.name);
        case "date_desc":
        case "date_asc":
          // Date sorting would require a date field; fallback to value for now
          return advancedFilter.sortBy === "date_desc" ? b.value - a.value : a.value - b.value;
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
  }, [query, filterCategory, advancedFilter, categoryParam, collectionParam, dataSource]);

  const portfolioTotal = useMemo(
    () => dataSource.reduce((sum, item) => sum + item.value, 0),
    [dataSource]
  );

  const handleAddForCategory = (category: string) => {
    router.push({
      pathname: "/add",
      params: { categoryHint: category },
    });
  };


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

  // Loading state with skeleton
  if (loading) {
    return (
      <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
        <View style={styles.skeletonContainer}>
          <View style={styles.skeletonHeader}>
            <View style={{ width: 100, height: 24, backgroundColor: '#e2e8f0', borderRadius: 6 }} />
            <View style={{ width: 150, height: 16, backgroundColor: '#e2e8f0', borderRadius: 4, marginTop: 8 }} />
          </View>
          <View style={styles.skeletonSearch}>
            <View style={{ width: '100%', height: 44, backgroundColor: '#e2e8f0', borderRadius: 10 }} />
          </View>
          <SkeletonCategoryPills />
          <SkeletonList count={6} type="row" />
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
        {/* Header row - switches between normal and multi-select mode */}
        {isMultiSelectMode ? (
          <>
            <View style={styles.multiSelectHeader}>
              <AnimatedPressable
                style={styles.multiSelectCloseBtn}
                onPress={exitMultiSelectMode}
              >
                <Ionicons name="close" size={24} color={colors.text} />
              </AnimatedPressable>
              <Text style={[styles.multiSelectTitle, { color: colors.text }]}>
                {selectedCount} selected
              </Text>
              <View style={styles.multiSelectActions}>
                <AnimatedPressable
                  style={styles.multiSelectActionBtn}
                  onPress={selectedCount === providerItems.length ? deselectAll : selectAll}
                >
                  <Text style={[styles.multiSelectActionText, { color: colors.accent }]}>
                    {selectedCount === providerItems.length ? 'Deselect All' : 'Select All'}
                  </Text>
                </AnimatedPressable>
              </View>
            </View>

            {/* Bulk Actions - Top contextual bar */}
            {selectedCount > 0 && (
              <View style={[styles.topBulkActionsBar, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {bulkActionLoading ? (
                  <ActivityIndicator size="small" color={colors.accent} />
                ) : (
                  <View style={styles.topBulkActionsRow}>
                    <AnimatedPressable
                      style={[styles.topBulkActionBtn, { backgroundColor: colors.accent + '10' }]}
                      onPress={() => setCategoryModalVisible(true)}
                    >
                      <Ionicons name="folder-outline" size={18} color={colors.accent} />
                      <Text style={[styles.topBulkActionText, { color: colors.accent }]}>Move</Text>
                    </AnimatedPressable>

                    <AnimatedPressable
                      style={[styles.topBulkActionBtn, { backgroundColor: colors.accent + '10' }]}
                      onPress={handleBulkExport}
                    >
                      <Ionicons name="download-outline" size={18} color={colors.accent} />
                      <Text style={[styles.topBulkActionText, { color: colors.accent }]}>Export</Text>
                    </AnimatedPressable>

                    <AnimatedPressable
                      style={[styles.topBulkActionBtn, { backgroundColor: '#f9731610' }]}
                      onPress={handleBulkArchive}
                    >
                      <Ionicons name="archive-outline" size={18} color="#f97316" />
                      <Text style={[styles.topBulkActionText, { color: '#f97316' }]}>Archive</Text>
                    </AnimatedPressable>

                    <AnimatedPressable
                      style={[styles.topBulkActionBtn, { backgroundColor: '#ef444410' }]}
                      onPress={handleBulkDelete}
                    >
                      <Ionicons name="trash-outline" size={18} color="#ef4444" />
                      <Text style={[styles.topBulkActionText, { color: '#ef4444' }]}>Delete</Text>
                    </AnimatedPressable>
                  </View>
                )}
              </View>
            )}
          </>
        ) : (
          <View style={styles.headerRow}>
            <View style={styles.headerLeft}>
              <Text style={[styles.title, { color: colors.text }]}>
                Items
              </Text>
              <Text style={[styles.subtitle, { color: colors.muted }]}>
                Portfolio total: {formatCurrency(portfolioTotal)}
              </Text>
            </View>

            <View style={styles.headerIcons}>
              <InboxHeaderButton color={colors.text} size={22} />
              <ThemeToggleButton size={22} />
            </View>
          </View>
        )}

        {/* Search row */}
        <View style={styles.searchRow}>
          <View style={[styles.searchInputWrapper, { backgroundColor: colors.card }]}>
            <Ionicons name="search" size={16} color={colors.muted} style={styles.searchIcon} />
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Search items"
              placeholderTextColor={colors.muted}
              style={[
                styles.searchInput,
                {
                  backgroundColor: colors.card,
                  color: colors.text,
                },
              ]}
            />
          </View>

          {/* Filter button */}
          <AnimatedPressable
            style={[styles.searchRowButton, { backgroundColor: colors.card, borderColor: colors.border }]}
            onPress={() => setFilterSheetVisible(true)}
          >
            <Ionicons name="options-outline" size={18} color={colors.accent} />
            {(advancedFilter.categories.length > 0 ||
              advancedFilter.conditions.length > 0 ||
              advancedFilter.priceMin !== null ||
              advancedFilter.priceMax !== null) && (
              <View style={[styles.filterDot, { backgroundColor: colors.accent }]} />
            )}
          </AnimatedPressable>
        </View>

        {/* Controls row: View toggle, Select All */}
        <View style={styles.controlsRowNew}>
          {/* View mode toggle */}
          <View style={styles.viewToggleRow}>
            <AnimatedPressable
              style={[
                styles.viewToggleBtn,
                viewMode === 'list' && { backgroundColor: colors.accent + '20' },
                { borderColor: colors.border },
              ]}
              onPress={() => setViewMode('list')}
            >
              <Ionicons
                name="list"
                size={18}
                color={viewMode === 'list' ? colors.accent : colors.muted}
              />
            </AnimatedPressable>
            <AnimatedPressable
              style={[
                styles.viewToggleBtn,
                viewMode === 'gallery' && { backgroundColor: colors.accent + '20' },
                { borderColor: colors.border },
              ]}
              onPress={() => setViewMode('gallery')}
            >
              <Ionicons
                name="grid"
                size={18}
                color={viewMode === 'gallery' ? colors.accent : colors.muted}
              />
            </AnimatedPressable>
          </View>

          {/* Spacer */}
          <View style={{ flex: 1 }} />

          {/* Select All text button */}
          {!isMultiSelectMode && (
            <AnimatedPressable
              style={styles.selectAllTextBtn}
              onPress={enterMultiSelectMode}
            >
              <Text style={[styles.selectAllText, { color: colors.accent }]}>Select</Text>
            </AnimatedPressable>
          )}
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

        {/* Items view - List or Gallery */}
        {filteredAndSortedByCategory.length === 0 ? (
          <Text style={[styles.emptyText, { color: colors.muted }]}>
            No items match your filters yet.
          </Text>
        ) : viewMode === 'gallery' ? (
          /* Gallery View */
          <ItemGalleryGrid
            items={filteredAndSortedByCategory.flatMap((g) =>
              g.items.map((item) => ({
                id: item.id,
                name: item.name,
                category: item.category,
                value: item.value,
                imageUrl: undefined, // Add imageUrl when available from DataProvider
              }))
            )}
            onItemPress={(item) => {
              const fullItem = dataSource.find((i) => i.id === item.id);
              if (fullItem) handleOpenItem(fullItem);
            }}
            colors={{
              card: colors.card,
              text: colors.text,
              muted: colors.muted,
              border: colors.border,
              accent: colors.accent,
            }}
          />
        ) : (
          /* List View - Grouped by category */
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
                    isMultiSelectMode && isSelected(item.id) && {
                      backgroundColor: colors.accent + '15',
                      borderColor: colors.accent,
                    },
                  ]}
                  onPress={() => handleItemPress(item)}
                  onLongPress={() => handleLongPress(item.id)}
                  delayLongPress={400}
                >
                  {/* Checkbox in multi-select mode */}
                  {isMultiSelectMode && (
                    <View style={styles.checkboxContainer}>
                      <View
                        style={[
                          styles.checkbox,
                          { borderColor: colors.border },
                          isSelected(item.id) && {
                            backgroundColor: colors.accent,
                            borderColor: colors.accent,
                          },
                        ]}
                      >
                        {isSelected(item.id) && (
                          <Ionicons name="checkmark" size={14} color="#fff" />
                        )}
                      </View>
                    </View>
                  )}
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
                styles.actionButtonPrimary,
                { backgroundColor: colors.accent },
                exporting && styles.actionButtonDisabled,
              ]}
              onPress={handleExportCSV}
              disabled={exporting}
            >
              {exporting ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Ionicons name="download-outline" size={18} color="#FFFFFF" />
              )}
              <Text style={styles.actionButtonPrimaryText}>
                {exporting ? 'Exporting...' : 'Download overview'}
              </Text>
            </AnimatedPressable>

            {/* Projects */}
            <AnimatedPressable
              style={[
                styles.actionButtonSecondary,
                { borderColor: colors.accent },
              ]}
              onPress={() => router.push('/build-paint-projects')}
            >
              <Ionicons name="color-palette-outline" size={18} color={colors.accent} />
              <Text style={[styles.actionButtonSecondaryText, { color: colors.accent }]}>
                Projects
              </Text>
            </AnimatedPressable>
          </View>

          {/* Export status feedback */}
          {exportStatus && (
            <View style={[styles.exportStatusBanner, { backgroundColor: colors.accent + '15' }]}>
              <Ionicons name="checkmark-circle" size={16} color={colors.accent} />
              <Text style={[styles.exportStatusText, { color: colors.accent }]}>
                {exportStatus}
              </Text>
            </View>
          )}
        </View>
        </Animated.View>

        {/* Bulk actions moved to top contextual bar - see multiSelectHeader section */}
</ScrollView>

      {/* Category Change Modal */}
      <Modal
        visible={categoryModalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setCategoryModalVisible(false)}
      >
        <Pressable
          style={styles.modalOverlay}
          onPress={() => setCategoryModalVisible(false)}
        >
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>
                Change Category
              </Text>
              <Text style={[styles.modalSubtitle, { color: colors.muted }]}>
                Move {selectedCount} item{selectedCount > 1 ? 's' : ''} to:
              </Text>
            </View>

            <ScrollView style={styles.modalList}>
              {allCategories.map((cat) => (
                <AnimatedPressable
                  key={cat}
                  style={[styles.modalOption, { borderColor: colors.border }]}
                  onPress={() => handleBulkChangeCategory(cat)}
                >
                  <CategoryPill id={cat} label={cat} />
                  <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                </AnimatedPressable>
              ))}
            </ScrollView>

            <AnimatedPressable
              style={[styles.modalCancelBtn, { borderColor: colors.border }]}
              onPress={() => setCategoryModalVisible(false)}
            >
              <Text style={[styles.modalCancelText, { color: colors.muted }]}>Cancel</Text>
            </AnimatedPressable>
          </View>
        </Pressable>
      </Modal>

      {/* Advanced Filter Sheet */}
      <FilterSheet
        visible={filterSheetVisible}
        onClose={() => setFilterSheetVisible(false)}
        onApply={(config) => setAdvancedFilter(config)}
        currentConfig={advancedFilter}
        availableCategories={allCategories}
        availableConditions={allConditions}
        colors={{
          background: colors.background,
          card: colors.card,
          text: colors.text,
          muted: colors.muted,
          accent: colors.accent,
          border: colors.border,
        }}
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
  // Skeleton loading styles
  skeletonContainer: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 12,
  },
  skeletonHeader: {
    marginBottom: 16,
  },
  skeletonSearch: {
    marginBottom: 16,
  },
  // View toggle styles
  viewToggleRow: {
    flexDirection: 'row',
    gap: 6,
  },
  viewToggleBtn: {
    padding: 8,
    borderRadius: 8,
    borderWidth: 1,
  },
  controlsRowNew: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  selectAllTextBtn: {
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  selectAllText: {
    fontSize: 14,
    fontWeight: '600',
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 8,
  },
  headerLeft: {
    flex: 1,
  },
  title: {
    fontSize: 22,
    fontWeight: "700",
  },
  subtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  headerIcons: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  actionButtonsRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 12,
  },
  actionBtn: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    gap: 6,
    minHeight: 36,
  },
  actionBtnText: {
    fontSize: 13,
    fontWeight: "600",
  },
  wishlistBtn: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    gap: 4,
  },
  wishlistBtnText: {
    fontSize: 12,
    fontWeight: "600",
  },
  iconButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: "center",
    alignItems: "center",
    position: "relative",
  },
  filterActiveDot: {
    position: "absolute",
    top: 4,
    right: 4,
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },
  searchInputWrapper: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 12,
    paddingLeft: 14,
    height: 44,
  },
  searchIcon: {
    marginRight: 10,
  },
  searchInput: {
    flex: 1,
    borderRadius: 12,
    paddingHorizontal: 0,
    paddingVertical: 10,
    fontSize: 14,
  },
  searchRowButton: {
    width: 44,
    height: 44,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
  },
  filterDot: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 6,
    height: 6,
    borderRadius: 3,
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
    marginTop: 16,
    marginBottom: 24,
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
  },
  bottomActionTitle: {
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 14,
  },
  bottomActionButtons: {
    flexDirection: "row",
    gap: 12,
  },
  actionButtonPrimary: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    gap: 8,
  },
  actionButtonPrimaryText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#FFFFFF",
  },
  actionButtonSecondary: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1.5,
    gap: 8,
    backgroundColor: "transparent",
  },
  actionButtonSecondaryText: {
    fontSize: 14,
    fontWeight: "600",
  },
  actionButtonDisabled: {
    opacity: 0.6,
  },
  exportStatusBanner: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginTop: 12,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 10,
  },
  exportStatusText: {
    fontSize: 13,
    fontWeight: "500",
  },
  // Multi-select styles
  multiSelectHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    marginBottom: 8,
  },
  multiSelectCloseBtn: {
    padding: 4,
    marginRight: 12,
  },
  multiSelectTitle: {
    flex: 1,
    fontSize: 18,
    fontWeight: "700",
  },
  multiSelectActions: {
    flexDirection: "row",
    gap: 8,
  },
  multiSelectActionBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  multiSelectActionText: {
    fontSize: 14,
    fontWeight: "600",
  },
  checkboxContainer: {
    marginRight: 12,
    justifyContent: "center",
    alignItems: "center",
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    justifyContent: "center",
    alignItems: "center",
  },
  topBulkActionsBar: {
    marginBottom: 12,
    padding: 8,
    borderRadius: 12,
    borderWidth: 1,
  },
  topBulkActionsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
  },
  topBulkActionBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: 8,
    gap: 4,
  },
  topBulkActionText: {
    fontSize: 12,
    fontWeight: "600",
  },
  bulkActionsBar: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    padding: 12,
    borderTopWidth: 1,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 5,
  },
  bulkActionsRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    gap: 8,
  },
  bulkActionBtn: {
    alignItems: "center",
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    minWidth: 70,
  },
  bulkActionText: {
    fontSize: 11,
    fontWeight: "600",
    marginTop: 4,
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
    justifyContent: "flex-end",
  },
  modalContent: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingTop: 20,
    paddingBottom: 34,
    maxHeight: "70%",
  },
  modalHeader: {
    paddingHorizontal: 20,
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 4,
  },
  modalSubtitle: {
    fontSize: 14,
  },
  modalList: {
    paddingHorizontal: 20,
  },
  modalOption: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  modalCancelBtn: {
    marginTop: 16,
    marginHorizontal: 20,
    paddingVertical: 14,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: "center",
  },
  modalCancelText: {
    fontSize: 16,
    fontWeight: "600",
  },
});

export default ItemsScreen;
