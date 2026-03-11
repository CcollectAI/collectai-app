/**
 * WatchlistEmptyState — Shown when the watchlist is empty.
 */
import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";

type ThemeColors = {
  text: string;
  muted: string;
  accent: string;
  brand?: { dark?: string };
};

type Props = {
  colors: ThemeColors;
  onAdd: () => void;
};

export const WatchlistEmptyState = React.memo(function WatchlistEmptyState({
  colors,
  onAdd,
}: Props) {
  return (
    <AnimatedPressable
      style={styles.emptyState}
      onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onAdd(); }}
      accessibilityRole="button"
      accessibilityLabel="Start your watchlist, add your first item"
    >
      <View style={[styles.emptyIconWrap, { backgroundColor: colors.accent + '15' }]}>
        <Ionicons name="eye-outline" size={32} color={colors.accent} />
      </View>
      <Text style={[styles.emptyTitle, { color: colors.text }]}>Start Your Watchlist</Text>
      <Text style={[styles.emptySubtitle, { color: colors.muted }]}>
        Track items you want to buy and set price targets to get notified when
        they hit your budget.
      </Text>
      <View style={[styles.emptyAddBtn, { backgroundColor: colors.accent + '15' }]}>
        <Ionicons name="add" size={18} color={colors.brand?.dark ?? colors.accent} />
        <Text style={[styles.emptyAddText, { color: colors.brand?.dark ?? colors.accent }]}>Add Your First Item</Text>
      </View>
    </AnimatedPressable>
  );
});

const styles = StyleSheet.create({
  emptyState: {
    alignItems: "center",
    paddingVertical: 40,
    paddingHorizontal: 24,
  },
  emptyIconWrap: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: "700",
    marginBottom: 8,
    textAlign: "center",
  },
  emptySubtitle: {
    fontSize: 14,
    textAlign: "center",
    lineHeight: 20,
    marginBottom: 20,
  },
  emptyAddBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 20,
  },
  emptyAddText: {
    fontSize: 14,
    fontWeight: "600",
  },
});
