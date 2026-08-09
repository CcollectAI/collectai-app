/**
 * Archived Items Screen — the route back.
 *
 * This screen is not a nice-to-have; it is the precondition for the filter
 * that hides archived items. `listItems` and the portfolio queries started
 * excluding `archived` on 2026-08-09, and archiving is reachable from a SWIPE.
 * Without somewhere to see and restore what you archived, one swipe would put
 * an item beyond reach — over a row that 29 tables still reference and that
 * DELETE would cascade through.
 *
 * Two ways in:
 *   - you archived it yourself (swipe / bulk select on the Items tab)
 *   - a P2P sale completed and settlement retired it (`source = 'marketplace'`)
 *
 * The second is why each row states WHY it left. "Sold on Sparrow" and "You
 * archived this" are different facts, and restoring the first puts back an
 * object somebody else now owns — so it says so rather than offering a bare
 * Restore.
 */
import React, { useState, useCallback, useEffect, useRef } from "react";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import {
  View,
  Text,
  Image,
  ActivityIndicator,
  StyleSheet,
  RefreshControl,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { Stack } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { fireHaptic, HapticIntent } from "@/haptics";
import { radius, text as textToken, fontWeight as fw } from "@/theme/tokens";
import { AnimatedPressable } from "@/motion";
import { dataProvider } from "@/data";
import type { Item } from "@/data/types";
import { logger } from "@/lib/logger";
import { useToast } from "@/components/Toast";

function ArchivedContent() {
  const { colors } = useAppTheme();
  const { showToast } = useToast();
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  // A load FAILURE must not render as "nothing archived". On this screen an
  // empty list is a claim that your items are gone, so the two states are
  // held apart deliberately.
  const [error, setError] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  const fetchArchived = useCallback(async () => {
    try {
      const data = await dataProvider.listArchivedItems();
      if (cancelledRef.current) return;
      setItems(data);
      setError(null);
    } catch (err) {
      if (cancelledRef.current) return;
      logger.error("[Archived] Failed to load archived items:", err);
      setError(
        err instanceof Error ? err.message : "Could not load archived items",
      );
    } finally {
      if (!cancelledRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    cancelledRef.current = false;
    fetchArchived();
    return () => {
      cancelledRef.current = true;
    };
  }, [fetchArchived]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    fetchArchived();
  }, [fetchArchived]);

  const handleRestore = useCallback(
    async (item: Item) => {
      if (restoringId) return;
      setRestoringId(item.id);
      // Optimistic: drop it here, because it is about to belong to the Items
      // tab again. Re-added on failure so a failed restore never looks like it
      // worked (the row leaving is the only signal the user gets).
      const previous = items;
      setItems((prev) => prev.filter((i) => i.id !== item.id));
      try {
        await dataProvider.unarchiveItem(item.id);
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
        showToast({ message: "Restored to your collection", type: "success", duration: 2000 });
      } catch (err) {
        logger.error("[Archived] Restore failed:", err);
        setItems(previous);
        showToast({ message: "Could not restore that item", type: "error", duration: 3000 });
      } finally {
        setRestoringId(null);
      }
    },
    [items, restoringId, showToast],
  );

  const renderItem = useCallback(
    ({ item }: { item: Item }) => {
      // `source === 'marketplace'` is written by _settle_completed_trade on the
      // BUYER's new row; the seller's retired row keeps its original source.
      // What marks a sale on this screen is the item having left via a trade,
      // so we surface the distinction rather than implying every archived item
      // was tidied away by hand.
      const soldOnSparrow = item.source === "marketplace";
      const busy = restoringId === item.id;

      return (
        <View
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
        >
          {item.imageUrl ? (
            <Image source={{ uri: item.imageUrl }} style={styles.thumb} />
          ) : (
            <View style={[styles.thumb, styles.thumbEmpty, { backgroundColor: colors.background }]}>
              <Ionicons name="image-outline" size={20} color={colors.muted} />
            </View>
          )}

          <View style={styles.cardBody}>
            <Text style={[styles.title, { color: colors.text }]} numberOfLines={2}>
              {item.name || "Untitled"}
            </Text>
            <Text style={[styles.meta, { color: colors.muted }]} numberOfLines={1}>
              {soldOnSparrow ? "Sold on Sparrow" : "You archived this"}
              {item.category ? ` · ${item.category}` : ""}
            </Text>
          </View>

          <AnimatedPressable
            onPress={() => handleRestore(item)}
            disabled={busy}
            style={[styles.restoreBtn, { borderColor: colors.border }]}
            accessibilityRole="button"
            accessibilityLabel={`Restore ${item.name || "item"} to your collection`}
          >
            {busy ? (
              <ActivityIndicator size="small" color={colors.accent} />
            ) : (
              <Text style={[styles.restoreText, { color: colors.accent }]}>Restore</Text>
            )}
          </AnimatedPressable>
        </View>
      );
    },
    [colors, handleRestore, restoringId],
  );

  const renderEmpty = useCallback(() => {
    if (loading) return null;
    if (error) {
      return (
        <View style={styles.empty}>
          <Ionicons name="alert-circle-outline" size={48} color={colors.danger} />
          <Text style={[styles.emptyTitle, { color: colors.text }]}>
            Could not load your archive
          </Text>
          <Text style={[styles.emptyBody, { color: colors.muted }]}>
            {error} Pull down to try again — nothing has been deleted.
          </Text>
        </View>
      );
    }
    return (
      <View style={styles.empty}>
        <Ionicons name="archive-outline" size={48} color={colors.muted} />
        <Text style={[styles.emptyTitle, { color: colors.text }]}>
          Nothing archived
        </Text>
        <Text style={[styles.emptyBody, { color: colors.muted }]}>
          Items you archive, and items that leave your collection when a sale
          completes, appear here. You can put any of them back.
        </Text>
      </View>
    );
  }, [loading, error, colors]);

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerTitle: "Archived", headerBackTitle: "Items" }} />

      {loading ? (
        <View style={styles.loader}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
        <FlashList
          data={items}
          renderItem={renderItem}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          ListEmptyComponent={renderEmpty}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.accent}
            />
          }
        />
      )}
    </View>
  );
}

export default function ArchivedScreen() {
  return (
    <ScreenErrorBoundary screenName="Archived">
      <ArchivedContent />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  loader: { flex: 1, alignItems: "center", justifyContent: "center" },
  listContent: { padding: 16, paddingBottom: 32 },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    padding: 12,
    marginBottom: 10,
  },
  thumb: { width: 44, height: 44, borderRadius: radius.sm },
  thumbEmpty: { alignItems: "center", justifyContent: "center" },
  cardBody: { flex: 1, gap: 2 },
  title: { fontSize: textToken.md, fontWeight: fw.semibold },
  meta: { fontSize: textToken.sm },
  restoreBtn: {
    minWidth: 76,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  restoreText: { fontSize: textToken.sm, fontWeight: fw.semibold },
  empty: {
    alignItems: "center",
    justifyContent: "center",
    paddingTop: 80,
    paddingHorizontal: 32,
    gap: 12,
  },
  emptyTitle: { fontSize: textToken.lg, fontWeight: fw.semibold },
  emptyBody: { fontSize: textToken.sm, textAlign: "center", lineHeight: 20 },
});
