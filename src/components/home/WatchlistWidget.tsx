/**
 * Watchlist summary widget.
 *
 * Shows a compact list of watchlist items with notification bell,
 * target price, and a "See all" link. Extracted from app/(tabs)/index.tsx.
 */
import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import type { WatchlistItem } from "@/data/types";

// ── Props ──────────────────────────────────────────────────────────────

interface WatchlistWidgetProps {
  theme: {
    text: string;
    muted: string;
    card: string;
    border: string;
    accent: string;
  };
  watchlistItems: WatchlistItem[];
  onItemPress: (item: WatchlistItem) => void;
  onViewAll: () => void;
  formatPrice: (amount: number) => string;
  hapticsEnabled?: boolean;
}

// ── Component ──────────────────────────────────────────────────────────

function WatchlistWidgetInner({
  theme,
  watchlistItems,
  onItemPress,
  onViewAll,
  formatPrice,
  hapticsEnabled = true,
}: WatchlistWidgetProps) {
  if (watchlistItems.length === 0) return null;

  return (
    <>
      <View style={s.sectionHeader}>
        <Text style={[s.sectionTitle, { color: theme.text }]}>Watchlist</Text>
        <AnimatedPressable
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
            onViewAll();
          }}
          accessibilityRole="link"
          accessibilityLabel="See all watchlist items"
        >
          <Text style={[s.seeAllLink, { color: theme.accent }]}>{"See all \u2192"}</Text>
        </AnimatedPressable>
      </View>

      <View style={[s.listCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
        {watchlistItems.map((it, idx) => {
          const hasAlert = Boolean(it.targetPrice);

          return (
            <AnimatedPressable
              key={it.id}
              style={[
                s.watchlistRow,
                { borderTopColor: theme.border },
                idx === 0 && s.itemRowFirst,
              ]}
              onPress={() => {
                fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
                onItemPress(it);
              }}
              accessibilityRole="button"
              accessibilityLabel={`Watchlist item: ${it.title}`}
            >
              <View style={s.watchlistLeft}>
                <View style={s.watchlistNameRow}>
                  <Ionicons
                    name={hasAlert ? "notifications" : "notifications-outline"}
                    size={16}
                    color={hasAlert ? theme.accent : theme.muted}
                    style={s.bellIcon}
                  />
                  <Text style={[s.itemName, { color: theme.text }]} numberOfLines={1}>
                    {it.title ?? "Watchlist Item"}
                  </Text>
                </View>
                <Text style={[s.itemCategory, { color: theme.muted }]} numberOfLines={1}>
                  {it.category ?? "—"}
                </Text>
              </View>
              <View style={s.watchlistRight}>
                {it.targetPrice != null ? (
                  <>
                    <Ionicons name="flag-outline" size={12} color={theme.accent} style={s.targetIcon} />
                    <Text style={[s.targetPrice, { color: theme.accent }]}>
                      {formatPrice(it.targetPrice)}
                    </Text>
                  </>
                ) : (
                  <Text style={[s.noTarget, { color: theme.muted }]}>No target</Text>
                )}
              </View>
            </AnimatedPressable>
          );
        })}
      </View>
    </>
  );
}

export const WatchlistWidget = React.memo(WatchlistWidgetInner);

// ── Styles ─────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
  },
  seeAllLink: {
    fontSize: 13,
    fontWeight: "600",
  },
  listCard: {
    borderWidth: 1,
    borderRadius: 12,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
    marginBottom: 20,
  },
  watchlistRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderTopWidth: 1,
  },
  itemRowFirst: {
    borderTopWidth: 0,
  },
  watchlistLeft: {
    flex: 1,
    paddingRight: 12,
  },
  watchlistNameRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  bellIcon: {
    marginRight: 6,
  },
  itemName: {
    fontWeight: "700",
    fontSize: 14,
  },
  itemCategory: {
    fontWeight: "600",
    fontSize: 12,
    marginTop: 2,
  },
  watchlistRight: {
    flexDirection: "row",
    alignItems: "center",
    minWidth: 80,
    justifyContent: "flex-end",
  },
  targetIcon: {
    marginRight: 4,
  },
  targetPrice: {
    fontWeight: "700",
    fontSize: 13,
  },
  noTarget: {
    fontWeight: "500",
    fontSize: 12,
    fontStyle: "italic",
  },
});
