/**
 * Category Browse — the catalog "full grid" behind the overview rail's
 * "See all" (mockup: web/category-redesign-preview.html — "scroll the rail or
 * 'See all' for the full grid").
 *
 * A browsable 2-column gallery of the WHOLE category catalog ("what exists"),
 * with search + the same sort chips as the category page. Every tap opens the
 * museum detail (→ affiliate "Where to buy"). Server-side search/sort/paging
 * via /catalog/{cat}/items.
 *
 * The old missing-items checklist that lived here (text rows + Mark Owned) is
 * gone with the redesign — ownership lives on the items tab, the catalog is
 * the museum.
 */
import React, { useEffect, useState, useCallback, useRef } from "react";
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
import { useLocalSearchParams, useRouter, Stack, type Href } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { collectorsApi } from "@/api/collectorsApi";
import { getCategoryById, type CategoryId } from "@/data/categories";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { QuickNavBar } from "@/components/QuickNavBar";
import { colors as tokens } from "@/theme/tokens";
import CategorySortChips, { type CatalogSortKey } from "@/components/category/CategorySortChips";
import type { CatalogItemData } from "@/components/CatalogBrowseSection";
import logger from "@/utils/logger";

const PAGE_SIZE = 40;

function CategoryBrowseScreen() {
  const { categoryId } = useLocalSearchParams<{ categoryId: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();

  const catMeta = getCategoryById(categoryId as CategoryId);
  const catName = catMeta?.name ?? categoryId ?? "Category";

  const [items, setItems] = useState<CatalogItemData[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  // Same default as the category page rail: highest-earning items lead.
  const [sort, setSort] = useState<CatalogSortKey>("value");
  // Monotonic request id — a stale slow response must not clobber a newer one.
  const reqId = useRef(0);

  const fetchPage = useCallback(
    async (offset: number, q: string, sortKey: CatalogSortKey, mode: "replace" | "append") => {
      if (!categoryId) return;
      const id = ++reqId.current;
      try {
        const res = await collectorsApi.browseCatalogItems(categoryId, {
          q: q.trim() || undefined,
          limit: PAGE_SIZE,
          offset,
          pricedOnly: sortKey === "value",
          sort: sortKey === "all" ? "title" : sortKey,
        });
        if (id !== reqId.current) return; // superseded
        const page = (res?.items ?? []) as CatalogItemData[];
        setItems((prev) => (mode === "append" ? [...prev, ...page] : page));
        if (typeof res?.total === "number") setTotal(res.total);
      } catch (err) {
        logger.warn("[CategoryBrowse] load error:", err);
        if (mode === "replace" && id === reqId.current) setItems([]);
      } finally {
        if (id === reqId.current) {
          setLoading(false);
          setLoadingMore(false);
          setRefreshing(false);
        }
      }
    },
    [categoryId],
  );

  // First page — refetched on sort change and (debounced) on search input.
  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => fetchPage(0, search, sort, "replace"), search ? 400 : 0);
    return () => clearTimeout(t);
  }, [fetchPage, search, sort]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    fetchPage(0, search, sort, "replace");
  }, [fetchPage, search, sort]);

  const handleEndReached = useCallback(() => {
    if (loading || loadingMore) return;
    if (total != null && items.length >= total) return;
    setLoadingMore(true);
    fetchPage(items.length, search, sort, "append");
  }, [loading, loadingMore, total, items.length, fetchPage, search, sort]);

  const handleSortChange = useCallback(
    (next: CatalogSortKey) => {
      fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: settings.hapticsEnabled });
      setSort(next);
    },
    [settings.hapticsEnabled],
  );

  // Tap → museum detail, same param contract as the category page rail.
  const openMuseum = useCallback(
    (it: CatalogItemData) => {
      router.push({
        pathname: "/catalog-item/[key]",
        params: {
          key: it.item_key, category: it.category, title: it.title,
          image_url: it.image_url ?? "", rarity: it.rarity ?? "",
          set_code: it.set_code ?? "", brand: it.brand ?? "",
          estimated_price: it.estimated_price != null ? String(it.estimated_price) : "",
        },
      } as unknown as Href);
    },
    [router],
  );

  const renderItem = useCallback(
    ({ item }: { item: CatalogItemData }) => (
      <AnimatedPressable
        style={[s.card, { backgroundColor: colors.card, borderColor: colors.border }]}
        onPress={() => openMuseum(item)}
        accessibilityRole="button"
        accessibilityLabel={`View ${item.title}`}
      >
        {item.image_url ? (
          <Image source={{ uri: item.image_url }} style={s.art} resizeMode="cover" accessibilityIgnoresInvertColors />
        ) : (
          <View style={[s.art, s.artEmpty, { backgroundColor: tokens.brand.base + "12" }]}>
            <Ionicons name="cube-outline" size={28} color={tokens.brand.base} />
          </View>
        )}
        <View style={s.meta}>
          <Text style={[s.nm, { color: colors.text }]} numberOfLines={2}>{item.title}</Text>
          {item.estimated_price != null ? (
            <Text style={s.pr}>~€{Math.round(item.estimated_price)}</Text>
          ) : (
            <Text style={[s.tag, { color: colors.muted }]} numberOfLines={1}>
              {item.rarity || item.set_code || "Explore"}
            </Text>
          )}
        </View>
      </AnimatedPressable>
    ),
    [colors, openMuseum],
  );

  return (
    <View style={[s.container, { backgroundColor: colors.background }]}>
      <Stack.Screen
        options={{
          title: `${catName} catalog`,
          headerTintColor: colors.text,
          headerStyle: { backgroundColor: colors.background },
        }}
      />

      {/* Search */}
      <View style={[s.searchRow, { borderColor: colors.border, backgroundColor: colors.card }]}>
        <Ionicons name="search-outline" size={18} color={colors.muted} />
        <TextInput
          style={[s.searchInput, { color: colors.text }]}
          placeholder={`Search ${catName}...`}
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

      {/* Sort chips — same component + order as the category page */}
      <CategorySortChips sort={sort} onChange={handleSortChange} total={total} colors={colors} />

      {/* Catalog grid */}
      {loading ? (
        <View style={s.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
        <FlashList
          data={items}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          numColumns={2}
          contentContainerStyle={s.list}
          onEndReached={handleEndReached}
          onEndReachedThreshold={0.4}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={handleRefresh}
              tintColor={colors.accent}
              colors={[colors.accent]}
            />
          }
          ListFooterComponent={
            loadingMore ? <ActivityIndicator color={colors.accent} style={s.footerSpinner} /> : null
          }
          ListEmptyComponent={
            <View style={s.emptyContainer}>
              <Ionicons name="search-outline" size={48} color={colors.muted} />
              <Text style={[s.emptyTitle, { color: colors.text }]}>
                {search ? "No matching items" : "No catalog items yet"}
              </Text>
              <Text style={[s.emptySubtitle, { color: colors.muted }]}>
                {search ? "Try a different search term" : "This category's catalog is still being curated"}
              </Text>
            </View>
          }
        />
      )}

      <QuickNavBar />
    </View>
  );
}

export default function CategoryBrowseScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Category Browse">
      <CategoryBrowseScreen />
    </ScreenErrorBoundary>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  searchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginHorizontal: 16,
    marginTop: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
  },
  searchInput: { flex: 1, fontSize: 14, padding: 0 },
  loadingContainer: { flex: 1, alignItems: "center", justifyContent: "center" },
  list: { paddingHorizontal: 10, paddingBottom: 96 },
  // Museum card — same visual language as the category rail (mockup `.card`).
  card: {
    flex: 1,
    margin: 6,
    borderRadius: 14,
    borderWidth: 1,
    overflow: "hidden",
  },
  art: { width: "100%", height: 150 },
  artEmpty: { alignItems: "center", justifyContent: "center" },
  meta: { paddingVertical: 8, paddingHorizontal: 10 },
  nm: { fontSize: 12, fontWeight: "700" },
  pr: { fontSize: 15, fontWeight: "900", marginTop: 2, color: tokens.brand.deep },
  tag: { fontSize: 9, marginTop: 2 },
  footerSpinner: { marginVertical: 16 },
  emptyContainer: { alignItems: "center", paddingTop: 64, paddingHorizontal: 32 },
  emptyTitle: { fontSize: 16, fontWeight: "700", marginTop: 12 },
  emptySubtitle: { fontSize: 13, textAlign: "center", marginTop: 4 },
});
