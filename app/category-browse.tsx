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
  Modal,
  ScrollView,
  useWindowDimensions,
  type ListRenderItemInfo,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
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
import ScreenHeader from "@/components/ScreenHeader";
import { cleanCatalogItem } from "@/lib/catalogPresentation";
import { formatPrice } from "@/lib/format";
import type { CatalogItemData } from "@/components/CatalogBrowseSection";
import logger from "@/utils/logger";

const PAGE_SIZE = 40;

// Match the set-detail grid (app/catalog-set/[setCode].tsx) EXACTLY so "See all"
// and a collection open into the same Instagram-discover-style square image
// grid: 3 columns, a 2px gutter, square tiles that `contain` the card art.
// Tile size is computed via useWindowDimensions() so it tracks rotation /
// split-view instead of freezing at the module-load width.
const NUM_COLS = 3;
const GAP = 2;

function CategoryBrowseScreen() {
  const { categoryId, sort: sortParam } = useLocalSearchParams<{ categoryId: string; sort?: string }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  // Recomputes on rotation / split-view instead of freezing at module load.
  const { width: screenW } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const tile = Math.floor((screenW - GAP * (NUM_COLS - 1)) / NUM_COLS);

  const catMeta = getCategoryById(categoryId as CategoryId);
  const catName = catMeta?.name ?? categoryId ?? "Category";

  // Full-screen swipe viewer — same as the set-detail grid. Tapping a tile
  // opens the viewer at that index so the user can swipe left/right through the
  // whole (paginated) catalog instead of bouncing back to the grid each time.
  const [viewerIndex, setViewerIndex] = useState<number | null>(null);

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
        logger.error("[CategoryBrowse] load error:", err);
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

  const openViewer = useCallback((index: number) => setViewerIndex(index), []);
  const closeViewer = useCallback(() => setViewerIndex(null), []);

  // One full-screen page of the swipe viewer: hero image + title + tags + price,
  // plus a deep-link to the full museum detail (market view + affiliate links).
  const renderViewerPage = useCallback(
    ({ item }: ListRenderItemInfo<CatalogItemData>) => {
      const clean = cleanCatalogItem({
        title: item.title,
        brand: item.brand,
        rarity: item.rarity,
        setCode: item.set_code,
      });
      return (
        <ScrollView
          style={{ width: screenW }}
          contentContainerStyle={[s.viewerPage, { paddingTop: insets.top + 56, paddingBottom: insets.bottom + 32 }]}
          showsVerticalScrollIndicator={false}
        >
          {item.image_url ? (
            <Image source={{ uri: item.image_url }} style={s.viewerHero} resizeMode="contain" accessibilityIgnoresInvertColors />
          ) : (
            <View style={[s.viewerHero, s.placeholder, { backgroundColor: tokens.brand.base + "12" }]}>
              <Ionicons name="cube-outline" size={48} color={tokens.brand.base} />
            </View>
          )}
          <Text style={[s.viewerTitle, { color: colors.text }]}>{clean.title}</Text>
          {clean.tags.length > 0 && (
            <View style={s.badgeRow}>
              {clean.tags.map((b) => (
                <View key={b} style={[s.badge, { backgroundColor: colors.accent + "20" }]}>
                  <Text style={[s.badgeText, { color: tokens.brand.deep }]} numberOfLines={1}>{b}</Text>
                </View>
              ))}
            </View>
          )}
          {item.estimated_price != null && (
            <Text style={[s.viewerPrice, { color: colors.text }]}>~{formatPrice(item.estimated_price)}</Text>
          )}
          <AnimatedPressable
            style={[s.viewerCta, { borderColor: colors.border }]}
            onPress={() => { closeViewer(); openMuseum(item); }}
            accessibilityRole="button"
            accessibilityLabel={`View full details for ${item.title}`}
          >
            <Text style={[s.viewerCtaText, { color: colors.accent }]}>View full details</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.accent} />
          </AnimatedPressable>
        </ScrollView>
      );
    },
    [screenW, insets.top, insets.bottom, colors, closeViewer, openMuseum],
  );

  // Square image tile — identical structure to the set-detail grid so "See all"
  // and a collection look and behave the same. Per-tile art only; tap opens the
  // full-screen swipe viewer (price + details are one more tap away).
  const renderItem = useCallback(
    ({ item, index }: { item: CatalogItemData; index: number }) => (
      <AnimatedPressable
        style={{
          width: tile,
          height: tile,
          marginRight: (index + 1) % NUM_COLS === 0 ? 0 : GAP,
          marginBottom: GAP,
          backgroundColor: colors.card,
        }}
        onPress={() => openViewer(index)}
        accessibilityRole="button"
        accessibilityLabel={`View ${item.title}`}
      >
        {item.image_url ? (
          <Image source={{ uri: item.image_url }} style={s.fill} resizeMode="contain" accessibilityIgnoresInvertColors />
        ) : (
          <View style={[s.fill, s.placeholder, { backgroundColor: tokens.brand.base + "12" }]}>
            <Ionicons name="cube-outline" size={26} color={tokens.brand.base} />
          </View>
        )}
      </AnimatedPressable>
    ),
    [tile, colors.card, openViewer],
  );

  return (
    <View style={[s.container, { backgroundColor: colors.background }]}>
      {/* Native header off — replaced by the flat ScreenHeader below so the
          back/chat/settings icons don't get the iOS 26 glass capsules. */}
      <Stack.Screen options={{ headerShown: false }} />
      <ScreenHeader title={catName} />

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
          // Stable key tied to the column count — RN forbids changing
          // numColumns on a live FlatList; a key makes any change remount it.
          key={`grid-${NUM_COLS}`}
          data={items}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          numColumns={NUM_COLS}
          contentContainerStyle={s.grid}
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

      {/* Full-screen swipe viewer — page left/right through the whole catalog. */}
      {viewerIndex != null && (
        <Modal visible animationType="slide" onRequestClose={closeViewer}>
          <View style={{ flex: 1, backgroundColor: colors.background }}>
            <FlatList
              data={items}
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              initialScrollIndex={viewerIndex}
              getItemLayout={(_, index) => ({ length: screenW, offset: screenW * index, index })}
              keyExtractor={(item) => `v_${item.id}`}
              renderItem={renderViewerPage}
              onEndReached={handleEndReached}
              onEndReachedThreshold={0.5}
              windowSize={3}
              initialNumToRender={1}
              maxToRenderPerBatch={2}
            />
            <AnimatedPressable
              style={[s.viewerClose, {
                // Inside a RN <Modal> useSafeAreaInsets() resolves to 0, so
                // top:insets.top+8 put the arrow at y=8 — UNDER the status bar,
                // invisible (flagged 3×). Floor it so it always clears the status
                // bar. Visible chrome (card bg + border + shadow) so a dark arrow
                // can't vanish on a light card either.
                top: Math.max(insets.top, 44) + 8,
                backgroundColor: colors.card,
                borderColor: colors.border,
              }]}
              onPress={closeViewer}
              accessibilityRole="button"
              accessibilityLabel="Back to grid"
            >
              <Ionicons name="arrow-back" size={24} color={colors.text} />
            </AnimatedPressable>
          </View>
        </Modal>
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
    // Sits just below the in-body ScreenHeader now (no native header to clear).
    marginTop: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
  },
  searchInput: { flex: 1, fontSize: 14, padding: 0 },
  loadingContainer: { flex: 1, alignItems: "center", justifyContent: "center" },
  // Edge-to-edge square grid (mirrors the set-detail grid): tile size + gutters
  // are applied inline in renderItem, so the container just owns the tab-bar
  // bottom clearance.
  // paddingTop keeps the edge-to-edge grid from butting right up against the
  // sort chips (All / Most valuable / …). The tiles have white card backgrounds,
  // so without a clear gap that white field merges into the (also light) chip
  // row and reads as encroaching on the chips.
  grid: { paddingTop: 24, paddingBottom: 96 },
  fill: { width: "100%", height: "100%" },
  placeholder: { alignItems: "center", justifyContent: "center" },
  footerSpinner: { marginVertical: 16 },
  emptyContainer: { alignItems: "center", paddingTop: 64, paddingHorizontal: 32 },
  emptyTitle: { fontSize: 16, fontWeight: "700", marginTop: 12 },
  emptySubtitle: { fontSize: 13, textAlign: "center", marginTop: 4 },
  // Swipe viewer (mirrors app/catalog-set/[setCode].tsx).
  viewerPage: { paddingHorizontal: 20, alignItems: "center" },
  viewerHero: { width: "100%", height: 340, marginBottom: 20 },
  viewerTitle: { fontSize: 22, fontWeight: "800", textAlign: "center" },
  badgeRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center", gap: 6, marginTop: 10 },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  badgeText: { fontSize: 12, fontWeight: "700" },
  viewerPrice: { fontSize: 26, fontWeight: "800", marginTop: 16 },
  viewerCta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginTop: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 22,
    borderWidth: 1,
  },
  viewerCtaText: { fontSize: 14, fontWeight: "700" },
  viewerClose: {
    position: "absolute",
    left: 12,
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 1,
    // Visible chrome (bg/border set inline for theme) + shadow so the back arrow
    // is unmistakable on any card background. bg is transparent-vanish no more.
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
});
