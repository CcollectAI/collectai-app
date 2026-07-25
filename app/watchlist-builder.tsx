/**
 * Watchlist Builder — Track items you want with price alerts
 *
 * Features:
 * - Clean, focused UI for adding watchlist items
 * - Priority badges (High/Medium/Low)
 * - Price targets with alert settings
 * - Quick add flow
 * - SafeAreaView for notch support
 * - SwipeableRow for quick delete
 * - Category filter chips
 * - Sort menu (Priority / Newest / Price / Custom)
 * - B3.2: Bulk Actions (multi-select, bulk delete, CSV export)
 * - B3.3: Optimistic Updates (immediate UI feedback with rollback)
 * - B2.2: Drag-to-Reorder with Haptics (long-press move up/down)
 * - B3.4/B3.5: Watchlist Sharing (text share via native sheet, CSV export)
 */

import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { SkeletonList } from '@/components/Skeleton';
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TextInput,
  Alert,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Animated,
  RefreshControl,
  Share,
} from "react-native";
import { useToast } from "@/components/Toast";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useAppTheme } from "@/hooks/useAppTheme";
import logger from "@/utils/logger";
import { QuickNavBar } from "@/components/QuickNavBar";
import { CATEGORY_SLUG_TO_NAME } from "@/constants/categories";
import { useMultiSelect } from "@/hooks/useMultiSelect";
import { saveCSVAndShare } from "@/export/csv";
import { track } from "@/analytics/track";

import { useAuthContext } from "@/providers/useAuthContext";
import { dataProvider } from "@/data";
import type { WatchlistItem } from "@/data/types";
import { useWatchlistRealtime } from "@/hooks/useWatchlistRealtime";

// Extracted components
import { WatchlistStatsBanner } from "@/components/watchlist/WatchlistStatsBanner";
import { WatchlistFilterSort, type SortKey } from "@/components/watchlist/WatchlistFilterSort";
import { WatchlistAddForm } from "@/components/watchlist/WatchlistAddForm";
import { WatchlistEmptyState } from "@/components/watchlist/WatchlistEmptyState";
import { WatchlistItemCard } from "@/components/watchlist/WatchlistItemCard";
import { WatchlistBulkBar } from "@/components/watchlist/WatchlistBulkBar";

type WatchlistPriority = 'high' | 'medium' | 'low';

// ─────────────────────────────────────────────────────────────────────────────
// CSV generation for watchlist items
// ─────────────────────────────────────────────────────────────────────────────

function watchlistToCSV(items: WatchlistItem[], currency: string): string {
  const escape = (v: unknown) => {
    if (v == null) return '';
    const s = String(v);
    return /[,"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const head = ['Title', 'Priority', 'Target Price', 'Market Price', 'Currency', 'Category', 'Notes', 'Created'];
  const lines = [head.join(',')];
  for (const item of items) {
    lines.push([
      escape(item.title),
      escape(item.priority),
      escape(item.targetPrice != null ? item.targetPrice.toFixed(2) : ''),
      escape(item.lastMarketPrice != null ? item.lastMarketPrice.toFixed(2) : ''),
      escape(currency),
      escape(item.category ?? ''),
      escape(item.notes ?? ''),
      escape(item.createdAt ?? ''),
    ].join(','));
  }
  return lines.join('\n');
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

function WatchlistBuilderScreen() {
  const { user } = useAuthContext();
  const userId = user?.id ?? "";
  const { animatedStyle } = useEnterReveal({ delay: 50 });
  const { settings } = useSettings();
  const { showToast } = useToast();
  const { colors } = useAppTheme();

  // Input refs for keyboard chaining
  const targetPriceRef = useRef<TextInput>(null);
  const notesRef = useRef<TextInput>(null);

  // State
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Filter & sort state
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('priority');
  const [showSortMenu, setShowSortMenu] = useState(false);

  // Add form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newTargetPrice, setNewTargetPrice] = useState("");
  const [newPriority, setNewPriority] = useState<WatchlistPriority>("high");
  const [newNotes, setNewNotes] = useState("");

  // B2.2: Reorder state — which item has the reorder controls visible
  const [reorderItemId, setReorderItemId] = useState<string | null>(null);

  // B3.2: Multi-select via existing hook
  const {
    isMultiSelectMode,
    selectedCount,
    enterMultiSelectMode,
    exitMultiSelectMode,
    toggleItem,
    isSelected,
    getSelectedItems,
  } = useMultiSelect({
    items,
    keyExtractor: (item: WatchlistItem) => item.id,
  });

  // Realtime updates for market price changes
  useWatchlistRealtime(userId, useCallback((id: string, patch: Partial<WatchlistItem>) => {
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    );
  }, []));

  // Load watchlist
  const loadWatchlist = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await dataProvider.listWatchlist(userId);
      setItems(data);
    } catch (err: unknown) {
      logger.error("[watchlist-builder] load error", err);
      setError(err instanceof Error ? err.message : "Unable to load your watchlist.");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadWatchlist();
  }, [loadWatchlist]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    try {
      await loadWatchlist();
    } finally {
      setRefreshing(false);
    }
  }, [loadWatchlist]);

  // Unique categories from current watchlist items (for filter chips)
  const uniqueCategories = useMemo(() => {
    const cats = new Set<string>();
    for (const item of items) {
      if (item.category) cats.add(item.category);
    }
    return Array.from(cats).sort();
  }, [items]);

  // Category-filtered items
  const filteredItems = useMemo(() => {
    if (!activeCategory) return items;
    return items.filter((i) => i.category === activeCategory);
  }, [items, activeCategory]);

  // Sort items based on selected sort key
  const priorityOrder: Record<WatchlistPriority, number> = useMemo(() => ({ high: 0, medium: 1, low: 2 }), []);
  const sortedItems = useMemo(() => {
    return [...filteredItems].sort((a, b) => {
      switch (sortKey) {
        case 'priority': {
          const pa = priorityOrder[a.priority] ?? 1;
          const pb = priorityOrder[b.priority] ?? 1;
          if (pa !== pb) return pa - pb;
          return new Date(b.createdAt ?? '').getTime() - new Date(a.createdAt ?? '').getTime();
        }
        case 'newest':
          return new Date(b.createdAt ?? '').getTime() - new Date(a.createdAt ?? '').getTime();
        case 'price_asc':
          return (a.targetPrice ?? Infinity) - (b.targetPrice ?? Infinity);
        case 'price_desc':
          return (b.targetPrice ?? -Infinity) - (a.targetPrice ?? -Infinity);
        case 'custom':
          return (a.sortOrder ?? 0) - (b.sortOrder ?? 0);
        default:
          return 0;
      }
    });
  }, [filteredItems, sortKey, priorityOrder]);

  // Stats
  const stats = useMemo(() => {
    const high = items.filter((i) => i.priority === "high").length;
    const withTarget = items.filter((i) => i.targetPrice != null).length;
    return { total: items.length, high, withTarget };
  }, [items]);

  // Reset form
  const resetForm = () => {
    setNewTitle("");
    setNewTargetPrice("");
    setNewPriority("high");
    setNewNotes("");
    setShowAddForm(false);
  };

  // ─────────────────────────────────────────────────────────────────────────
  // B3.3: Optimistic add — Save new item
  // ─────────────────────────────────────────────────────────────────────────
  const handleSave = useCallback(async () => {
    if (!userId) {
      showToast({ message: "Please sign in to save watchlist items.", type: "warning" });
      return;
    }

    const title = newTitle.trim();
    if (!title) {
      showToast({ message: "Please enter a name for this item.", type: "warning" });
      return;
    }

    let targetPrice: number | null = null;
    if (newTargetPrice.trim()) {
      const parsed = parseFloat(newTargetPrice.replace(/[^\d.]/g, "").trim());
      if (Number.isFinite(parsed) && parsed > 0) {
        targetPrice = parsed;
      }
    }

    // Optimistic: create a temporary item and show it immediately
    const optimisticId = `optimistic-${Date.now()}`;
    const optimisticItem: WatchlistItem = {
      id: optimisticId,
      title,
      priority: newPriority,
      owned: false,
      targetPrice,
      currency: (settings.currency as WatchlistItem['currency']) || 'EUR',
      category: undefined,
      notes: newNotes.trim() || undefined,
      createdAt: new Date().toISOString(),
      sortOrder: items.length,
    };

    // Save previous state for rollback
    const previousItems = [...items];

    // Apply optimistic update immediately
    setItems((prev) => [...prev, optimisticItem]);
    resetForm();
    setSaving(true);

    try {
      const savedItem = await dataProvider.addWatchlistItem({
        title,
        category: '',
        targetPrice,
        priority: newPriority,
        notes: newNotes.trim() || undefined,
      });

      // Replace optimistic item with real item from server
      setItems((prev) =>
        prev.map((item) => (item.id === optimisticId ? savedItem : item)),
      );
    } catch (err: unknown) {
      logger.error("[watchlist-builder] save error", err);
      // Rollback: restore previous state
      setItems(previousItems);
      showToast({ message: err instanceof Error ? err.message : "Unable to save this item.", type: "error" });
    } finally {
      setSaving(false);
    }
  }, [userId, newTitle, newTargetPrice, newPriority, newNotes, items, settings.currency, showToast]);

  // ─────────────────────────────────────────────────────────────────────────
  // B3.3: Optimistic delete — single item
  // ─────────────────────────────────────────────────────────────────────────
  const handleDelete = useCallback(
    async (item: WatchlistItem) => {
      Alert.alert(
        "Remove from watchlist?",
        `"${item.title}" will be removed from your watchlist.`,
        [
          { text: "Cancel", style: "cancel" },
          {
            text: "Remove",
            style: "destructive",
            onPress: async () => {
              // Save previous state for rollback
              const previousItems = [...items];

              // Optimistic removal
              setItems((prev) => prev.filter((i) => i.id !== item.id));

              try {
                await dataProvider.removeWatchlistItem(item.id);
              } catch {
                // Rollback on failure
                setItems(previousItems);
                showToast({ message: "Could not remove this item.", type: "error" });
              }
            },
          },
        ]
      );
    },
    [items, showToast]
  );

  // ─────────────────────────────────────────────────────────────────────────
  // B3.2: Bulk delete with optimistic update
  // ─────────────────────────────────────────────────────────────────────────
  const handleBulkDelete = useCallback(() => {
    const selected = getSelectedItems();
    if (selected.length === 0) return;

    Alert.alert(
      `Remove ${selected.length} item${selected.length === 1 ? '' : 's'}?`,
      "Selected items will be permanently removed from your watchlist.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Remove All",
          style: "destructive",
          onPress: async () => {
            const idsToRemove = new Set(selected.map((i) => i.id));
            const previousItems = [...items];

            // Optimistic removal
            setItems((prev) => prev.filter((i) => !idsToRemove.has(i.id)));
            exitMultiSelectMode();

            try {
              await dataProvider.removeWatchlistItems(Array.from(idsToRemove));
              showToast({ message: `Removed ${selected.length} item${selected.length === 1 ? '' : 's'}.`, type: "success" });
            } catch {
              // Rollback on failure
              setItems(previousItems);
              showToast({ message: "Could not remove some items. Please try again.", type: "error" });
            }
          },
        },
      ]
    );
  }, [getSelectedItems, items, exitMultiSelectMode, showToast]);

  // ─────────────────────────────────────────────────────────────────────────
  // B3.2: Export CSV
  // ─────────────────────────────────────────────────────────────────────────
  const handleExportCSV = useCallback(async () => {
    const selected = getSelectedItems();
    const itemsToExport = selected.length > 0 ? selected : items;
    if (itemsToExport.length === 0) {
      showToast({ message: "No items to export.", type: "warning" });
      return;
    }

    fireHaptic(HapticIntent.JUDGMENT_LOCKED);
    const csv = watchlistToCSV(itemsToExport, settings.currency);
    const filename = `watchlist_${new Date().toISOString().slice(0, 10)}.csv`;
    await saveCSVAndShare(filename, csv);
    exitMultiSelectMode();
  }, [getSelectedItems, items, settings.currency, exitMultiSelectMode, showToast]);

  // ─────────────────────────────────────────────────────────────────────────
  // Resolve category slug to human-readable name (moved above share handlers)
  const categoryDisplayName = useCallback((slug: string): string =>
    CATEGORY_SLUG_TO_NAME[slug] || slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()), []);

  // B3.4/B3.5: Sharing — text list or CSV file
  // ─────────────────────────────────────────────────────────────────────────
  const handleShareText = useCallback(async () => {
    if (items.length === 0) {
      showToast({ message: "No items to share.", type: "warning" });
      return;
    }
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);

    const lines = items.map((item) => {
      const parts: string[] = [item.title];
      if (item.category) parts.push(`[${categoryDisplayName(item.category)}]`);
      if (item.targetPrice != null) parts.push(`Target: ${item.targetPrice.toFixed(2)} ${settings.currency}`);
      return parts.join(' — ');
    });
    const message = `My Watchlist (${items.length} items)\n\n${lines.join('\n')}`;

    try {
      await Share.share({ message });
      track({ name: 'watchlist_shared', properties: { method: 'text', itemCount: items.length } });
    } catch (e) {
      logger.error('[silent-catch] watchlist-builder.tsx:419:', e);
      // user cancelled or share failed — no action needed
    }
  }, [items, settings.currency, categoryDisplayName, showToast]);

  const handleShareCSV = useCallback(async () => {
    if (items.length === 0) {
      showToast({ message: "No items to export.", type: "warning" });
      return;
    }
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);

    const csv = watchlistToCSV(items, settings.currency);
    const filename = `watchlist_${new Date().toISOString().slice(0, 10)}.csv`;
    await saveCSVAndShare(filename, csv);
    track({ name: 'watchlist_shared', properties: { method: 'csv', itemCount: items.length } });
  }, [items, settings.currency, showToast]);

  // ─────────────────────────────────────────────────────────────────────────
  // B2.2: Reorder handlers with haptic feedback
  // ─────────────────────────────────────────────────────────────────────────
  const handleLongPress = useCallback((itemId: string) => {
    if (isMultiSelectMode) return;
    fireHaptic(HapticIntent.JUDGMENT_LOCKED);
    setReorderItemId((prev) => (prev === itemId ? null : itemId));
  }, [isMultiSelectMode]);

  const handleMoveUp = useCallback(async (itemId: string) => {
    const idx = items.findIndex((i) => i.id === itemId);
    if (idx <= 0) return;

    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);

    const newItems = [...items];
    const temp = newItems[idx];
    newItems[idx] = newItems[idx - 1];
    newItems[idx - 1] = temp;

    const updatedItems = newItems.map((item, i) => ({ ...item, sortOrder: i }));
    const previousItems = [...items];
    setItems(updatedItems);
    setSortKey('custom');

    try {
      await Promise.all([
        dataProvider.updateWatchlistItem(updatedItems[idx].id, { sortOrder: idx }),
        dataProvider.updateWatchlistItem(updatedItems[idx - 1].id, { sortOrder: idx - 1 }),
      ]);
    } catch {
      setItems(previousItems);
      showToast({ message: "Could not reorder. Please try again.", type: "error" });
    }
  }, [items, showToast]);

  const handleMoveDown = useCallback(async (itemId: string) => {
    const idx = items.findIndex((i) => i.id === itemId);
    if (idx < 0 || idx >= items.length - 1) return;

    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);

    const newItems = [...items];
    const temp = newItems[idx];
    newItems[idx] = newItems[idx + 1];
    newItems[idx + 1] = temp;

    const updatedItems = newItems.map((item, i) => ({ ...item, sortOrder: i }));
    const previousItems = [...items];
    setItems(updatedItems);
    setSortKey('custom');

    try {
      await Promise.all([
        dataProvider.updateWatchlistItem(updatedItems[idx].id, { sortOrder: idx }),
        dataProvider.updateWatchlistItem(updatedItems[idx + 1].id, { sortOrder: idx + 1 }),
      ]);
    } catch {
      setItems(previousItems);
      showToast({ message: "Could not reorder. Please try again.", type: "error" });
    }
  }, [items, showToast]);

  // categoryDisplayName moved above share handlers

  const handleCloseReorder = useCallback(() => setReorderItemId(null), []);

  const handleOpenAddForm = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    setShowAddForm(true);
  }, []);

  return (
    <View style={[styles.safe, { backgroundColor: colors.background }]}>
      <KeyboardAvoidingView
        style={styles.flex1}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        {/* Header */}
        <View style={[styles.header, { backgroundColor: colors.background }]}>
          <View style={styles.headerText}>
            <Text style={[styles.headerLabel, { color: colors.muted }]}>COLLECTOR</Text>
            <Text style={[styles.headerTitle, { color: colors.text }]}>Watchlist</Text>
          </View>

          {/* Select / Cancel toggle button */}
          {items.length > 0 && (
            <AnimatedPressable
              style={[styles.selectHeaderBtn, { backgroundColor: isMultiSelectMode ? colors.accent + '20' : 'transparent' }]}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                if (isMultiSelectMode) {
                  exitMultiSelectMode();
                } else {
                  enterMultiSelectMode();
                  setReorderItemId(null);
                }
              }}
              accessibilityRole="button"
              accessibilityLabel={isMultiSelectMode ? 'Cancel selection' : 'Select items'}
            >
              <Text style={[styles.selectHeaderBtnText, { color: colors.accent }]}>
                {isMultiSelectMode ? 'Cancel' : 'Select'}
              </Text>
            </AnimatedPressable>
          )}

          {!isMultiSelectMode && items.length > 0 && (
            <AnimatedPressable
              style={[styles.shareHeaderBtn, { backgroundColor: colors.accent + '15' }]}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                Alert.alert(
                  'Share Watchlist',
                  `Share your ${items.length} watchlist items`,
                  [
                    { text: 'Cancel', style: 'cancel' },
                    { text: 'Share as Text', onPress: handleShareText },
                    { text: 'Export CSV', onPress: handleShareCSV },
                  ],
                );
              }}
              accessibilityRole="button"
              accessibilityLabel="Share watchlist"
            >
              <Ionicons name="share-outline" size={22} color={colors.brand?.dark ?? colors.accent} />
            </AnimatedPressable>
          )}

          {!isMultiSelectMode && (
            <AnimatedPressable
              style={[styles.addHeaderBtn, { backgroundColor: colors.accent + '15' }]}
              onPress={handleOpenAddForm}
              accessibilityRole="button"
              accessibilityLabel="Add item to watchlist"
            >
              <Ionicons name="add" size={24} color={colors.brand?.dark ?? colors.accent} />
            </AnimatedPressable>
          )}
        </View>

        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor={colors.accent}
            />
          }
        >
          <Animated.View style={settings.animationsEnabled ? animatedStyle : undefined}>
            {/* Stats Banner */}
            {!loading && items.length > 0 && (
              <WatchlistStatsBanner stats={stats} colors={colors} />
            )}

            {/* Category filter chips + sort pill */}
            {!loading && items.length > 0 && !isMultiSelectMode && (
              <WatchlistFilterSort
                colors={colors}
                hapticsEnabled={settings.hapticsEnabled}
                activeCategory={activeCategory}
                setActiveCategory={setActiveCategory}
                sortKey={sortKey}
                setSortKey={setSortKey}
                showSortMenu={showSortMenu}
                setShowSortMenu={setShowSortMenu}
                uniqueCategories={uniqueCategories}
                categoryDisplayName={categoryDisplayName}
              />
            )}

            {/* Error */}
            {error && (
              <View style={[styles.errorBanner, { backgroundColor: colors.card, borderColor: colors.danger + '40' }]}>
                <Ionicons name="warning-outline" size={16} color={colors.danger} />
                <Text style={[styles.errorText, { color: colors.danger }]}>{error}</Text>
                <AnimatedPressable
                  onPress={handleRefresh}
                  accessibilityRole="button"
                  accessibilityLabel="Retry loading watchlist"
                  style={styles.retryBtn}
                >
                  <Text style={[styles.retryText, { color: colors.accent }]}>Retry</Text>
                </AnimatedPressable>
              </View>
            )}

            {/* Loading */}
            {loading && (
              <SkeletonList count={3} type="card" />
            )}

            {/* Add Form */}
            {showAddForm && (
              <WatchlistAddForm
                colors={colors}
                currency={settings.currency}
                saving={saving}
                newTitle={newTitle}
                setNewTitle={setNewTitle}
                newTargetPrice={newTargetPrice}
                setNewTargetPrice={setNewTargetPrice}
                newPriority={newPriority}
                setNewPriority={setNewPriority}
                newNotes={newNotes}
                setNewNotes={setNewNotes}
                targetPriceRef={targetPriceRef}
                notesRef={notesRef}
                onSave={handleSave}
                onClose={resetForm}
              />
            )}

            {/* Empty State */}
            {!loading && items.length === 0 && !showAddForm && (
              <WatchlistEmptyState colors={colors} onAdd={handleOpenAddForm} />
            )}

            {/* Watchlist Items */}
            {!loading && sortedItems.length > 0 && (
              <View style={styles.listSection}>
                <Text style={[styles.listTitle, { color: colors.muted }]}>
                  {sortedItems.length} {sortedItems.length === 1 ? "item" : "items"}
                  {activeCategory ? ` in ${categoryDisplayName(activeCategory)}` : ''}
                </Text>

                {sortedItems.map((item, index) => (
                  <WatchlistItemCard
                    key={item.id}
                    item={item}
                    colors={colors}
                    currency={settings.currency}
                    isMultiSelectMode={isMultiSelectMode}
                    isSelected={isSelected(item.id)}
                    isReordering={reorderItemId === item.id}
                    isFirst={index === 0}
                    isLast={index === sortedItems.length - 1}
                    hapticsEnabled={settings.hapticsEnabled}
                    onToggleSelect={toggleItem}
                    onLongPress={handleLongPress}
                    onDelete={handleDelete}
                    onMoveUp={handleMoveUp}
                    onMoveDown={handleMoveDown}
                    onCloseReorder={handleCloseReorder}
                    categoryDisplayName={categoryDisplayName}
                  />
                ))}
              </View>
            )}

            {/* Inline Add Button (when form is closed and list exists) */}
            {!showAddForm && items.length > 0 && !isMultiSelectMode && (
              <AnimatedPressable style={[styles.inlineAddBtn, { backgroundColor: colors.accent }]} onPress={handleOpenAddForm} accessibilityRole="button" accessibilityLabel="Add item to watchlist">
                <Ionicons name="add" size={20} color="#FFFFFF" />
                <Text style={styles.inlineAddText}>Add Item</Text>
              </AnimatedPressable>
            )}

            {/* Bottom spacing for QuickNavBar / bulk action bar */}
            <View style={isMultiSelectMode ? styles.bottomSpacerBulk : styles.bottomSpacer} />
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Bulk Action Bar (visible in multi-select mode) */}
      {isMultiSelectMode && (
        <WatchlistBulkBar
          colors={colors}
          selectedCount={selectedCount}
          onBulkDelete={handleBulkDelete}
          onExportCSV={handleExportCSV}
          onCancel={exitMultiSelectMode}
        />
      )}

      {!isMultiSelectMode && <QuickNavBar />}
    </View>
  );
}

export default function WatchlistBuilderScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Watchlist Builder">
      <WatchlistBuilderScreen />
    </ScreenErrorBoundary>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Styles (structural only — colors applied inline via theme)
// ─────────────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  flex1: {
    flex: 1,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  headerText: {
    flex: 1,
    marginLeft: 4,
  },
  headerLabel: {
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 0.5,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: "800",
  },
  addHeaderBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
  },
  shareHeaderBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    marginRight: 4,
  },
  selectHeaderBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
    marginRight: 8,
  },
  selectHeaderBtnText: {
    fontSize: 14,
    fontWeight: "600",
  },

  // Error
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 16,
  },
  errorText: {
    fontSize: 13,
    flex: 1,
  },
  retryBtn: {
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  retryText: {
    fontSize: 13,
    fontWeight: "600",
  },

  // List Section
  listSection: {
    marginTop: 8,
  },
  listTitle: {
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 12,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },

  // Inline Add Button
  inlineAddBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    borderRadius: 12,
    paddingVertical: 14,
    alignSelf: "center",
    paddingHorizontal: 24,
    marginTop: 8,
  },
  inlineAddText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },

  // Bottom spacing for QuickNavBar
  bottomSpacer: {
    height: 64,
  },
  bottomSpacerBulk: {
    height: 100,
  },
});
