/**
 * Catalog Set — the grouped-set "museum" behind a Featured Collections / BY SET
 * tile. A set (category_items.set_code, e.g. taylor_swift → "eras-tour") opens
 * here as an Instagram-discover-style square image grid of every item in the
 * set; tapping a tile opens that item's museum detail.
 *
 * Server-side: GET /catalog/{category}/items?set_code=… (paged).
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  Image,
  StyleSheet,
  ActivityIndicator,
  Modal,
  ScrollView,
  useWindowDimensions,
  type ListRenderItemInfo,
} from "react-native";
import { FlatList } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter, Stack, type Href } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import { browseCatalogItems } from "@/api/intakeApi";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import { colors as tokens } from "@/theme/tokens";
import { cleanCatalogItem } from "@/lib/catalogPresentation";
import { formatPrice } from "@/lib/format";
import type { CatalogItemData } from "@/components/CatalogBrowseSection";
import logger from "@/utils/logger";
import { logAuthState, logLoad, startTimer } from "@/utils/diagnostics";

const PAGE_SIZE = 60;
const NUM_COLS = 3;
const GAP = 2;

function CatalogSetScreen() {
  const { setCode, category, name, dimension } = useLocalSearchParams<{
    setCode: string;
    category: string;
    name?: string;
    dimension?: 'set' | 'brand';
  }>();
  const router = useRouter();
  const { colors } = useAppTheme();
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const tile = Math.floor((width - GAP * (NUM_COLS - 1)) / NUM_COLS);

  // Full-screen swipe viewer: index of the item currently open (null = closed).
  // Tapping a grid tile opens the viewer here so the user can swipe left/right
  // through every item in the set without bouncing back to the grid.
  const [viewerIndex, setViewerIndex] = useState<number | null>(null);

  const [items, setItems] = useState<CatalogItemData[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const reqId = useRef(0);

  const fetchPage = useCallback(
    async (offset: number, mode: "replace" | "append") => {
      if (!category || !setCode) return;
      const id = ++reqId.current;
      const elapsed = startTimer();
      // DIAG: on the initial load, snapshot auth — the recurring "spins forever"
      // reports line up with getSession() stalling before the request even fires.
      if (mode === "replace") void logAuthState(`set-grid:${category}/${setCode}`);
      try {
        // `setCode` carries the collection_key — a brand value for brand-grouped
        // categories (watches), a set_code otherwise. Filter by the right field.
        const res = await browseCatalogItems(category, {
          ...(dimension === "brand" ? { brand: setCode } : { setCode }),
          limit: PAGE_SIZE,
          offset,
          // NOTE: sort:"value" filters to priced-only on the BE, which returns
          // ZERO items for sets whose cards have no market comp (e.g. most MTG
          // sets — MKM has 265 items, 0 priced → empty grid). This screen's job
          // is to show EVERY item in the set, so use set order instead.
          sort: "set",
        });
        if (id !== reqId.current) return;
        const page = (res?.items ?? []) as CatalogItemData[];
        setItems((prev) => (mode === "append" ? [...prev, ...page] : page));
        if (typeof res?.total === "number") setTotal(res.total);
        logLoad(`set-grid:${category}/${setCode}`, {
          dimension: dimension ?? "set",
          mode,
          offset,
          got: page.length,
          total: res?.total ?? "?",
          ms: elapsed(),
        });
      } catch (err) {
        logLoad(`set-grid:${category}/${setCode}`, {
          error: err instanceof Error ? err.message : String(err),
          ms: elapsed(),
        });
        logger.warn("[CatalogSet] load error:", err);
        if (mode === "replace" && id === reqId.current) setItems([]);
      } finally {
        if (id === reqId.current) {
          setLoading(false);
          setLoadingMore(false);
        }
      }
    },
    [category, setCode, dimension],
  );

  useEffect(() => {
    setLoading(true);
    fetchPage(0, "replace");
  }, [fetchPage]);

  const handleEndReached = useCallback(() => {
    if (loading || loadingMore) return;
    if (total != null && items.length >= total) return;
    setLoadingMore(true);
    fetchPage(items.length, "append");
  }, [loading, loadingMore, total, items.length, fetchPage]);

  const openItem = useCallback(
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
  // with a deep-link to the full museum detail for the richer market view.
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
          style={{ width }}
          contentContainerStyle={[styles.viewerPage, { paddingTop: insets.top + 56, paddingBottom: insets.bottom + 32 }]}
          showsVerticalScrollIndicator={false}
        >
          {item.image_url ? (
            <Image source={{ uri: item.image_url }} style={styles.viewerHero} resizeMode="contain" accessibilityIgnoresInvertColors />
          ) : (
            <View style={[styles.viewerHero, styles.placeholder, { backgroundColor: tokens.brand.base + "12" }]}>
              <Ionicons name="cube-outline" size={48} color={tokens.brand.base} />
            </View>
          )}
          <Text style={[styles.viewerTitle, { color: colors.text }]}>{clean.title}</Text>
          {clean.tags.length > 0 && (
            <View style={styles.badgeRow}>
              {clean.tags.map((b) => (
                <View key={b} style={[styles.badge, { backgroundColor: colors.accent + "20" }]}>
                  <Text style={[styles.badgeText, { color: tokens.brand.deep }]} numberOfLines={1}>{b}</Text>
                </View>
              ))}
            </View>
          )}
          {item.estimated_price != null && (
            <Text style={[styles.viewerPrice, { color: colors.text }]}>~{formatPrice(item.estimated_price)}</Text>
          )}
          <AnimatedPressable
            style={[styles.viewerCta, { borderColor: colors.border }]}
            onPress={() => { closeViewer(); openItem(item); }}
            accessibilityRole="button"
            accessibilityLabel={`View full details for ${item.title}`}
          >
            <Text style={[styles.viewerCtaText, { color: colors.accent }]}>View full details</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.accent} />
          </AnimatedPressable>
        </ScrollView>
      );
    },
    [width, insets.top, insets.bottom, colors, closeViewer, openItem],
  );

  const renderItem = useCallback(
    ({ item, index }: ListRenderItemInfo<CatalogItemData>) => (
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
          <Image
            source={{ uri: item.image_url }}
            style={styles.fill}
            resizeMode="contain"
            accessibilityIgnoresInvertColors
          />
        ) : (
          <View style={[styles.fill, styles.placeholder, { backgroundColor: tokens.brand.base + "12" }]}>
            <Ionicons name="cube-outline" size={26} color={tokens.brand.base} />
          </View>
        )}
      </AnimatedPressable>
    ),
    [tile, colors.card, openViewer],
  );

  const setName = name || "Set";

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Stack.Screen
        options={{
          title: setName,
          headerTintColor: colors.text,
          headerStyle: { backgroundColor: colors.background },
        }}
      />

      {/* Set header */}
      <View style={styles.header}>
        <Text style={[styles.setTitle, { color: colors.text }]} numberOfLines={2}>{setName}</Text>
        <Text style={[styles.setMeta, { color: colors.muted }]}>
          {total != null ? `${total} ${total === 1 ? "item" : "items"}` : "Collection"}
        </Text>
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          numColumns={NUM_COLS}
          onEndReached={handleEndReached}
          onEndReachedThreshold={0.5}
          contentContainerStyle={styles.grid}
          ListFooterComponent={
            loadingMore ? <ActivityIndicator color={colors.accent} style={styles.footer} /> : null
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="albums-outline" size={48} color={colors.muted} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>This set is empty</Text>
              <Text style={[styles.emptySub, { color: colors.muted }]}>Items are still being curated</Text>
            </View>
          }
        />
      )}

      {/* Full-screen swipe viewer — page left/right through the whole set. */}
      {viewerIndex != null && (
        <Modal visible animationType="slide" onRequestClose={closeViewer}>
          <View style={{ flex: 1, backgroundColor: colors.background }}>
            <FlatList
              data={items}
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              initialScrollIndex={viewerIndex}
              getItemLayout={(_, index) => ({ length: width, offset: width * index, index })}
              keyExtractor={(item) => `v_${item.id}`}
              renderItem={renderViewerPage}
              onEndReached={handleEndReached}
              onEndReachedThreshold={0.5}
              windowSize={3}
              initialNumToRender={1}
              maxToRenderPerBatch={2}
            />
            <AnimatedPressable
              style={[styles.viewerClose, { top: insets.top + 8, backgroundColor: colors.card, borderColor: colors.border }]}
              onPress={closeViewer}
              accessibilityRole="button"
              accessibilityLabel="Close"
            >
              <Ionicons name="close" size={24} color={colors.text} />
            </AnimatedPressable>
          </View>
        </Modal>
      )}
    </View>
  );
}

export default function CatalogSetScreenWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Catalog Set">
      <CatalogSetScreen />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 10 },
  setTitle: { fontSize: 22, fontWeight: "800" },
  setMeta: { fontSize: 13, marginTop: 2 },
  grid: { paddingBottom: 96 },
  fill: { width: "100%", height: "100%" },
  placeholder: { alignItems: "center", justifyContent: "center" },
  loadingContainer: { flex: 1, alignItems: "center", justifyContent: "center" },
  footer: { marginVertical: 16 },
  empty: { alignItems: "center", paddingTop: 64, paddingHorizontal: 32 },
  emptyTitle: { fontSize: 16, fontWeight: "700", marginTop: 12 },
  emptySub: { fontSize: 13, textAlign: "center", marginTop: 4 },
  // Swipe viewer
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
    left: 16,
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
});
