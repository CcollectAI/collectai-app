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
  useWindowDimensions,
  type ListRenderItemInfo,
} from "react-native";
import { FlatList } from "react-native";
import { useLocalSearchParams, useRouter, Stack, type Href } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import { browseCatalogItems } from "@/api/intakeApi";
import { useAppTheme } from "@/hooks/useAppTheme";
import { AnimatedPressable } from "@/motion";
import { colors as tokens } from "@/theme/tokens";
import type { CatalogItemData } from "@/components/CatalogBrowseSection";
import logger from "@/utils/logger";

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
  const tile = Math.floor((width - GAP * (NUM_COLS - 1)) / NUM_COLS);

  const [items, setItems] = useState<CatalogItemData[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const reqId = useRef(0);

  const fetchPage = useCallback(
    async (offset: number, mode: "replace" | "append") => {
      if (!category || !setCode) return;
      const id = ++reqId.current;
      try {
        // `setCode` carries the collection_key — a brand value for brand-grouped
        // categories (watches), a set_code otherwise. Filter by the right field.
        const res = await browseCatalogItems(category, {
          ...(dimension === "brand" ? { brand: setCode } : { setCode }),
          limit: PAGE_SIZE,
          offset,
          sort: "value", // priced/known items lead — the "what people know" feed
        });
        if (id !== reqId.current) return;
        const page = (res?.items ?? []) as CatalogItemData[];
        setItems((prev) => (mode === "append" ? [...prev, ...page] : page));
        if (typeof res?.total === "number") setTotal(res.total);
      } catch (err) {
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
        onPress={() => openItem(item)}
        accessibilityRole="button"
        accessibilityLabel={`View ${item.title}`}
      >
        {item.image_url ? (
          <Image
            source={{ uri: item.image_url }}
            style={styles.fill}
            resizeMode="cover"
            accessibilityIgnoresInvertColors
          />
        ) : (
          <View style={[styles.fill, styles.placeholder, { backgroundColor: tokens.brand.base + "12" }]}>
            <Ionicons name="cube-outline" size={26} color={tokens.brand.base} />
          </View>
        )}
      </AnimatedPressable>
    ),
    [tile, colors.card, openItem],
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
});
