import React, { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useAppTheme } from '@/hooks/useAppTheme';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';
import { ThemeToggleButton } from '@/components/ThemeToggleButton';
import { CategoryPill } from '@/components/CategoryPill';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  SectionList,
  ActivityIndicator,
  Alert,
  Animated,
  RefreshControl,
  Modal,
  KeyboardAvoidingView,
  Platform,
  Image,
  type NativeSyntheticEvent,
  type NativeScrollEvent,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useLocalSearchParams } from "expo-router";
import { dataProvider, type Item as DataItem } from "@/data";
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { AnimatedPressable, useEnterReveal, useStaggerReveal } from "@/motion";
import { SkeletonList, SkeletonCategoryPills } from "@/components/Skeleton";
import { ItemGalleryGrid } from "@/components/ItemGalleryGrid";
import { useMultiSelect } from "@/hooks/useMultiSelect";
import {
  useOptimisticBulkArchive,
  useOptimisticBulkDelete,
} from "@/hooks/useOptimisticItems";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import haptics from "@/lib/haptics";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { formatPrice } from "@/lib/format";
import { useToast } from "@/components/Toast";
import { FilterSheet, FilterConfig, SortOption } from "@/components/FilterSheet";
import AsyncStorage from '@react-native-async-storage/async-storage';
import logger from "@/utils/logger";

type Item = {
  id: string;
  name: string;
  category: string;        // e.g. Pokémon, LEGO
  collectionName: string;  // e.g. "151 Base Set"
  value: number;
  condition?: string;
  notes?: string;
  imageUrl?: string;
};

// Semantic action colors (theme-independent)
const ACTION_COLORS = {
  archive: '#f97316',
  archiveBg: '#f9731610',
  danger: '#ef4444',
  dangerBg: '#ef444410',
} as const;

type SortKey = "value_desc" | "value_asc" | "title";

const VIEW_MODE_KEY = '@collectai/items_view_mode';

const ItemsScreen: React.FC = () => {
  const router = useRouter();
  const params = useLocalSearchParams<{ category?: string; collectionName?: string }>();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { showToast } = useToast();

  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("value_desc");
  const [filterCategory, setFilterCategory] = useState<string | null>(null);
  // Paginated data fetching
  const itemFetcher = useCallback(
    async (limit: number, offset: number): Promise<Item[]> => {
      const items = await dataProvider.listItems({ limit, offset });
      return items.map((it: DataItem) => ({
        id: it.id,
        name: it.name,
        category: it.category,
        collectionName: "",
        value: it.price,
        condition: undefined,
        notes: undefined,
        imageUrl: (it as any).imageUrl,
      }));
    },
    [],
  );

  const {
    items: providerItems,
    isLoading: loading,
    isLoadingMore,
    hasMore,
    error,
    loadMore,
    refresh: paginatedRefresh,
    setItems: setProviderItems,
  } = usePaginatedList<Item>(itemFetcher, { pageSize: 20 });

  // Stagger animation for list items — compute flat index map
  const { getItemStyle: getStaggerStyle } = useStaggerReveal({
    count: (providerItems ?? []).length,
    enabled: settings.animationsEnabled && !loading,
    staggerMs: 40,
  });
  // Pre-compute flat index per item id for stagger animation
  const staggerIndexMap = useRef(new Map<string, number>());
  useEffect(() => {
    const map = new Map<string, number>();
    let idx = 0;
    for (const item of (providerItems ?? [])) {
      map.set(item.id, idx++);
    }
    staggerIndexMap.current = map;
  }, [providerItems]);

  const [refreshing, setRefreshing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'gallery'>('list');

  // Restore persisted view mode on mount
  useEffect(() => {
    AsyncStorage.getItem(VIEW_MODE_KEY).then((stored) => {
      if (stored === 'list' || stored === 'gallery') setViewMode(stored);
    }).catch(() => {});
  }, []);

  // Toggle handler that persists the preference
  const toggleViewMode = useCallback(() => {
    const next = viewMode === 'list' ? 'gallery' : 'list';
    setViewMode(next);
    AsyncStorage.setItem(VIEW_MODE_KEY, next).catch(() => {});
  }, [viewMode]);

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

  // Stable ref for refresh so optimistic rollback callbacks stay current
  const refreshRef = useRef(paginatedRefresh);
  refreshRef.current = paginatedRefresh;
  const stableReload = useCallback(() => { refreshRef.current(); }, []);

  // Optimistic mutation hooks for bulk operations
  const optimisticBulkArchive = useOptimisticBulkArchive(setProviderItems, stableReload);
  const optimisticBulkDelete = useOptimisticBulkDelete(setProviderItems, stableReload);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await paginatedRefresh();
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
    setRefreshing(false);
  }, [paginatedRefresh, settings.hapticsEnabled]);

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

      if (!FileSystem.documentDirectory) {
        showToast({ message: 'File storage not available on this platform', type: 'error' });
        setExporting(false);
        return;
      }

      const filePath = `${FileSystem.documentDirectory}${filename}`;

      // Write file
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
        showToast({ message: `Saved to ${filename}`, type: 'info', duration: 4000 });
        setExportStatus('Saved (sharing unavailable)');
      }
    } catch (err: unknown) {
      logger.warn('[Items] export error:', err);
      setExportStatus('Export failed');
      showToast({ message: 'Failed to export items', type: 'error' });
    } finally {
      setExporting(false);
      // Clear status after 3 seconds
      setTimeout(() => setExportStatus(null), 3000);
    }
  }, [showToast]);

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
    } catch (err: unknown) {
      logger.warn('[Items] bulk export error:', err);
      showToast({ message: (err as Error)?.message || 'Failed to export selected items', type: 'error' });
      haptics.error();
    } finally {
      setBulkActionLoading(false);
    }
  }, [selectedCount, selectedItems, exitMultiSelectMode]);

  // Bulk archive (mark as archived/sold) — with optimistic update
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
            const ids = [...selectedIds];
            exitMultiSelectMode();
            // Optimistic: removes items from list immediately, reverts on error
            await optimisticBulkArchive.mutate(ids);
            if (!optimisticBulkArchive.error) {
              haptics.success();
            } else {
              showToast({ message: optimisticBulkArchive.error.message || 'Failed to archive items', type: 'error' });
              haptics.error();
            }
          },
        },
      ]
    );
  }, [selectedCount, selectedIds, exitMultiSelectMode, optimisticBulkArchive]);

  // Bulk delete — with optimistic update
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
            const ids = [...selectedIds];
            exitMultiSelectMode();
            // Optimistic: removes items from list immediately, reverts on error
            await optimisticBulkDelete.mutate(ids);
            if (!optimisticBulkDelete.error) {
              haptics.success();
            } else {
              showToast({ message: optimisticBulkDelete.error.message || 'Failed to delete items', type: 'error' });
              haptics.error();
            }
          },
        },
      ]
    );
  }, [selectedCount, selectedIds, exitMultiSelectMode, optimisticBulkDelete]);

  // Bulk change category
  const handleBulkChangeCategory = useCallback(async (newCategory: string) => {
    if (selectedCount === 0) return;

    const count = selectedCount;
    const ids = [...selectedIds];
    setBulkActionLoading(true);
    setCategoryModalVisible(false);
    try {
      for (const id of ids) {
        await dataProvider.updateItem(id, { category: newCategory });
      }
      haptics.success();
      exitMultiSelectMode();
      showToast({ message: `${count} item${count > 1 ? 's' : ''} moved to ${newCategory}`, type: 'success' });
      await paginatedRefresh();
    } catch (err: unknown) {
      logger.warn('[Items] bulk category change error:', err);
      showToast({ message: 'Could not update items', type: 'error' });
      haptics.error();
    } finally {
      setBulkActionLoading(false);
    }
  }, [selectedCount, selectedIds, exitMultiSelectMode, paginatedRefresh]);

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

  const dataSource = providerItems;

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

  // Memoize gallery-mode items to avoid recomputing flatMap on every render
  const galleryItems = useMemo(
    () =>
      filteredAndSortedByCategory.flatMap((g) =>
        g.items.map((item) => ({
          id: item.id,
          name: item.name,
          category: item.category,
          value: item.value,
          imageUrl: item.imageUrl,
        }))
      ),
    [filteredAndSortedByCategory]
  );

  const portfolioTotal = useMemo(
    () => dataSource.reduce((sum, item) => sum + item.value, 0),
    [dataSource]
  );

  const handleAddForCategory = useCallback((category: string) => {
    router.push({
      pathname: "/add",
      params: { categoryHint: category },
    });
  }, [router]);

  // SectionList sections derived from grouped data
  const sections = useMemo(() =>
    filteredAndSortedByCategory.map(group => ({
      title: group.category,
      data: group.items,
      total: group.total,
    })),
    [filteredAndSortedByCategory]
  );

  const hasAnyFilter =
    !!categoryParam ||
    !!collectionParam ||
    !!filterCategory ||
    query.trim().length > 0;

  // Detect when ScrollView is near the bottom to trigger loadMore
  const handleScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const { contentOffset, layoutMeasurement, contentSize } = event.nativeEvent;
      const distanceFromBottom = contentSize.height - layoutMeasurement.height - contentOffset.y;
      if (distanceFromBottom < layoutMeasurement.height * 0.5) {
        loadMore();
      }
    },
    [loadMore],
  );

  // Compute total filtered items count for display
  const filteredItemCount = useMemo(
    () => filteredAndSortedByCategory.reduce((sum, g) => sum + g.items.length, 0),
    [filteredAndSortedByCategory]
  );

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
          <AnimatedPressable style={[styles.retryBtn, { backgroundColor: colors.accent }]} onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            paginatedRefresh();
          }} accessibilityRole="button" accessibilityLabel="Retry loading items">
            <Text style={styles.retryText}>Retry</Text>
          </AnimatedPressable>
        </View>
      </SafeAreaView>
    );
  }

  // Shared header element for both gallery ScrollView and list SectionList
  const headerElement = (
    <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
      {/* Header row - switches between normal and multi-select mode */}
      {isMultiSelectMode ? (
        <>
          <View style={styles.multiSelectHeader}>
            <AnimatedPressable
              style={styles.multiSelectCloseBtn}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                exitMultiSelectMode();
              }}
              accessibilityRole="button"
              accessibilityLabel="Exit multi-select mode"
            >
              <Ionicons name="close" size={24} color={colors.text} />
            </AnimatedPressable>
            <Text style={[styles.multiSelectTitle, { color: colors.text }]}>
              {selectedCount} selected
            </Text>
            <View style={styles.multiSelectActions}>
              <AnimatedPressable
                style={styles.multiSelectActionBtn}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  (selectedCount === providerItems.length ? deselectAll : selectAll)();
                }}
                accessibilityRole="button"
                accessibilityLabel={selectedCount === providerItems.length ? 'Deselect all items' : 'Select all items'}
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
              {(bulkActionLoading || optimisticBulkArchive.isLoading || optimisticBulkDelete.isLoading) ? (
                <ActivityIndicator size="small" color={colors.accent} />
              ) : (
                <View style={styles.topBulkActionsRow}>
                  <AnimatedPressable
                    style={[styles.topBulkActionBtn, { backgroundColor: colors.accent + '10' }]}
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                      setCategoryModalVisible(true);
                    }}
                    accessibilityRole="button"
                    accessibilityLabel="Move selected items to category"
                  >
                    <Ionicons name="folder-outline" size={18} color={colors.accent} />
                    <Text style={[styles.topBulkActionText, { color: colors.accent }]}>Move</Text>
                  </AnimatedPressable>

                  <AnimatedPressable
                    style={[styles.topBulkActionBtn, { backgroundColor: colors.accent + '10' }]}
                    onPress={() => {
                      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
                      handleBulkExport();
                    }}
                    accessibilityRole="button"
                    accessibilityLabel="Export selected items"
                  >
                    <Ionicons name="download-outline" size={18} color={colors.accent} />
                    <Text style={[styles.topBulkActionText, { color: colors.accent }]}>Export</Text>
                  </AnimatedPressable>

                  <AnimatedPressable
                    style={[styles.topBulkActionBtn, { backgroundColor: ACTION_COLORS.archiveBg }]}
                    onPress={() => {
                      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
                      handleBulkArchive();
                    }}
                    accessibilityRole="button"
                    accessibilityLabel="Archive selected items"
                  >
                    <Ionicons name="archive-outline" size={18} color={ACTION_COLORS.archive} />
                    <Text style={[styles.topBulkActionText, { color: ACTION_COLORS.archive }]}>Archive</Text>
                  </AnimatedPressable>

                  <AnimatedPressable
                    style={[styles.topBulkActionBtn, { backgroundColor: ACTION_COLORS.dangerBg }]}
                    onPress={() => {
                      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
                      handleBulkDelete();
                    }}
                    accessibilityRole="button"
                    accessibilityLabel="Delete selected items"
                  >
                    <Ionicons name="trash-outline" size={18} color={ACTION_COLORS.danger} />
                    <Text style={[styles.topBulkActionText, { color: ACTION_COLORS.danger }]}>Delete</Text>
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
              Portfolio total: {formatPrice(portfolioTotal)}
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
            accessibilityLabel="Search items"
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
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            setFilterSheetVisible(true);
          }}
          accessibilityRole="button"
          accessibilityLabel="Open filters"
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
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              if (viewMode !== 'list') toggleViewMode();
            }}
            accessibilityRole="button"
            accessibilityLabel="List view"
            accessibilityState={{ selected: viewMode === 'list' }}
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
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              if (viewMode !== 'gallery') toggleViewMode();
            }}
            accessibilityRole="button"
            accessibilityLabel="Gallery view"
            accessibilityState={{ selected: viewMode === 'gallery' }}
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
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              enterMultiSelectMode();
            }}
            accessibilityRole="button"
            accessibilityLabel="Enter selection mode"
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
              <View style={[styles.filterChip, { borderColor: colors.border, backgroundColor: colors.accent + '15' }]}>
                <Text style={[styles.filterChipText, { color: colors.text }]}>
                  Category: {categoryParam}
                </Text>
              </View>
            )}
            {collectionParam && (
              <View style={[styles.filterChip, { borderColor: colors.border, backgroundColor: colors.accent + '15' }]}>
                <Text style={[styles.filterChipText, { color: colors.text }]}>
                  Collection: {collectionParam}
                </Text>
              </View>
            )}
            {filterCategory && !categoryParam && (
              <View style={[styles.filterChip, { borderColor: colors.border, backgroundColor: colors.accent + '15' }]}>
                <Text style={[styles.filterChipText, { color: colors.text }]}>
                  Category: {filterCategory}
                </Text>
              </View>
            )}
            {query.trim().length > 0 && (
              <View style={[styles.filterChip, { borderColor: colors.border, backgroundColor: colors.accent + '15' }]}>
                <Text style={[styles.filterChipText, { color: colors.text }]}>
                  Search: "{query.trim()}"
                </Text>
              </View>
            )}
          </View>
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              clearFilters();
            }}
            style={styles.filterClearButton}
            accessibilityRole="button"
            accessibilityLabel="Clear all filters"
          >
            <Text style={[styles.filterClearText, { color: colors.muted }]}>
              Clear
            </Text>
          </AnimatedPressable>
        </View>
      )}

      {/* Item count */}
      <Text style={[styles.itemCount, { color: colors.muted }]}>
        {filteredItemCount} item{filteredItemCount !== 1 ? 's' : ''}
      </Text>
    </Animated.View>
  );

  // Shared footer element
  const footerElement = (
    <>
      {/* Bottom Action Bar */}
      <View style={[styles.bottomActionBar, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <Text style={[styles.bottomActionTitle, { color: colors.text }]}>
          Actions
        </Text>

        <View style={styles.bottomActionButtons}>
          <AnimatedPressable
            style={[
              styles.actionButtonPrimary,
              { backgroundColor: colors.accent },
              exporting && styles.actionButtonDisabled,
            ]}
            onPress={() => {
              fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
              handleExportCSV();
            }}
            disabled={exporting}
            accessibilityRole="button"
            accessibilityLabel="Download collection overview as CSV"
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

          <AnimatedPressable
            style={[
              styles.actionButtonSecondary,
              { borderColor: colors.accent },
            ]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
              router.push('/build-paint-projects');
            }}
            accessibilityRole="button"
            accessibilityLabel="Open build and paint projects"
          >
            <Ionicons name="color-palette-outline" size={18} color={colors.accent} />
            <Text style={[styles.actionButtonSecondaryText, { color: colors.accent }]}>
              Projects
            </Text>
          </AnimatedPressable>
        </View>

        {exportStatus && (
          <View style={[styles.exportStatusBanner, { backgroundColor: colors.accent + '15' }]}>
            <Ionicons name="checkmark-circle" size={16} color={colors.accent} />
            <Text style={[styles.exportStatusText, { color: colors.accent }]}>
              {exportStatus}
            </Text>
          </View>
        )}
      </View>

      {/* Loading-more spinner at bottom of list */}
      {isLoadingMore && (
        <View style={styles.loadingMoreContainer}>
          <ActivityIndicator size="small" color={colors.accent} />
        </View>
      )}
    </>
  );

  const emptyElement = (
    <View style={styles.emptyContainer}>
      <Text style={[styles.emptyText, { color: colors.muted }]}>
        No items match your filters yet.
      </Text>
      <AnimatedPressable
        onPress={() => router.push('/quickscan')}
        style={[styles.emptyCtaBtn, { backgroundColor: colors.accent }]}
        accessibilityRole="button"
        accessibilityLabel="QuickScan AI"
      >
        <Ionicons name="camera-outline" size={18} color="#fff" />
        <Text style={styles.emptyCtaBtnText}>QuickScan AI</Text>
      </AnimatedPressable>
      <AnimatedPressable
        onPress={() => router.push('/add-manual')}
        style={[styles.emptyCtaBtn, { borderColor: colors.border, borderWidth: 1, backgroundColor: colors.card }]}
        accessibilityRole="button"
        accessibilityLabel="Add item manually"
      >
        <Ionicons name="add-circle-outline" size={18} color={colors.text} />
        <Text style={[styles.emptyCtaBtnTextSecondary, { color: colors.text }]}>Add Item Manually</Text>
      </AnimatedPressable>
      <AnimatedPressable
        onPress={() => router.push('/barcode-scan')}
        style={[styles.emptyCtaBtn, { borderColor: colors.border, borderWidth: 1, backgroundColor: colors.card }]}
        accessibilityRole="button"
        accessibilityLabel="Scan a barcode"
      >
        <Ionicons name="barcode-outline" size={18} color={colors.text} />
        <Text style={[styles.emptyCtaBtnTextSecondary, { color: colors.text }]}>Scan Barcode</Text>
      </AnimatedPressable>
    </View>
  );

  const refreshCtrl = (
    <RefreshControl
      refreshing={refreshing}
      onRefresh={handleRefresh}
      tintColor={colors.accent}
      colors={[colors.accent]}
    />
  );

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={{ flex: 1 }}
        keyboardVerticalOffset={Platform.OS === "ios" ? 50 : 0}
      >
      {viewMode === 'gallery' ? (
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={[styles.content, { backgroundColor: colors.background }]}
          keyboardShouldPersistTaps="handled"
          onScroll={handleScroll}
          scrollEventThrottle={400}
          refreshControl={refreshCtrl}
        >
          {headerElement}
          {filteredAndSortedByCategory.length === 0 ? (
            emptyElement
          ) : (
            <ItemGalleryGrid
              items={galleryItems}
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
          )}
          {footerElement}
        </ScrollView>
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(item) => item.id}
          renderSectionHeader={({ section }) => (
            <View style={[styles.categoryBlock, { borderTopColor: colors.border, backgroundColor: colors.background }]}>
              <View style={styles.categoryHeaderRow}>
                <Text style={[styles.categoryTitle, { color: colors.text }]}>
                  {section.title}
                </Text>
                <AnimatedPressable
                  style={[styles.categoryAddButton, { borderColor: colors.accent }]}
                  onPress={() => {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                    handleAddForCategory(section.title);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`Add item to ${section.title}`}
                >
                  <Ionicons name="add-outline" size={14} color={colors.accent} style={{ marginRight: 4 }} />
                  <Text style={[styles.categoryAddText, { color: colors.accent }]}>Add</Text>
                </AnimatedPressable>
              </View>
            </View>
          )}
          renderItem={({ item }) => (
            <Animated.View style={getStaggerStyle(staggerIndexMap.current.get(item.id) ?? 0)}>
              <AnimatedPressable
                style={[
                  styles.itemRow,
                  { borderColor: colors.border },
                  isMultiSelectMode && isSelected(item.id) && {
                    backgroundColor: colors.accent + '15',
                    borderColor: colors.accent,
                  },
                ]}
                onPress={() => {
                  fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                  handleItemPress(item);
                }}
                onLongPress={() => handleLongPress(item.id)}
                delayLongPress={400}
                accessibilityRole="button"
                accessibilityLabel={`${item.name}, ${formatPrice(item.value)}`}
                accessibilityHint={isMultiSelectMode ? "Tap to select or deselect" : "Long press to select multiple items"}
              >
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
                {item.imageUrl ? (
                  <Image source={{ uri: item.imageUrl }} style={styles.itemThumb} />
                ) : (
                  <View style={[styles.itemThumbPlaceholder, { backgroundColor: colors.accent + '10' }]}>
                    <Ionicons name="image-outline" size={18} color={colors.accent + '40'} />
                  </View>
                )}
                <View style={{ flex: 1 }}>
                  <Text style={[styles.itemName, { color: colors.text }]}>
                    {item.name}
                  </Text>
                  <Text style={[styles.itemMeta, { color: colors.muted }]}>
                    <CategoryPill id={item.category} label={item.category} /> – {item.collectionName}
                  </Text>
                  {item.condition ? (
                    <Text style={[styles.itemCondition, { color: colors.muted }]}>
                      {item.condition}
                    </Text>
                  ) : null}
                </View>
                <View style={styles.itemRight}>
                  <Text style={[styles.itemValue, { color: colors.text }]}>
                    {formatPrice(item.value)}
                  </Text>
                </View>
              </AnimatedPressable>
            </Animated.View>
          )}
          renderSectionFooter={({ section }) => (
            <View style={styles.categoryFooterRow}>
              <View style={{ flex: 1 }} />
              <View style={{ alignItems: "flex-end" }}>
                <Text style={[styles.categoryTotalLabel, { color: colors.muted }]}>
                  Collection total
                </Text>
                <Text style={[styles.categoryTotalValue, { color: colors.text }]}>
                  {formatPrice(section.total)}
                </Text>
              </View>
            </View>
          )}
          ListHeaderComponent={headerElement}
          ListFooterComponent={footerElement}
          ListEmptyComponent={emptyElement}
          style={styles.scroll}
          contentContainerStyle={[styles.content, { backgroundColor: colors.background }]}
          stickySectionHeadersEnabled={false}
          keyboardShouldPersistTaps="handled"
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          refreshControl={refreshCtrl}
        />
      )}
      </KeyboardAvoidingView>

      {/* Category Change Modal */}
      <Modal
        visible={categoryModalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setCategoryModalVisible(false)}
      >
        <AnimatedPressable
          style={styles.modalOverlay}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            setCategoryModalVisible(false);
          }}
        >
          <View style={[styles.modalContent, { backgroundColor: colors.card }]} accessibilityRole="menu">
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
                  onPress={() => {
                    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
                    handleBulkChangeCategory(cat);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`Move to ${cat}`}
                >
                  <CategoryPill id={cat} label={cat} />
                  <Ionicons name="chevron-forward" size={18} color={colors.muted} />
                </AnimatedPressable>
              ))}
            </ScrollView>

            <AnimatedPressable
              style={[styles.modalCancelBtn, { borderColor: colors.border }]}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                setCategoryModalVisible(false);
              }}
              accessibilityRole="button"
              accessibilityLabel="Cancel category change"
            >
              <Text style={[styles.modalCancelText, { color: colors.muted }]}>Cancel</Text>
            </AnimatedPressable>
          </View>
        </AnimatedPressable>
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
  // Loading more (infinite scroll)
  loadingMoreContainer: {
    paddingVertical: 16,
    alignItems: 'center',
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
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  emptyCtaBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 10,
    marginTop: 12,
  },
  emptyCtaBtnText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
  emptyCtaBtnTextSecondary: {
    fontSize: 14,
    fontWeight: '600',
  },
  itemCount: {
    fontSize: 13,
    fontWeight: '500',
    paddingHorizontal: 16,
    paddingVertical: 4,
  },
  categoryBlock: {
    marginTop: 10,
    paddingVertical: 8,
    paddingHorizontal: 4,
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
  itemThumb: {
    width: 40,
    height: 40,
    borderRadius: 8,
    marginRight: 10,
  },
  itemThumbPlaceholder: {
    width: 40,
    height: 40,
    borderRadius: 8,
    marginRight: 10,
    alignItems: 'center',
    justifyContent: 'center',
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

function ItemsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Items">
      <ItemsScreen />
    </ScreenErrorBoundary>
  );
}

export default ItemsScreenWithBoundary;
