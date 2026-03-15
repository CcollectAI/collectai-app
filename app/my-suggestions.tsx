/**
 * My Catalog Suggestions Screen
 *
 * Displays a paginated list of the user's catalog suggestions with status badges.
 * Mapped items can be tapped to navigate to the item detail.
 */
import React, { useState, useCallback, useEffect, useRef } from "react";
import { ScreenErrorBoundary } from "@/components/ScreenErrorBoundary";
import {
  View,
  Text,
  ActivityIndicator,
  StyleSheet,
  RefreshControl,
} from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useRouter, Stack } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { fireHaptic, HapticIntent } from "@/haptics";
import { radius, text as textToken, fontWeight as fw } from "@/theme/tokens";
import { getMyCatalogSuggestions, type MySuggestion } from "@/api/intakeApi";
import { QuickNavBar } from "@/components/QuickNavBar";
import { AnimatedPressable } from "@/motion";
import { logger } from "@/lib/logger";
import { timeAgo } from "@/lib/timeAgo";
import type { Href } from "expo-router";

const PAGE_SIZE = 20;

const STATUS_CONFIG: Record<string, { icon: keyof typeof Ionicons.glyphMap; label: string }> = {
  pending: { icon: "time-outline", label: "Pending" },
  mapped: { icon: "checkmark-circle", label: "Mapped" },
  rejected: { icon: "close-circle", label: "Rejected" },
  new_category: { icon: "sparkles", label: "New Category" },
};

function MySuggestionsContent() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const [suggestions, setSuggestions] = useState<MySuggestion[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const cancelledRef = useRef(false);

  const fetchSuggestions = useCallback(
    async (offset = 0, append = false) => {
      try {
        const data = await getMyCatalogSuggestions({ limit: PAGE_SIZE, offset });
        if (cancelledRef.current) return;
        if (append) {
          setSuggestions((prev) => [...prev, ...data.suggestions]);
        } else {
          setSuggestions(data.suggestions);
        }
        setTotal(data.total);
      } catch (err) {
        logger.warn("[MySuggestions] Failed to fetch suggestions:", err);
      } finally {
        if (!cancelledRef.current) {
          setLoading(false);
          setRefreshing(false);
          setLoadingMore(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    cancelledRef.current = false;
    fetchSuggestions();
    return () => {
      cancelledRef.current = true;
    };
  }, [fetchSuggestions]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    fetchSuggestions(0, false);
  }, [fetchSuggestions]);

  const onEndReached = useCallback(() => {
    if (loadingMore || suggestions.length >= total) return;
    setLoadingMore(true);
    fetchSuggestions(suggestions.length, true);
  }, [loadingMore, suggestions.length, total, fetchSuggestions]);

  const getStatusColor = useCallback(
    (status: string) => {
      switch (status) {
        case "pending":
          return colors.warning;
        case "mapped":
          return colors.success;
        case "rejected":
          return colors.danger;
        case "new_category":
          return colors.info;
        default:
          return colors.muted;
      }
    },
    [colors],
  );

  const handlePress = useCallback(
    (item: MySuggestion) => {
      if (item.status === "mapped" && item.mapped_item_key) {
        fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
        router.push(`/item/${encodeURIComponent(item.mapped_item_key)}` as Href);
      }
    },
    [router],
  );

  const renderItem = useCallback(
    ({ item }: { item: MySuggestion }) => {
      const statusConf = STATUS_CONFIG[item.status] ?? STATUS_CONFIG.pending;
      const statusColor = getStatusColor(item.status);
      const isTappable = item.status === "mapped" && item.mapped_item_key;

      return (
        <AnimatedPressable
          style={[
            styles.card,
            { backgroundColor: colors.card, borderColor: colors.border },
          ]}
          onPress={() => handlePress(item)}
          disabled={!isTappable}
          accessibilityRole={isTappable ? "button" : "text"}
          accessibilityLabel={`Suggestion: ${item.suggested_name}, status: ${statusConf.label}`}
        >
          <View style={styles.cardHeader}>
            <Text
              style={[styles.name, { color: colors.text }]}
              numberOfLines={2}
            >
              {item.suggested_name}
            </Text>
            <View
              style={[styles.badge, { backgroundColor: statusColor + "20" }]}
            >
              <Ionicons name={statusConf.icon} size={14} color={statusColor} />
              <Text style={[styles.badgeText, { color: statusColor }]}>
                {statusConf.label}
              </Text>
            </View>
          </View>

          <View style={styles.meta}>
            <Text style={[styles.metaText, { color: colors.muted }]}>
              via {item.source}
            </Text>
            {item.suggested_category ? (
              <Text style={[styles.metaText, { color: colors.muted }]}>
                {item.suggested_category}
              </Text>
            ) : null}
            <Text style={[styles.metaText, { color: colors.muted }]}>
              {timeAgo(item.created_at)}
            </Text>
          </View>

          {item.status === "mapped" && item.matched_category ? (
            <View style={styles.mappedInfo}>
              <Ionicons
                name="arrow-forward-outline"
                size={14}
                color={colors.success}
              />
              <Text style={[styles.mappedText, { color: colors.success }]}>
                Mapped to {item.matched_category}
                {item.mapped_item_key ? ` — tap to view` : ""}
              </Text>
            </View>
          ) : null}
        </AnimatedPressable>
      );
    },
    [colors, getStatusColor, handlePress],
  );

  const renderEmpty = useCallback(() => {
    if (loading) return null;
    return (
      <View style={styles.empty}>
        <Ionicons name="sparkles-outline" size={48} color={colors.muted} />
        <Text style={[styles.emptyTitle, { color: colors.text }]}>
          No suggestions yet
        </Text>
        <Text style={[styles.emptyBody, { color: colors.muted }]}>
          When you scan or add items we don't recognize, they'll appear here so
          you can track their status.
        </Text>
      </View>
    );
  }, [loading, colors]);

  const renderFooter = useCallback(() => {
    if (!loadingMore) return null;
    return (
      <View style={styles.footer}>
        <ActivityIndicator size="small" color={colors.accent} />
      </View>
    );
  }, [loadingMore, colors]);

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <Stack.Screen
        options={{
          title: "My Suggestions",
          headerBackTitle: "Settings",
        }}
      />

      {loading ? (
        <View style={styles.loader}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
        <FlashList
          data={suggestions}
          renderItem={renderItem}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.accent}
            />
          }
          onEndReached={onEndReached}
          onEndReachedThreshold={0.3}
          ListEmptyComponent={renderEmpty}
          ListFooterComponent={renderFooter}
        />
      )}

      <QuickNavBar />
    </View>
  );
}

export default function MySuggestionsScreen() {
  return (
    <ScreenErrorBoundary screenName="MySuggestions">
      <MySuggestionsContent />
    </ScreenErrorBoundary>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  listContent: {
    padding: 16,
  },
  loader: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  card: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: 14,
    marginBottom: 10,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 8,
  },
  name: {
    flex: 1,
    fontSize: textToken.md,
    fontWeight: fw.semibold,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.pill,
  },
  badgeText: {
    fontSize: textToken.xs,
    fontWeight: fw.semibold,
  },
  meta: {
    flexDirection: "row",
    gap: 12,
    marginTop: 6,
  },
  metaText: {
    fontSize: textToken.sm,
  },
  mappedInfo: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginTop: 8,
  },
  mappedText: {
    fontSize: textToken.sm,
    fontWeight: fw.medium,
  },
  empty: {
    alignItems: "center",
    justifyContent: "center",
    paddingTop: 80,
    paddingHorizontal: 32,
    gap: 12,
  },
  emptyTitle: {
    fontSize: textToken.lg,
    fontWeight: fw.semibold,
  },
  emptyBody: {
    fontSize: textToken.sm,
    textAlign: "center",
    lineHeight: 20,
  },
  footer: {
    paddingVertical: 16,
    alignItems: "center",
  },
});
