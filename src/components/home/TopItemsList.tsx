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
