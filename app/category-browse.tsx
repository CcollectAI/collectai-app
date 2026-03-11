/**
 * Category Browse — Pro-grade item browser for a single category.
 *
 * Shows all missing items in a category with search, filter by ownership,
 * and one-tap "Mark Owned" action. Navigated to from "X more to collect"
 * on the category overview page.
 */
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import {
  View,
  Text,
  TextInput,
  Image,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useLocalSearchParams, useRouter, Stack } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  dataProvider,
  type CategoryMissingItem,
} from "@/data";
import { getCategoryById, CATEGORY_VISUAL, type CategoryId } from "@/data/categories";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { QuickNavBar } from "@/components/QuickNavBar";
import { useToast } from "@/components/Toast";
import logger from "@/utils/logger";

type FilterMode = "all" | "missing" | "owned";

function CategoryBrowseScreen() {
  const { categoryId } = useLocalSearchParams<{ categoryId: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { showToast } = useToast();

  const catMeta = getCategoryById(categoryId as CategoryId);
  const visual = CATEGORY_VISUAL[categoryId as CategoryId];
  // Use app theme accent for all UI; category accent only for small visual indicators
  const categoryAccent = visual?.accentColor ?? colors.accent;
  const catName = catMeta?.name ?? categoryId ?? "Category";

  const [items, setItems] = useState<CategoryMissingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterMode>("missing");
  const [ownedIds, setOwnedIds] = useState<Set<string>>(new Set());
  const [markingId, setMarkingId] = useState<string | null>(null);

  const loadItems = useCallback(async () => {
    if (!categoryId) return;
    try {
      const data = await dataProvider.listCategoryMissing(categoryId);
      setItems(data);
    } catch (err) {
      logger.warn("[CategoryBrowse] load error:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [categoryId]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    loadItems();
  }, [loadItems]);

  const handleMarkOwned = useCallback(
    async (item: CategoryMissingItem) => {
      if (ownedIds.has(item.id)) return;
      setMarkingId(item.id);
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      try {
        await dataProvider.markCategoryItemOwned(item.id, 1);
        setOwnedIds((prev) => new Set(prev).add(item.id));
        showToast({ message: `Added "${item.title}" to collection`, type: "success" });
      } catch {
        showToast({ message: "Failed to mark as owned", type: "error" });
      } finally {
        setMarkingId(null);
      }
    },
    [ownedIds, settings.hapticsEnabled, showToast],
  );

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((item) => {
      if (q && !item.title.toLowerCase().includes(q) && !(item.brand?.toLowerCase().includes(q))) {
        return false;
      }
      if (filter === "owned") return ownedIds.has(item.id);
      if (filter === "missing") return !ownedIds.has(item.id);
      return true;
    });
  }, [items, search, filter, ownedIds]);

  const missingCount = items.filter((i) => !ownedIds.has(i.id)).length;
  const ownedCount = ownedIds.size;

  const renderItem = useCallback(
    ({ item }: { item: CategoryMissingItem }) => {
      const isOwned = ownedIds.has(item.id);
      const isMarking = markingId === item.id;

      return (
        <View style={[s.itemCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <View style={[s.itemAccent, { backgroundColor: isOwned ? "#22c55e" : colors.accent }]} />
          <View style={s.itemBody}>
            <View style={s.itemTop}>
              <View style={s.itemInfo}>
                <Text style={[s.itemTitle, { color: colors.text }]} numberOfLines={1}>
                  {item.title}
                </Text>
                {item.brand && (
                  <Text style={[s.itemBrand, { color: colors.muted }]} numberOfLines={1}>
                    {item.brand}
                  </Text>
                )}
                {item.notes && (
                  <Text style={[s.itemNotes, { color: colors.muted }]} numberOfLines={2}>
                    {item.notes}
                  </Text>
                )}
              </View>

              {isOwned ? (
                <View style={[s.ownedBadge, { backgroundColor: "#22c55e15" }]}>
                  <Ionicons name="checkmark-circle" size={18} color="#22c55e" />
                  <Text style={s.ownedBadgeText}>Owned</Text>
                </View>
              ) : (
                <AnimatedPressable
                  onPress={() => handleMarkOwned(item)}
                  disabled={isMarking}
                  style={[s.addBtn, { backgroundColor: colors.accent }]}
                  accessibilityRole="button"
                  accessibilityLabel={`Mark "${item.title}" as owned`}
                >
                  {isMarking ? (
                    <ActivityIndicator size="small" color="#fff" />
                  ) : (
                    <>
                      <Ionicons name="add" size={16} color="#fff" />
                      <Text style={s.addBtnText}>Add</Text>
                    </>
                  )}
                </AnimatedPressable>
              )}
            </View>
          </View>
        </View>
      );
    },
    [colors, ownedIds, markingId, handleMarkOwned],
  );

  const FILTERS: { key: FilterMode; label: string; count: number }[] = [
    { key: "all", label: "All", count: items.length },
    { key: "missing", label: "Missing", count: missingCount },
    { key: "owned", label: "Owned", count: ownedCount },
  ];

  return (
    <View style={[s.container, { backgroundColor: colors.background }]}>
      <Stack.Screen
        options={{
          title: catName,
          headerTintColor: colors.text,
          headerStyle: { backgroundColor: colors.background },
        }}
      />

      {/* Header stats card */}
      <View style={[s.statsCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={[s.statsAccent, { backgroundColor: categoryAccent }]} />
        <View style={s.statsContent}>
          <Text style={[s.statsTitle, { color: colors.text }]}>Collection Progress</Text>
          <View style={s.statsRow}>
            <View style={s.statItem}>
              <Text style={[s.statValue, { color: "#22c55e" }]}>{ownedCount}</Text>
              <Text style={[s.statLabel, { color: colors.muted }]}>Owned</Text>
            </View>
            <View style={[s.statDivider, { backgroundColor: colors.border }]} />
            <View style={s.statItem}>
              <Text style={[s.statValue, { color: colors.accent }]}>{missingCount}</Text>
              <Text style={[s.statLabel, { color: colors.muted }]}>Missing</Text>
            </View>
            <View style={[s.statDivider, { backgroundColor: colors.border }]} />
            <View style={s.statItem}>
              <Text style={[s.statValue, { color: colors.text }]}>{items.length}</Text>
              <Text style={[s.statLabel, { color: colors.muted }]}>Total</Text>
            </View>
          </View>
          {/* Progress bar */}
          <View style={[s.progressTrack, { backgroundColor: colors.border }]}>
            <View
              style={[
                s.progressFill,
                {
                  backgroundColor: "#22c55e",
                  width: items.length > 0 ? `${Math.round((ownedCount / items.length) * 100)}%` : "0%",
                },
              ]}
            />
          </View>
        </View>
      </View>

      {/* Search */}
      <View style={[s.searchRow, { borderColor: colors.border }]}>
        <Ionicons name="search-outline" size={18} color={colors.muted} />
        <TextInput
          style={[s.searchInput, { color: colors.text }]}
          placeholder={`Search ${catName} items...`}
          placeholderTextColor={colors.muted}
          value={search}
          onChangeText={setSearch}
          autoCorrect={false}
          autoCapitalize="none"
          returnKeyType="search"
          accessibilityLabel={`Search ${catName} items`}
        />
        {search.length > 0 && (
          <AnimatedPressable onPress={() => setSearch("")} accessibilityLabel="Clear search">
            <Ionicons name="close-circle" size={18} color={colors.muted} />
          </AnimatedPressable>
        )}
      </View>

      {/* Filter pills */}
      <View style={s.filterRow}>
        {FILTERS.map((f) => {
          const active = filter === f.key;
          return (
            <AnimatedPressable
              key={f.key}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
                setFilter(f.key);
              }}
              style={[
                s.filterPill,
                {
                  backgroundColor: active ? colors.accent : colors.card,
                  borderColor: active ? colors.accent : colors.border,
                },
              ]}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              accessibilityLabel={`${f.label}: ${f.count}`}
            >
              <Text style={[s.filterPillText, { color: active ? "#fff" : colors.text }]}>
                {f.label}
              </Text>
              <View style={[s.filterBadge, { backgroundColor: active ? "#ffffff30" : colors.border }]}>
                <Text style={[s.filterBadgeText, { color: active ? "#fff" : colors.muted }]}>
                  {f.count}
                </Text>
              </View>
            </AnimatedPressable>
          );
        })}
      </View>

      {/* Item list */}
      {loading ? (
        <View style={s.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
        <FlashList
          data={filteredItems}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          contentContainerStyle={s.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor={colors.accent}
              colors={[colors.accent]}
            />
          }
          ListEmptyComponent={
            <View style={s.emptyContainer}>
              <Ionicons
                name={filter === "owned" ? "checkmark-done-circle-outline" : "search-outline"}
                size={48}
                color={colors.muted}
              />
              <Text style={[s.emptyTitle, { color: colors.text }]}>
                {filter === "owned"
                  ? "No owned items yet"
                  : search
                  ? "No matching items"
                  : "All caught up!"}
              </Text>
              <Text style={[s.emptySubtitle, { color: colors.muted }]}>
                {filter === "owned"
                  ? "Tap Add on items below to track your collection"
                  : search
                  ? "Try a different search term"
                  : "You've collected everything in this category"}
              </Text>
            </View>
          }
        />
      )}

      <QuickNavBar />
    </View>
  );
}

const s = StyleSheet.create({
  container: {
    flex: 1,
  },
  // Stats card
  statsCard: {
    flexDirection: "row",
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 14,
    borderWidth: 1,
    overflow: "hidden",
  },
  statsAccent: {
    width: 5,
  },
  statsContent: {
    flex: 1,
    padding: 14,
  },
  statsTitle: {
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 12,
  },
  statsRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 12,
  },
  statItem: {
    flex: 1,
    alignItems: "center",
  },
  statValue: {
    fontSize: 22,
    fontWeight: "800",
  },
  statLabel: {
    fontSize: 11,
    fontWeight: "600",
    marginTop: 2,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  statDivider: {
    width: 1,
    height: 28,
  },
  progressTrack: {
    height: 6,
    borderRadius: 3,
  },
  progressFill: {
    height: 6,
    borderRadius: 3,
  },
  // Search
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: 16,
    marginTop: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
    paddingVertical: 0,
  },
  // Filter pills
  filterRow: {
    flexDirection: "row",
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
  },
  filterPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
  },
  filterPillText: {
    fontSize: 13,
    fontWeight: "600",
  },
  filterBadge: {
    minWidth: 22,
    height: 20,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 5,
  },
  filterBadgeText: {
    fontSize: 11,
    fontWeight: "700",
  },
  // List
  list: {
    paddingHorizontal: 16,
    paddingBottom: 80,
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  // Item card
  itemCard: {
    flexDirection: "row",
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 8,
    overflow: "hidden",
  },
  itemAccent: {
    width: 4,
  },
  itemBody: {
    flex: 1,
    padding: 14,
  },
  itemTop: {
    flexDirection: "row",
    alignItems: "center",
  },
  itemInfo: {
    flex: 1,
    paddingRight: 12,
  },
  itemTitle: {
    fontSize: 15,
    fontWeight: "600",
  },
  itemBrand: {
    fontSize: 12,
    fontWeight: "500",
    marginTop: 2,
  },
  itemNotes: {
    fontSize: 12,
    marginTop: 4,
    lineHeight: 16,
    fontStyle: "italic",
  },
  // Owned badge
  ownedBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  ownedBadgeText: {
    color: "#22c55e",
    fontSize: 12,
    fontWeight: "700",
  },
  // Add button
  addBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    minWidth: 60,
    justifyContent: "center",
  },
  addBtnText: {
    color: "#fff",
    fontSize: 13,
    fontWeight: "600",
  },
  // Empty
  emptyContainer: {
    alignItems: "center",
    paddingTop: 60,
    paddingHorizontal: 32,
  },
  emptyTitle: {
    fontSize: 17,
    fontWeight: "700",
    marginTop: 12,
  },
  emptySubtitle: {
    fontSize: 14,
    textAlign: "center",
    marginTop: 6,
    lineHeight: 20,
  },
});

export default function CategoryBrowseScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Category Browse">
      <CategoryBrowseScreen />
    </ScreenErrorBoundary>
  );
}
