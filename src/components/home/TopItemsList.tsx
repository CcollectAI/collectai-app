/**
 * Top Movers & Shakers list.
 *
 * Shows the top gainers and losers in the portfolio with trending
 * icons and percentage change. Extracted from app/(tabs)/index.tsx.
 */
import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useAppTheme } from "@/hooks/useAppTheme";
import { radius, text, fontWeight as fw, shadow } from "@/theme/tokens";

// ── Types ──────────────────────────────────────────────────────────────

export type ItemRow = {
  id: string;
  name: string;
  category?: string;
  value: number;
  changePct?: number;
  /** `v_item_values_v1.value_source` — carried so Home can say how much of the
   *  headline rests on a number nobody checked. Undefined = unknown, which the
   *  caller must treat as an estimate rather than as market. */
  valueSource?: string;
};

// ── Props ──────────────────────────────────────────────────────────────

interface TopItemsListProps {
  theme: {
    text: string;
    muted: string;
    card: string;
    border: string;
  };
  items: ItemRow[];
  onItemPress: (item: ItemRow) => void;
  formatPrice: (amount: number) => string;
  hapticsEnabled?: boolean;
}

// ── Helpers ────────────────────────────────────────────────────────────

function formatPct(p?: number): string {
  if (p === undefined || p === null || Number.isNaN(p)) return "—";
  const sign = p > 0 ? "+" : "";
  return `${sign}${(p * 100).toFixed(2)}%`;
}

// ── Component ──────────────────────────────────────────────────────────

function TopItemsListInner({
  theme,
  items,
  onItemPress,
  formatPrice,
  hapticsEnabled = true,
}: TopItemsListProps) {
  const { colors } = useAppTheme();
  const gainers = items
    .filter((it) => (it.changePct ?? 0) > 0)
    .sort((a, b) => (b.changePct ?? 0) - (a.changePct ?? 0))
    .slice(0, 3);

  const losers = items
    .filter((it) => (it.changePct ?? 0) < 0)
    .sort((a, b) => (a.changePct ?? 0) - (b.changePct ?? 0))
    .slice(0, 3);

  // An item whose changePct is 0 or undefined matched NEITHER filter above, so
  // it rendered nowhere. This component is a top-movers widget, but it sits
  // under a heading that says "Collection" — so a user whose items simply have
  // not moved (no price predictions yet, which is every hand-added item) saw an
  // empty Collection on Home while the Items tab listed everything. Reported
  // 2026-07-28 as "the collection on the home tab has no items despite items
  // being added manually".
  //
  // When nothing has moved, fall back to showing the collection itself. Sorted
  // by value like the movers lists, capped the same way.
  const steady =
    gainers.length === 0 && losers.length === 0
      ? [...items].sort((a, b) => b.value - a.value).slice(0, 5)
      : [];

  return (
    <View style={[s.listCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
      {/* Movers (top gainers) */}
      {gainers.map((it, idx) => (
        <AnimatedPressable
          key={it.id}
          style={[
            s.itemRow,
            { borderTopColor: theme.border },
            idx === 0 && s.itemRowFirst,
          ]}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
            onItemPress(it);
          }}
          accessibilityRole="button"
          accessibilityLabel={`${it.name}, ${it.category ?? 'unknown category'}, ${formatPrice(it.value)}, ${formatPct(it.changePct)}`}
        >
          <View style={s.itemLeft}>
            <View style={s.moverLabel}>
              <Ionicons name="trending-up" size={12} color="#10B981" />
              <Text style={[s.itemName, { color: theme.text }]} numberOfLines={1}>
                {it.name}
              </Text>
            </View>
            <Text style={[s.itemCategory, { color: theme.muted }]} numberOfLines={1}>
              {it.category ?? "—"}
            </Text>
          </View>
          <View style={s.itemRight}>
            <Text style={[s.itemValue, { color: theme.text }]}>{formatPrice(it.value)}</Text>
            <Text style={[s.itemPct, { color: "#10B981" }]}>{formatPct(it.changePct)}</Text>
          </View>
        </AnimatedPressable>
      ))}

      {/* Shakers (top losers) */}
      {losers.map((it, idx) => {
        const isFirstInList = idx === 0 && gainers.length === 0;
        return (
          <AnimatedPressable
            key={it.id}
            style={[
              s.itemRow,
              { borderTopColor: theme.border },
              isFirstInList && s.itemRowFirst,
            ]}
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
              onItemPress(it);
            }}
            accessibilityRole="button"
            accessibilityLabel={`${it.name}, ${it.category ?? 'unknown category'}, ${formatPrice(it.value)}, ${formatPct(it.changePct)}`}
          >
            <View style={s.itemLeft}>
              <View style={s.moverLabel}>
                <Ionicons name="trending-down" size={12} color={colors.danger} />
                <Text style={[s.itemName, { color: theme.text }]} numberOfLines={1}>
                  {it.name}
                </Text>
              </View>
              <Text style={[s.itemCategory, { color: theme.muted }]} numberOfLines={1}>
                {it.category ?? "—"}
              </Text>
            </View>
            <View style={s.itemRight}>
              <Text style={[s.itemValue, { color: theme.text }]}>{formatPrice(it.value)}</Text>
              <Text style={[s.itemPct, { color: colors.danger }]}>{formatPct(it.changePct)}</Text>
            </View>
          </AnimatedPressable>
        );
      })}

      {/* Steady holdings — shown only when nothing has moved, so the
          "Collection" heading is never left with an empty card. No trend icon
          or percentage: these items have no movement to report, and inventing
          a 0.0% badge would imply we measured one. */}
      {steady.map((it, idx) => (
        <AnimatedPressable
          key={it.id}
          style={[
            s.itemRow,
            { borderTopColor: theme.border },
            idx === 0 && s.itemRowFirst,
          ]}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
            onItemPress(it);
          }}
          accessibilityRole="button"
          accessibilityLabel={`${it.name}, ${it.category ?? 'unknown category'}, ${formatPrice(it.value)}`}
        >
          <View style={s.itemLeft}>
            <Text style={[s.itemName, { color: theme.text }]} numberOfLines={1}>
              {it.name}
            </Text>
            <Text style={[s.itemCategory, { color: theme.muted }]} numberOfLines={1}>
              {it.category ?? "—"}
            </Text>
          </View>
          <View style={s.itemRight}>
            <Text style={[s.itemValue, { color: theme.text }]}>{formatPrice(it.value)}</Text>
          </View>
        </AnimatedPressable>
      ))}
    </View>
  );
}

export const TopItemsList = React.memo(TopItemsListInner);

// ── Styles ─────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  listCard: {
    borderWidth: 1,
    borderRadius: radius.md,
    overflow: "hidden",
    ...shadow.card,
    marginBottom: 20,
  },
  itemRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderTopWidth: 1,
  },
  itemRowFirst: {
    borderTopWidth: 0,
  },
  itemLeft: {
    flex: 1,
    paddingRight: 12,
  },
  moverLabel: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  itemName: {
    fontWeight: fw.bold,
    fontSize: text.md,
  },
  itemCategory: {
    fontWeight: fw.semibold,
    fontSize: text.sm,
    marginTop: 2,
  },
  itemRight: {
    alignItems: "flex-end",
    minWidth: 90,
  },
  itemValue: {
    fontWeight: fw.extrabold,
    fontSize: text.md,
  },
  itemPct: {
    fontWeight: fw.bold,
    fontSize: text.sm,
    marginTop: 2,
  },
});
