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
  FlatList,
  Dimensions,
} from "react-native";
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
import { cleanCatalogTitle } from "@/lib/catalogPresentation";
import { formatPrice } from "@/lib/format";
import type { CatalogItemData } from "@/components/CatalogBrowseSection";
import logger from "@/utils/logger";

const PAGE_SIZE = 40;

// Fixed tile geometry so every card occupies the SAME footprint regardless of
// the source image's shape. list padding (10*2) + per-card margin (6*2 each) →
// 44px of fixed horizontal chrome across a 2-column row.
const SCREEN_W = Dimensions.get("window").width;
const CARD_W = (SCREEN_W - 44) / 2;
// Standard trading-card ratio (63×88mm). Art fills the full card height at this
// ratio and uses `contain`, so the WHOLE card shows (portrait, landscape, or
// full-art) — no more cover-cropping the name/HP off the top and bottom.
const CARD_ART_RATIO = 63 / 88;

function CategoryBrowseScreen() {
  const { categoryId, sort: sortParam } = useLocalSearchParams<{ categoryId: string; sort?: string }>();
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
  // The BY SET rail's "See all" deep-links here with ?sort=set.
  const [sort, setSort] = useState<CatalogSortKey>(
    sortParam === "set" || sortParam === "newest" || sortParam === "all" ? sortParam : "value",
  );
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
          <Image source={{ uri: item.image_url }} style={s.art} resizeMode="contain" accessibilityIgnoresInvertColors />
        ) : (
          <View style={[s.art, s.artEmpty, { backgroundColor: tokens.brand.base + "12" }]}>
            <Ionicons name="cube-outline" size={28} color={tokens.brand.base} />
            {/* No catalog art yet — user photos will fill these as the database grows. */}
            <Text style={s.comingSoon}>Image coming soon</Text>
          </View>
        )}
        <View style={s.meta}>
          <Text style={[s.nm, { color: colors.text }]} numberOfLines={2}>{cleanCatalogTitle(item.title, { brand: item.brand, setCode: item.set_code })}</Text>
          {item.estimated_price != null ? (
            <Text style={s.pr}>~{formatPrice(item.estimated_price)}</Text>
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
      <CategorySortChips sort={sort} onChange={handleSortChange} colors={colors} />

      {/* Catalog grid */}
      {loading ? (
        <View style={s.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          numColumns={2}
          columnWrapperStyle={s.column}
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
  // Left-align each row so a lone last card sits in its column instead of
  // stretching to full width (the flex:1 + numColumns odd-item gotcha).
  column: { justifyContent: "flex-start" },
  // Museum card — same visual language as the category rail (mockup `.card`).
  // Fixed width (not flex:1) so every tile is identical and odd counts don't
  // blow up the last card.
  card: {
    width: CARD_W,
    margin: 6,
    borderRadius: 14,
    borderWidth: 1,
    overflow: "hidden",
  },
  // Full card height at the standard card ratio + `contain` (in renderItem) so
  // nothing is cropped. The faint tint fills the letterbox gutters when a
  // non-portrait card doesn't fill the frame.
  art: { width: "100%", aspectRatio: CARD_ART_RATIO, backgroundColor: tokens.brand.base + "0A" },
  artEmpty: { alignItems: "center", justifyContent: "center" },
  comingSoon: { fontSize: 10, fontWeight: "600", marginTop: 6, color: tokens.brand.deep, opacity: 0.7 },
  meta: { paddingVertical: 8, paddingHorizontal: 10 },
  nm: { fontSize: 12, fontWeight: "700" },
  pr: { fontSize: 15, fontWeight: "900", marginTop: 2, color: tokens.brand.deep },
  tag: { fontSize: 9, marginTop: 2 },
  footerSpinner: { marginVertical: 16 },
  emptyContainer: { alignItems: "center", paddingTop: 64, paddingHorizontal: 32 },
  emptyTitle: { fontSize: 16, fontWeight: "700", marginTop: 12 },
  emptySubtitle: { fontSize: 13, textAlign: "center", marginTop: 4 },
});
