import React, { useMemo, useState, useCallback, useRef, useEffect } from 'react';
import { useModal } from '@/hooks/useModal';
import { useHasEverHadItems } from '@/hooks/useHasEverHadItems';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { useAppTheme } from '@/hooks/useAppTheme';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  SectionList,
  ActivityIndicator,
  Alert,
  Animated,
  RefreshControl,
  KeyboardAvoidingView,
  Platform,
  type NativeSyntheticEvent,
  type NativeScrollEvent,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useLocalSearchParams, useFocusEffect } from "expo-router";
import { dataProvider, type Item as DataItem } from "@/data";
import { mapDataItemToScreenItem, type ScreenItem } from "@/data/screenItem";
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import { AnimatedPressable, useEnterReveal, useStaggerReveal } from "@/motion";
// Skeleton imports moved to ItemsLoadingState
import { ItemGalleryGrid } from "@/components/ItemGalleryGrid";
import { useMultiSelect } from "@/hooks/useMultiSelect";
import {
  useOptimisticArchive,
  useOptimisticDelete,
  useOptimisticBulkArchive,
  useOptimisticBulkDelete,
} from "@/hooks/useOptimisticItems";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
// formatPrice moved to ItemsSectionFooter
import { useToast } from "@/components/Toast";
import { FilterSheet, FilterConfig } from "@/components/FilterSheet";
import AsyncStorage from '@react-native-async-storage/async-storage';
import logger from "@/utils/logger";
import { BulkActionsToolbar } from '@/components/BulkActionsToolbar';
import { ItemsListHeader } from '@/components/ItemsListHeader';
import { AdBanner } from '@/components/ads/AdBanner';
import {
  CategoryBreakdownSection,
  type CategoryBreakdownItem,
} from '@/components/home/CategoryBreakdownSection';
import { collectorsApi } from '@/api/collectorsApi';
import { exportItemsOverview } from '@/api/miscApi';
import { formatPrice } from '@/lib/format';
import { getCategoryById, getCategoryByName } from '@/data/categories';
import { radius, text, fontWeight } from '@/theme/tokens';
import {
  ItemsGridHeader,
  ItemsFilterSummary,
  ItemsBottomActionBar,
  ItemsListItem,
  ItemsCategoryModal,
  ItemsEmptyState,
  ItemsLoadingState,
  ItemsErrorState,
  ItemsSectionFooter,
  ItemsFloatingAddButton,
} from '@/components/items';

// Screen row shape + the provider→screen mapper live in @/data/screenItem so
// the mapping is unit-testable (see screenItem.test.ts). Aliased to `Item`
// here to keep the rest of this file unchanged.
type Item = ScreenItem;

const VIEW_MODE_KEY = '@sparrowcollect/items_view_mode';

const ITEMS_PAGE_SIZE = 20;
const STAGGER_MS = 40;
const STATUS_CLEAR_DELAY_MS = 3000;
const SCROLL_LOAD_THRESHOLD = 0.5;
const FLOATING_BUTTON_SCROLL_PX = 100;

const ItemsScreen: React.FC = () => {
  const router = useRouter();
  const params = useLocalSearchParams<{ category?: string; collectionName?: string }>();
  const { colors } = useAppTheme();
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { showToast } = useToast();

  const [query, setQuery] = useState("");
  const [filterCategory, setFilterCategory] = useState<string | null>(null);
  // Paginated data fetching
  const itemFetcher = useCallback(
    async (limit: number, offset: number): Promise<Item[]> => {
      const items = await dataProvider.listItems({ limit, offset });
      return items.map(mapDataItemToScreenItem);
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
  } = usePaginatedList<Item>(itemFetcher, { pageSize: ITEMS_PAGE_SIZE });

  // Stagger animation for list items — compute flat index map
  const { getItemStyle: getStaggerStyle } = useStaggerReveal({
    count: (providerItems ?? []).length,
    enabled: settings.animationsEnabled && !loading,
    staggerMs: STAGGER_MS,
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
  const [showFloatingAdd, setShowFloatingAdd] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'gallery'>('list');
  const { hasEverHadItems, markHasItems } = useHasEverHadItems();
  useEffect(() => {
    if (providerItems.length > 0) markHasItems();
  }, [providerItems.length, markHasItems]);

  // Category breakdown (moved from home tab 2026-04-18)
  const [categoryBreakdown, setCategoryBreakdown] = useState<CategoryBreakdownItem[]>([]);
  const [breakdownLoading, setBreakdownLoading] = useState(false);
  useEffect(() => {
    let cancelled = false;
    setBreakdownLoading(true);
    collectorsApi.getPortfolioCategoryBreakdown()
      .then((data) => {
        if (cancelled) return;
        const cats = Array.isArray((data as { categories?: unknown })?.categories)
          ? (data as { categories: CategoryBreakdownItem[] }).categories
          : [];
        setCategoryBreakdown(cats);
      })
      .catch((err) => {
        logger.warn('[Items] category breakdown fetch failed:', err);
        if (!cancelled) setCategoryBreakdown([]);
      })
      .finally(() => {
        if (!cancelled) setBreakdownLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  // Restore persisted view mode on mount
  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(VIEW_MODE_KEY).then((stored) => {
      if (!cancelled && (stored === 'list' || stored === 'gallery')) setViewMode(stored);
    }).catch((err) => logger.warn('[Items] view mode restore failed:', err));
    return () => { cancelled = true; };
  }, []);

  // Toggle handler that persists the preference
  const toggleViewMode = useCallback(() => {
    const next = viewMode === 'list' ? 'gallery' : 'list';
    setViewMode(next);
    AsyncStorage.setItem(VIEW_MODE_KEY, next).catch((err) => logger.warn('[Items] view mode persist failed:', err));
  }, [viewMode]);

  const [categoryModalVisible, openCategoryModal, closeCategoryModal] = useModal();
  const [bulkActionLoading, setBulkActionLoading] = useState(false);
  const [filterSheetVisible, openFilterSheet, closeFilterSheet] = useModal();
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
  const exportTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refreshRef = useRef(paginatedRefresh);
  refreshRef.current = paginatedRefresh;
  const stableReload = useCallback(() => { refreshRef.current(); }, []);

  // Auto-refresh on tab focus so items saved from QuickScan / Add appear immediately
  // without the user having to pull-to-refresh.
  useFocusEffect(
    useCallback(() => {
      refreshRef.current();
    }, []),
  );

  // Optimistic mutation hooks for bulk operations (generic over item shape)
  const optimisticBulkArchive = useOptimisticBulkArchive(setProviderItems, stableReload);
  const optimisticBulkDelete = useOptimisticBulkDelete(setProviderItems, stableReload);

  // Single-item versions used by swipe-to-archive / swipe-to-delete in the row
  const optimisticArchive = useOptimisticArchive(setProviderItems, stableReload);
  const optimisticDelete = useOptimisticDelete(setProviderItems, stableReload);

  const handleSwipeArchive = useCallback(async (id: string) => {
    try {
      await optimisticArchive.mutate(id);
      showToast({ message: 'Archived', type: 'success', duration: 2000 });
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    } catch (err: unknown) {
      showToast({ message: (err as Error)?.message || 'Failed to archive', type: 'error' });
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
    }
  }, [optimisticArchive, showToast, settings.hapticsEnabled]);

  const handleSwipeDelete = useCallback((id: string) => {
    Alert.alert(
      'Delete Item',
      'Permanently delete this item? This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await optimisticDelete.mutate(id);
              fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
            } catch (err: unknown) {
              showToast({ message: (err as Error)?.message || 'Failed to delete', type: 'error' });
              fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
            }
          },
        },
      ]
    );
  }, [optimisticDelete, showToast, settings.hapticsEnabled]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await paginatedRefresh();
    fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
    setRefreshing(false);
  }, [paginatedRefresh, settings.hapticsEnabled]);

  // Export all items to CSV via the backend's canonical 12-col overview
  // (same column set as the import template, so round-trips work).
  const handleExportCSV = useCallback(async () => {
    setExporting(true);
    setExportStatus(null);

    try {
      const { csv_inline } = await exportItemsOverview();
      // Backend returns header-only CSV when there are no items.
      const lineCount = csv_inline.trim().split('\n').length;
      const itemCount = Math.max(0, lineCount - 1);

      if (itemCount === 0) {
        setExportStatus('No items to export');
        setExporting(false);
        return;
      }

      const dateStr = new Date().toISOString().split('T')[0];
      const filename = `Sparrow Collect_Collection_${dateStr}_${itemCount}items.csv`;

      if (!FileSystem.documentDirectory) {
        showToast({ message: 'File storage not available on this platform', type: 'error' });
        setExporting(false);
        return;
      }

      const filePath = `${FileSystem.documentDirectory}${filename}`;
      await FileSystem.writeAsStringAsync(filePath, csv_inline);

      const itemsLabel = itemCount === 1 ? '1 item' : `${itemCount} items`;
      const sharingAvailable = await Sharing.isAvailableAsync();
      if (sharingAvailable) {
        await Sharing.shareAsync(filePath, {
          mimeType: 'text/csv',
          dialogTitle: 'Export Collection',
          UTI: 'public.comma-separated-values-text',
        });
        showToast({ message: `Exported ${itemsLabel}`, type: 'success', duration: 3000 });
        setExportStatus(`Exported ${itemsLabel}`);
      } else {
        showToast({ message: `Saved ${itemsLabel} to ${filename}`, type: 'info', duration: 4000 });
        setExportStatus('Saved (sharing unavailable)');
      }
    } catch (err: unknown) {
      logger.warn('[Items] export error:', err);
      setExportStatus('Export failed');
      showToast({ message: 'Failed to export items', type: 'error' });
    } finally {
      setExporting(false);
      // Clear status after 3 seconds
      if (exportTimerRef.current) clearTimeout(exportTimerRef.current);
      exportTimerRef.current = setTimeout(() => setExportStatus(null), STATUS_CLEAR_DELAY_MS);
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
      const filename = `Sparrow Collect_Selected_${selectedCount}_${dateStr}.csv`;
      const filePath = `${FileSystem.documentDirectory}${filename}`;

      await FileSystem.writeAsStringAsync(filePath, csvContent);

      const sharingAvailable = await Sharing.isAvailableAsync();
      if (sharingAvailable) {
        await Sharing.shareAsync(filePath, {
          mimeType: 'text/csv',
          dialogTitle: 'Export Selected Items',
          UTI: 'public.comma-separated-values-text',
        });
        fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      }
      exitMultiSelectMode();
    } catch (err: unknown) {
      logger.warn('[Items] bulk export error:', err);
      showToast({ message: (err as Error)?.message || 'Failed to export selected items', type: 'error' });
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
    } finally {
      setBulkActionLoading(false);
    }
  }, [selectedCount, selectedItems, exitMultiSelectMode, settings.hapticsEnabled, showToast]);

  // Bulk archive (mark as archived/sold) — with optimistic update
  const handleBulkArchive = useCallback(async () => {
    if (selectedCount === 0) return;
    if (bulkActionLoading || optimisticBulkArchive.isLoading) return;

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
            try {
              await optimisticBulkArchive.mutate(ids);
              fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
            } catch (err: unknown) {
              showToast({ message: (err as Error)?.message || 'Failed to archive items', type: 'error' });
              fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
            }
          },
        },
      ]
    );
  }, [selectedCount, selectedIds, exitMultiSelectMode, optimisticBulkArchive]);

  // Bulk delete — with optimistic update
  const handleBulkDelete = useCallback(async () => {
    if (selectedCount === 0) return;
    if (bulkActionLoading || optimisticBulkDelete.isLoading) return;

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
            try {
              await optimisticBulkDelete.mutate(ids);
              fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
            } catch (err: unknown) {
              showToast({ message: (err as Error)?.message || 'Failed to delete items', type: 'error' });
              fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
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
    closeCategoryModal();
    try {
      for (const id of ids) {
        await dataProvider.updateItem(id, { category: newCategory });
      }
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      exitMultiSelectMode();
      showToast({ message: `${count} item${count > 1 ? 's' : ''} moved to ${newCategory}`, type: 'success' });
      await paginatedRefresh();
    } catch (err: unknown) {
      logger.warn('[Items] bulk category change error:', err);
      showToast({ message: 'Could not update items', type: 'error' });
      fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
    } finally {
      setBulkActionLoading(false);
    }
  }, [selectedCount, selectedIds, exitMultiSelectMode, paginatedRefresh, settings.hapticsEnabled, showToast]);

  // Open item detail
  const handleOpenItem = useCallback((item: Item) => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
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
  }, [router, settings.hapticsEnabled]);

  // Handle long press to enter multi-select
  const handleLongPress = useCallback((itemId: string) => {
    if (!isMultiSelectMode) {
      fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
      enterMultiSelectMode();
      toggleItem(itemId);
    }
  }, [isMultiSelectMode, enterMultiSelectMode, toggleItem, settings.hapticsEnabled]);

  // Handle item press in multi-select mode
  const handleItemPress = useCallback((item: Item) => {
    if (isMultiSelectMode) {
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      toggleItem(item.id);
    } else {
      handleOpenItem(item);
    }
  }, [isMultiSelectMode, toggleItem, handleOpenItem, settings.hapticsEnabled]);

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
          condition: item.condition,
        }))
      ),
    [filteredAndSortedByCategory]
  );

  const portfolioTotal = useMemo(
    () => dataSource.reduce((sum, item) => sum + item.value, 0),
    [dataSource]
  );

  // SectionList sections derived from grouped data
  const sections = useMemo(() =>
    filteredAndSortedByCategory.map(group => ({
      title: group.category,
      data: group.items,
      total: group.total,
    })),
    [filteredAndSortedByCategory]
  );

  // Detect when ScrollView is near the bottom to trigger loadMore + show floating add
  const handleScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const { contentOffset, layoutMeasurement, contentSize } = event.nativeEvent;
      const distanceFromBottom = contentSize.height - layoutMeasurement.height - contentOffset.y;
      if (distanceFromBottom < layoutMeasurement.height * SCROLL_LOAD_THRESHOLD) {
        loadMore();
      }
      // Show floating add button when user scrolls down past 100px
      setShowFloatingAdd(contentOffset.y > FLOATING_BUTTON_SCROLL_PX);
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
    } catch (err) {
      logger.warn('[Items] setParams failed:', err);
    }
  };

  // Loading state. For users who have never had items, skip the grey
  // skeleton entirely and render the hero CTA so they see "Add Your First
  // Item" from frame 1 instead of silhouettes. While the AsyncStorage flag
  // is still being read (null), also show the hero — better than a flash
  // of skeleton for new users.
  if (loading) {
    if (hasEverHadItems !== true) {
      return (
        <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
          <View style={{ flex: 1, justifyContent: 'center' }}>
            <ItemsEmptyState />
          </View>
        </SafeAreaView>
      );
    }
    return <ItemsLoadingState viewMode={viewMode} />;
  }

  // Error state
  if (error) {
    return (
      <ItemsErrorState
        error={error}
        onRetry={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          paginatedRefresh();
        }}
      />
    );
  }

  // First-run / zero-items state: show only the hero CTA, no skeletons,
  // no breakdown preview, no search bar. Triggers when the user has nothing
  // saved AND isn't actively searching/filtering.
  const hasActiveAdvancedFilter =
    advancedFilter.categories.length > 0 ||
    advancedFilter.conditions.length > 0 ||
    advancedFilter.priceMin !== null ||
    advancedFilter.priceMax !== null;
  const isFirstRun =
    providerItems.length === 0 &&
    !query.trim() &&
    !filterCategory &&
    !categoryParam &&
    !collectionParam &&
    !hasActiveAdvancedFilter;

  if (isFirstRun) {
    return (
      <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
        <ScrollView
          contentContainerStyle={{ flexGrow: 1, justifyContent: 'center' }}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor={colors.accent}
              colors={[colors.accent]}
            />
          }
        >
          <ItemsEmptyState />
        </ScrollView>
      </SafeAreaView>
    );
  }

  // Shared header element for both gallery ScrollView and list SectionList
  const headerElement = (
    <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
      {/* Header row - switches between normal and multi-select mode */}
      {isMultiSelectMode ? (
        <BulkActionsToolbar
          theme={{ text: colors.text, muted: colors.muted, accent: colors.accent, border: colors.border, card: colors.card }}
          selectedCount={selectedCount}
          totalCount={providerItems.length}
          isAllSelected={selectedCount === providerItems.length}
          loading={bulkActionLoading || optimisticBulkArchive.isLoading || optimisticBulkDelete.isLoading}
          disabled={bulkActionLoading || optimisticBulkArchive.isLoading || optimisticBulkDelete.isLoading}
          onExit={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            exitMultiSelectMode();
          }}
          onSelectAll={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            selectAll();
          }}
          onDeselectAll={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            deselectAll();
          }}
          onChangeCategory={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            openCategoryModal();
          }}
          onExport={() => {
            fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
            handleBulkExport();
          }}
          onArchive={() => {
            fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
            handleBulkArchive();
          }}
          onDelete={() => {
            fireHaptic(HapticIntent.ALERT_TRIGGERED, { enabled: settings.hapticsEnabled });
            handleBulkDelete();
          }}
        />
      ) : (
        <ItemsGridHeader portfolioTotal={portfolioTotal} />
      )}

      <ItemsListHeader
        theme={{ text: colors.text, muted: colors.muted, accent: colors.accent, border: colors.border, card: colors.card }}
        query={query}
        onQueryChange={setQuery}
        viewMode={viewMode}
        onToggleViewList={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          if (viewMode !== 'list') toggleViewMode();
        }}
        onToggleViewGallery={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          if (viewMode !== 'gallery') toggleViewMode();
        }}
        hasActiveFilter={
          advancedFilter.categories.length > 0 ||
          advancedFilter.conditions.length > 0 ||
          advancedFilter.priceMin !== null ||
          advancedFilter.priceMax !== null
        }
        onOpenFilter={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          openFilterSheet();
        }}
        onEnterMultiSelect={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          enterMultiSelectMode();
        }}
        isMultiSelectMode={isMultiSelectMode}
      />

      <ItemsFilterSummary
        categoryParam={categoryParam}
        collectionParam={collectionParam}
        filterCategory={filterCategory}
        query={query}
        filteredItemCount={filteredItemCount}
        onClearFilters={() => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          clearFilters();
        }}
      />

      {/* Category Breakdown (moved from home tab 2026-04-18) */}
      <CategoryBreakdownSection
        theme={colors}
        breakdown={categoryBreakdown}
        loading={breakdownLoading}
        formatPrice={(v) => formatPrice(v)}
        resolveCategoryName={(raw) => {
          const cat = getCategoryById(raw) ?? getCategoryByName(raw);
          return cat?.name ?? raw;
        }}
        onCategoryPress={(catRaw) => {
          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
          setFilterCategory(catRaw);
        }}
      />

      {/* Ad slot — invisible until FEATURE_ADS is enabled */}
      <AdBanner placement="items_banner" />
    </Animated.View>
  );

  // Shared footer element
  const footerElement = (
    <ItemsBottomActionBar
      exporting={exporting}
      exportStatus={exportStatus}
      isLoadingMore={isLoadingMore}
      onExportCSV={() => {
        fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: settings.hapticsEnabled });
        handleExportCSV();
      }}
      onOpenProjects={() => {
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
        router.push('/build-paint-projects');
      }}
    />
  );

  const emptyElement = query.trim() ? (
    <View style={{ alignItems: 'center', paddingVertical: 32 }}>
      <Ionicons name="search-outline" size={40} color={colors.muted} />
      <Text style={{ color: colors.muted, fontSize: text.lg, marginTop: 12 }}>
        No items match your search
      </Text>
      <Text style={{ color: colors.muted, fontSize: text.md, marginTop: 4 }}>
        Try a different keyword or clear filters
      </Text>
    </View>
  ) : <ItemsEmptyState />;

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
                accentText: colors.accentText,
                brand: colors.brand,
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
              <Text style={[styles.categoryTitle, { color: colors.text }]}>
                {section.title}
              </Text>
            </View>
          )}
          renderItem={({ item }) => (
            <ItemsListItem
              item={item}
              isMultiSelectMode={isMultiSelectMode}
              isSelected={isSelected(item.id)}
              staggerStyle={getStaggerStyle(staggerIndexMap.current.get(item.id) ?? 0)}
              onPress={handleItemPress}
              onLongPress={handleLongPress}
              onArchive={handleSwipeArchive}
              onDelete={handleSwipeDelete}
            />
          )}
          renderSectionFooter={({ section }) => (
            <ItemsSectionFooter total={section.total} />
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
          initialNumToRender={15}
          maxToRenderPerBatch={10}
          windowSize={5}
          removeClippedSubviews={true}
          onScroll={handleScroll}
          scrollEventThrottle={400}
        />
      )}

      {/* Floating Add Item button — appears when scrolling */}
      {showFloatingAdd && !isMultiSelectMode && (
        <ItemsFloatingAddButton
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
            router.push('/(tabs)/add');
          }}
        />
      )}
      </KeyboardAvoidingView>

      {/* Category Change Modal */}
      <ItemsCategoryModal
        visible={categoryModalVisible}
        selectedCount={selectedCount}
        allCategories={allCategories}
        onChangeCategory={handleBulkChangeCategory}
        onClose={() => closeCategoryModal()}
      />

      {/* Advanced Filter Sheet */}
      <FilterSheet
        visible={filterSheetVisible}
        onClose={() => closeFilterSheet()}
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
    paddingBottom: 80,
  },
  // Loading/Error/Skeleton styles moved to ItemsLoadingState + ItemsErrorState
  // (viewToggleRow, viewToggleBtn, controlsRowNew, selectAllTextBtn, selectAllText moved to ItemsListHeader)
  // (headerRow, headerLeft, title, subtitle, headerIcons moved to ItemsGridHeader)
  // (searchRow, searchInputWrapper, searchIcon, searchInput, searchRowButton, filterDot moved to ItemsListHeader)
  // (filterSummaryRow, filterSummaryText, filterChipsRow, filterChip, filterChipText, filterClearButton, filterClearText, itemCount moved to ItemsFilterSummary)
  // emptyText, emptyContainer, emptyCtaBtn styles moved to ItemsEmptyState
  categoryBlock: {
    marginTop: 10,
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "transparent",
  },
  categoryTitle: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
  },
  // itemRow, itemThumb, itemName, itemMeta, itemCondition, gradeBadge, itemRight, itemValue moved to ItemsListItem
  // categoryFooterRow, categoryTotalLabel, categoryTotalValue moved to ItemsSectionFooter
  // (bottomActionBar, bottomActionTitle, bottomActionButtons, actionButtonPrimary, actionButtonPrimaryText, actionButtonSecondary, actionButtonSecondaryText, actionButtonDisabled, exportStatusBanner, exportStatusText moved to ItemsBottomActionBar)
  // (multiSelectHeader, multiSelectCloseBtn, multiSelectTitle, multiSelectActions, multiSelectActionBtn, multiSelectActionText moved to BulkActionsToolbar)
  // checkboxContainer, checkbox moved to ItemsListItem
  // (topBulkActionsBar, topBulkActionsRow, topBulkActionBtn, topBulkActionText, bulkActionsBar, bulkActionsRow, bulkActionBtn, bulkActionText moved to BulkActionsToolbar)
  // Modal styles moved to ItemsCategoryModal
  // floatingAddBtn, floatingAddText moved to ItemsFloatingAddButton
});

function ItemsScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Items">
      <ItemsScreen />
    </ScreenErrorBoundary>
  );
}

export default ItemsScreenWithBoundary;
