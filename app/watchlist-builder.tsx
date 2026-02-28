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
 * - Sort menu (Priority / Newest / Price)
 */

import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';
import { SkeletonList } from '@/components/Skeleton';
import { SwipeableRow, SwipeActions } from '@/components/SwipeableRow';
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TextInput,
  Alert,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Animated,
  RefreshControl,
} from "react-native";
import { useToast } from "@/components/Toast";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable, useEnterReveal } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { useAppTheme } from "@/hooks/useAppTheme";
import logger from "@/utils/logger";
import { QuickNavBar } from "@/components/QuickNavBar";
import { formatPrice, getCurrencySymbol } from "@/lib/format";
import { CATEGORY_SLUG_TO_NAME } from "@/constants/categories";

import { useAuthContext } from "@/providers/useAuthContext";
import { dataProvider } from "@/data";
import type { WatchlistItem } from "@/data/types";
import { useWatchlistRealtime } from "@/hooks/useWatchlistRealtime";

type WatchlistPriority = 'high' | 'medium' | 'low';

// Relative time helper for "Last checked" display
function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Not checked yet';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

const TREND_INDICATOR: Record<string, { symbol: string; color: string }> = {
  up: { symbol: '\u25B2', color: '#059669' },
  down: { symbol: '\u25BC', color: '#DC2626' },
  stable: { symbol: '\u2550', color: '#6B7280' },
};

// ─────────────────────────────────────────────────────────────────────────────
// Priority config (semantic colors — not theme-dependent)
// ─────────────────────────────────────────────────────────────────────────────

const PRIORITY_CONFIG: Record<WatchlistPriority, { label: string; color: string; bg: string }> = {
  high: { label: "High", color: "#DC2626", bg: "#DC262615" },
  medium: { label: "Medium", color: "#D97706", bg: "#D9770615" },
  low: { label: "Low", color: "#059669", bg: "#05966915" },
};

// ─────────────────────────────────────────────────────────────────────────────
// Sort options
// ─────────────────────────────────────────────────────────────────────────────

type SortKey = 'priority' | 'newest' | 'price_asc' | 'price_desc';

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'priority', label: 'Priority (High\u2192Low)' },
  { key: 'newest', label: 'Newest first' },
  { key: 'price_asc', label: 'Price (Low\u2192High)' },
  { key: 'price_desc', label: 'Price (High\u2192Low)' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

function WatchlistBuilderScreen() {
  const router = useRouter();
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
      logger.warn("[watchlist-builder] load error", err);
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
  const sortedItems = useMemo(() => {
    const priorityOrder: Record<WatchlistPriority, number> = { high: 0, medium: 1, low: 2 };
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
        default:
          return 0;
      }
    });
  }, [filteredItems, sortKey]);

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

  // Save new item
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

    setSaving(true);
    try {
      await dataProvider.addWatchlistItem({
        title,
        category: '',
        targetPrice: targetPrice,
        priority: newPriority,
        notes: newNotes.trim() || undefined,
      });

      resetForm();
      await loadWatchlist();
    } catch (err: unknown) {
      logger.warn("[watchlist-builder] save error", err);
      showToast({ message: err instanceof Error ? err.message : "Unable to save this item.", type: "error" });
    } finally {
      setSaving(false);
    }
  }, [userId, newTitle, newTargetPrice, newPriority, newNotes, loadWatchlist, settings.currency, showToast]);

  // Delete item (used by both trash button and swipe)
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
              try {
                await dataProvider.removeWatchlistItem(item.id);
                await loadWatchlist();
              } catch {
                showToast({ message: "Could not remove this item.", type: "error" });
              }
            },
          },
        ]
      );
    },
    [loadWatchlist, showToast]
  );

  // Resolve category slug to human-readable name
  const categoryDisplayName = (slug: string): string =>
    CATEGORY_SLUG_TO_NAME[slug] || slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

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
          <AnimatedPressable
            style={[styles.addHeaderBtn, { backgroundColor: colors.accent + '15' }]}
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setShowAddForm(true); }}
            accessibilityRole="button"
            accessibilityLabel="Add item to watchlist"
          >
            <Ionicons name="add" size={24} color={colors.brand?.dark ?? colors.accent} />
          </AnimatedPressable>
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
            {/* Stats Banner — hidden during loading */}
            {!loading && items.length > 0 && (
              <View style={[styles.statsBanner, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <View style={styles.statItem} accessibilityLabel={`${stats.total} items`}>
                  <Text style={[styles.statValue, { color: colors.text }]}>{stats.total}</Text>
                  <Text style={[styles.statLabel, { color: colors.muted }]}>Items</Text>
                </View>
                <View style={[styles.statDivider, { backgroundColor: colors.border }]} />
                <View style={styles.statItem} accessibilityLabel={`${stats.high} high priority`}>
                  <Text style={[styles.statValue, { color: colors.text }]}>{stats.high}</Text>
                  <Text style={[styles.statLabel, { color: colors.muted }]}>High Priority</Text>
                </View>
                <View style={[styles.statDivider, { backgroundColor: colors.border }]} />
                <View style={styles.statItem} accessibilityLabel={`${stats.withTarget} with targets`}>
                  <Text style={[styles.statValue, { color: colors.text }]}>{stats.withTarget}</Text>
                  <Text style={[styles.statLabel, { color: colors.muted }]}>With Targets</Text>
                </View>
              </View>
            )}

            {/* Category filter chips + sort pill */}
            {!loading && items.length > 0 && (
              <View style={styles.filterSortRow}>
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  style={styles.filterChipScroll}
                  contentContainerStyle={styles.filterChipContent}
                >
                  {/* "All" chip */}
                  <AnimatedPressable
                    onPress={() => {
                      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                      setActiveCategory(null);
                    }}
                    style={[
                      styles.filterChip,
                      { borderColor: !activeCategory ? colors.accent : colors.border },
                      !activeCategory && { backgroundColor: colors.accent + '15' },
                    ]}
                    accessibilityRole="button"
                    accessibilityLabel="Show all categories"
                    accessibilityState={{ selected: !activeCategory }}
                  >
                    <Text style={[styles.filterChipText, { color: !activeCategory ? colors.accent : colors.muted }]}>
                      All
                    </Text>
                  </AnimatedPressable>

                  {/* Category chips */}
                  {uniqueCategories.map((catSlug) => {
                    const isActive = activeCategory === catSlug;
                    return (
                      <AnimatedPressable
                        key={catSlug}
                        onPress={() => {
                          fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                          setActiveCategory(isActive ? null : catSlug);
                        }}
                        style={[
                          styles.filterChip,
                          { borderColor: isActive ? colors.accent : colors.border },
                          isActive && { backgroundColor: colors.accent + '15' },
                        ]}
                        accessibilityRole="button"
                        accessibilityLabel={`Filter by ${categoryDisplayName(catSlug)}`}
                        accessibilityState={{ selected: isActive }}
                      >
                        <Text style={[styles.filterChipText, { color: isActive ? colors.accent : colors.muted }]}>
                          {categoryDisplayName(catSlug)}
                        </Text>
                      </AnimatedPressable>
                    );
                  })}
                </ScrollView>

                {/* Sort pill */}
                <AnimatedPressable
                  onPress={() => {
                    fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                    setShowSortMenu((v) => !v);
                  }}
                  style={[styles.sortPill, { borderColor: colors.border, backgroundColor: colors.card }]}
                  accessibilityRole="button"
                  accessibilityLabel="Sort watchlist"
                >
                  <Ionicons name="swap-vertical-outline" size={14} color={colors.accent} />
                  <Text style={[styles.sortPillText, { color: colors.text }]} numberOfLines={1}>
                    {SORT_OPTIONS.find((o) => o.key === sortKey)?.label.split(' ')[0] ?? 'Sort'}
                  </Text>
                </AnimatedPressable>
              </View>
            )}

            {/* Sort dropdown menu */}
            {showSortMenu && (
              <View style={[styles.sortMenu, { backgroundColor: colors.card, borderColor: colors.border }]}>
                {SORT_OPTIONS.map((opt) => {
                  const isActive = sortKey === opt.key;
                  return (
                    <AnimatedPressable
                      key={opt.key}
                      onPress={() => {
                        fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                        setSortKey(opt.key);
                        setShowSortMenu(false);
                      }}
                      style={[
                        styles.sortMenuItem,
                        isActive && { backgroundColor: colors.accent + '12' },
                      ]}
                      accessibilityRole="button"
                      accessibilityState={{ selected: isActive }}
                      accessibilityLabel={`Sort by ${opt.label}`}
                    >
                      <Text style={[styles.sortMenuItemText, { color: isActive ? colors.accent : colors.text }]}>
                        {opt.label}
                      </Text>
                      {isActive && (
                        <Ionicons name="checkmark" size={16} color={colors.accent} />
                      )}
                    </AnimatedPressable>
                  );
                })}
              </View>
            )}

            {/* Error */}
            {error && (
              <View style={[styles.errorBanner, { backgroundColor: colors.card, borderColor: '#EF444440' }]}>
                <Ionicons name="warning-outline" size={16} color="#EF4444" />
                <Text style={[styles.errorText, { color: '#EF4444' }]}>{error}</Text>
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

            {/* Loading — skeleton cards */}
            {loading && (
              <SkeletonList count={3} type="card" />
            )}

            {/* Add Form (Expanded) */}
            {showAddForm && (
              <View style={[styles.addFormCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
                <View style={styles.addFormHeader}>
                  <Text style={[styles.addFormTitle, { color: colors.text }]}>Add to Watchlist</Text>
                  <AnimatedPressable onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); resetForm(); }} style={styles.closeFormBtn} accessibilityRole="button" accessibilityLabel="Close add form">
                    <Ionicons name="close" size={20} color={colors.muted} />
                  </AnimatedPressable>
                </View>

                {/* Title Input */}
                <View style={styles.inputGroup}>
                  <Text style={[styles.inputLabel, { color: colors.text }]}>Item Name *</Text>
                  <TextInput
                    style={[styles.textInput, { backgroundColor: colors.background, borderColor: colors.border, color: colors.text }]}
                    value={newTitle}
                    onChangeText={setNewTitle}
                    placeholder="e.g., PSA 10 Charizard Base Set"
                    placeholderTextColor={colors.muted}
                    autoFocus
                    returnKeyType="next"
                    onSubmitEditing={() => targetPriceRef.current?.focus()}
                    maxLength={100}
                    accessibilityLabel="Item name"
                  />
                </View>

                {/* Target Price Input */}
                <View style={styles.inputGroup}>
                  <Text style={[styles.inputLabel, { color: colors.text }]}>Target Price ({settings.currency}) — optional</Text>
                  <View style={styles.priceInputRow}>
                    <Text style={[styles.currencyPrefix, { color: colors.muted }]}>{getCurrencySymbol(settings.currency)}</Text>
                    <TextInput
                      ref={targetPriceRef}
                      style={[styles.textInput, styles.priceInput, { backgroundColor: colors.background, borderColor: colors.border, color: colors.text }]}
                      value={newTargetPrice}
                      onChangeText={setNewTargetPrice}
                      placeholder="e.g., 500"
                      placeholderTextColor={colors.muted}
                      keyboardType="decimal-pad"
                      returnKeyType="next"
                      onSubmitEditing={() => notesRef.current?.focus()}
                      accessibilityLabel={`Target price in ${settings.currency}`}
                    />
                  </View>
                  <Text style={[styles.inputHint, { color: colors.muted }]}>Get notified when price hits your target</Text>
                </View>

                {/* Priority Selector */}
                <View style={styles.inputGroup}>
                  <Text style={[styles.inputLabel, { color: colors.text }]}>Priority</Text>
                  <View style={styles.priorityRow}>
                    {(["high", "medium", "low"] as WatchlistPriority[]).map((p) => {
                      const config = PRIORITY_CONFIG[p];
                      const active = newPriority === p;
                      return (
                        <AnimatedPressable
                          key={p}
                          style={[
                            styles.priorityBtn,
                            { borderColor: colors.border, backgroundColor: colors.card },
                            active && { backgroundColor: config.bg, borderColor: config.color },
                          ]}
                          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setNewPriority(p); }}
                          accessibilityRole="button"
                          accessibilityState={{ selected: active }}
                          accessibilityLabel={`${config.label} priority`}
                        >
                          <Text
                            style={[
                              styles.priorityBtnText,
                              { color: colors.muted },
                              active && { color: config.color, fontWeight: "700" },
                            ]}
                          >
                            {config.label}
                          </Text>
                        </AnimatedPressable>
                      );
                    })}
                  </View>
                </View>

                {/* Notes Input */}
                <View style={styles.inputGroup}>
                  <Text style={[styles.inputLabel, { color: colors.text }]}>Notes (optional)</Text>
                  <TextInput
                    ref={notesRef}
                    style={[styles.textInput, styles.textInputMultiline, { backgroundColor: colors.background, borderColor: colors.border, color: colors.text }]}
                    value={newNotes}
                    onChangeText={setNewNotes}
                    placeholder="Any notes about this item..."
                    placeholderTextColor={colors.muted}
                    multiline
                    numberOfLines={2}
                    maxLength={500}
                    returnKeyType="done"
                    accessibilityLabel="Notes"
                  />
                </View>

                {/* Save Button */}
                <AnimatedPressable
                  style={[styles.saveBtn, { backgroundColor: colors.accent }, saving && styles.saveBtnDisabled]}
                  onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED); handleSave(); }}
                  disabled={saving}
                  accessibilityRole="button"
                  accessibilityLabel={saving ? 'Saving' : 'Add to watchlist'}
                >
                  {saving ? (
                    <ActivityIndicator size="small" color="#FFFFFF" />
                  ) : (
                    <>
                      <Ionicons name="add-circle" size={20} color="#FFFFFF" />
                      <Text style={styles.saveBtnText}>Add to Watchlist</Text>
                    </>
                  )}
                </AnimatedPressable>
              </View>
            )}

            {/* Empty State */}
            {!loading && items.length === 0 && !showAddForm && (
              <AnimatedPressable style={styles.emptyState} onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setShowAddForm(true); }} accessibilityRole="button" accessibilityLabel="Start your watchlist, add your first item">
                <View style={[styles.emptyIconWrap, { backgroundColor: colors.accent + '15' }]}>
                  <Ionicons name="eye-outline" size={32} color={colors.accent} />
                </View>
                <Text style={[styles.emptyTitle, { color: colors.text }]}>Start Your Watchlist</Text>
                <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
                  Track items you want to buy and set price targets to get notified when
                  they hit your budget.
                </Text>
                <View style={[styles.emptyAddBtn, { backgroundColor: colors.accent + '15' }]}>
                  <Ionicons name="add" size={18} color={colors.brand?.dark ?? colors.accent} />
                  <Text style={[styles.emptyAddText, { color: colors.brand?.dark ?? colors.accent }]}>Add Your First Item</Text>
                </View>
              </AnimatedPressable>
            )}

            {/* Watchlist Items */}
            {!loading && sortedItems.length > 0 && (
              <View style={styles.listSection}>
                <Text style={[styles.listTitle, { color: colors.muted }]}>
                  {sortedItems.length} {sortedItems.length === 1 ? "item" : "items"}
                  {activeCategory ? ` in ${categoryDisplayName(activeCategory)}` : ''}
                </Text>

                {sortedItems.map((item) => {
                  const priorityConfig = PRIORITY_CONFIG[item.priority] ?? PRIORITY_CONFIG.medium;
                  return (
                    <SwipeableRow
                      key={item.id}
                      rightActions={[
                        SwipeActions.delete(() => handleDelete(item)),
                      ]}
                      enableHaptics={settings.hapticsEnabled}
                    >
                      <View style={[styles.itemCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
                        <View style={styles.itemCardMain}>
                          <View style={styles.itemCardLeft}>
                            <View style={styles.itemTitleRow}>
                              <Text style={[styles.itemTitle, { color: colors.text }]} numberOfLines={2}>
                                {item.title}
                              </Text>
                              <View
                                style={[
                                  styles.priorityBadge,
                                  { backgroundColor: priorityConfig.bg },
                                ]}
                              >
                                <Text
                                  style={[styles.priorityBadgeText, { color: priorityConfig.color }]}
                                >
                                  {priorityConfig.label}
                                </Text>
                              </View>
                            </View>

                            {/* Category label */}
                            {item.category ? (
                              <Text style={[styles.categoryLabel, { color: colors.muted }]} numberOfLines={1}>
                                {categoryDisplayName(item.category)}
                              </Text>
                            ) : null}

                            {item.targetPrice != null && (
                              <View style={[styles.targetBadge, { backgroundColor: colors.accent + '12' }]}>
                                <Ionicons name="flag" size={12} color={colors.brand?.dark ?? colors.accent} />
                                <Text style={[styles.targetBadgeText, { color: colors.brand?.dark ?? colors.accent }]}>
                                  Target: {formatPrice(item.targetPrice, settings.currency)}
                                </Text>
                              </View>
                            )}

                            {/* Market price + trend indicator */}
                            {item.lastMarketPrice != null && (
                              <View style={styles.marketRow}>
                                <Text style={[styles.marketLabel, { color: colors.muted }]}>Market: </Text>
                                <Text style={[styles.marketPrice, { color: colors.text }]}>
                                  {formatPrice(item.lastMarketPrice, settings.currency)}
                                </Text>
                                {item.priceTrend && TREND_INDICATOR[item.priceTrend] && (
                                  <Text style={{ color: TREND_INDICATOR[item.priceTrend].color, fontSize: 12, marginLeft: 4 }}>
                                    {TREND_INDICATOR[item.priceTrend].symbol}
                                  </Text>
                                )}
                                {item.marketHitCount != null && item.marketHitCount > 0 && (
                                  <Text style={[styles.hitCount, { color: colors.muted }]}>
                                    {` \u00B7 ${item.marketHitCount} listing${item.marketHitCount === 1 ? '' : 's'}`}
                                  </Text>
                                )}
                              </View>
                            )}

                            {/* Last checked timestamp */}
                            {item.lastCheckedAt && (
                              <Text style={[styles.lastChecked, { color: colors.muted }]}>
                                Checked {timeAgo(item.lastCheckedAt)}
                              </Text>
                            )}

                            {item.notes && (
                              <Text style={[styles.itemNotes, { color: colors.muted }]} numberOfLines={2}>
                                {item.notes}
                              </Text>
                            )}
                          </View>

                          <AnimatedPressable
                            style={styles.deleteBtn}
                            onPress={() => { fireHaptic(HapticIntent.ALERT_TRIGGERED); handleDelete(item); }}
                            accessibilityRole="button"
                            accessibilityLabel={`Remove ${item.title} from watchlist`}
                          >
                            <Ionicons name="trash-outline" size={18} color={colors.muted} />
                          </AnimatedPressable>
                        </View>
                      </View>
                    </SwipeableRow>
                  );
                })}
              </View>
            )}

            {/* Inline Add Button (when form is closed and list exists) */}
            {!showAddForm && items.length > 0 && (
              <AnimatedPressable style={[styles.inlineAddBtn, { backgroundColor: colors.accent }]} onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); setShowAddForm(true); }} accessibilityRole="button" accessibilityLabel="Add item to watchlist">
                <Ionicons name="add" size={20} color="#FFFFFF" />
                <Text style={styles.inlineAddText}>Add Item</Text>
              </AnimatedPressable>
            )}

            {/* Bottom spacing for QuickNavBar */}
            <View style={styles.bottomSpacer} />
          </Animated.View>
        </ScrollView>
      </KeyboardAvoidingView>
      <QuickNavBar />
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
  backBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: -8,
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

  // Stats Banner
  statsBanner: {
    flexDirection: "row",
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  statItem: {
    flex: 1,
    alignItems: "center",
  },
  statValue: {
    fontSize: 24,
    fontWeight: "800",
  },
  statLabel: {
    fontSize: 11,
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    alignSelf: "stretch",
    marginHorizontal: 8,
  },

  // Filter & Sort
  filterSortRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 12,
    gap: 8,
  },
  filterChipScroll: {
    flex: 1,
  },
  filterChipContent: {
    flexDirection: "row",
    alignItems: "center",
  },
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    marginRight: 8,
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: "600",
  },
  sortPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
  sortPillText: {
    fontSize: 12,
    fontWeight: "600",
  },
  sortMenu: {
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 12,
    overflow: "hidden",
  },
  sortMenuItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  sortMenuItemText: {
    fontSize: 13,
    fontWeight: "500",
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

  // Add Form
  addFormCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
  },
  addFormHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  addFormTitle: {
    fontSize: 18,
    fontWeight: "700",
  },
  closeFormBtn: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },

  // Inputs
  inputGroup: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
  },
  inputHint: {
    fontSize: 11,
    marginTop: 4,
  },
  textInput: {
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
  },
  textInputMultiline: {
    minHeight: 60,
    textAlignVertical: "top",
  },
  priceInputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  currencyPrefix: {
    fontSize: 16,
    fontWeight: "600",
    minWidth: 20,
  },
  priceInput: {
    flex: 1,
  },

  // Priority
  priorityRow: {
    flexDirection: "row",
    gap: 8,
  },
  priorityBtn: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: "center",
  },
  priorityBtnText: {
    fontSize: 13,
    fontWeight: "500",
  },

  // Save Button
  saveBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 4,
  },
  saveBtnDisabled: {
    opacity: 0.7,
  },
  saveBtnText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
  },

  // Empty State
  emptyState: {
    alignItems: "center",
    paddingVertical: 40,
    paddingHorizontal: 24,
  },
  emptyIconWrap: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: "700",
    marginBottom: 8,
    textAlign: "center",
  },
  emptySubtitle: {
    fontSize: 14,
    textAlign: "center",
    lineHeight: 20,
    marginBottom: 20,
  },
  emptyAddBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 20,
  },
  emptyAddText: {
    fontSize: 14,
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

  // Item Card
  itemCard: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
    marginBottom: 10,
  },
  itemCardMain: {
    flexDirection: "row",
  },
  itemCardLeft: {
    flex: 1,
  },
  itemTitleRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    marginBottom: 4,
  },
  itemTitle: {
    flex: 1,
    fontSize: 15,
    fontWeight: "600",
    lineHeight: 20,
  },
  priorityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  priorityBadgeText: {
    fontSize: 11,
    fontWeight: "700",
  },
  categoryLabel: {
    fontSize: 11,
    marginBottom: 4,
  },
  targetBadge: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    marginBottom: 4,
  },
  targetBadgeText: {
    fontSize: 12,
    fontWeight: "600",
  },
  targetRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 4,
  },
  targetText: {
    fontSize: 13,
    fontWeight: "600",
  },
  marketRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 4,
  },
  marketLabel: {
    fontSize: 12,
  },
  marketPrice: {
    fontSize: 12,
    fontWeight: "700",
  },
  hitCount: {
    fontSize: 11,
  },
  lastChecked: {
    fontSize: 10,
    marginBottom: 2,
  },
  itemNotes: {
    fontSize: 12,
    marginTop: 4,
    lineHeight: 16,
  },
  deleteBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 8,
  },

  // Inline Add Button (replaces fake "floating" button)
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
});
