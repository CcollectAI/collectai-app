/**
 * WatchlistStatsBanner — Displays total items, high-priority count, and items with targets.
 */
import React from "react";
import { View, Text, StyleSheet } from "react-native";

type ThemeColors = {
  text: string;
  muted: string;
  card: string;
  border: string;
};

type WatchlistStats = {
  total: number;
  high: number;
  withTarget: number;
};

type Props = {
  stats: WatchlistStats;
  colors: ThemeColors;
};

export const WatchlistStatsBanner = React.memo(function WatchlistStatsBanner({
  stats,
  colors,
}: Props) {
  return (
    <View style={[styles.statsBanner, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.statItem} accessibilityLabel={`${stats.total} items`}>
        <Text style={[styles.statValue, { color: colors.text }]}>{stats.total}</Text>
        <Text style={[styles.statLabel, { color: colors.muted }]}>Items</Text>
      </View>
      <View style={[styles.statDivider, { backgroundColor: colors.border }]} />
      <View style={styles.statItem} accessibilityLabel={`${stats.high} high priority`}>
        <Text style={[styles.statValue, { color: colors.text }]}>{stats.high}</Text>
        <Text style={[styles.statLabel, { color: colors.muted }]}>High Priority</Text>
      </View>
      <View style={[styles.statDivider, { backgroundColor: colors.border }]} />
      <View style={styles.statItem} accessibilityLabel={`${stats.withTarget} with targets`}>
        <Text style={[styles.statValue, { color: colors.text }]}>{stats.withTarget}</Text>
        <Text style={[styles.statLabel, { color: colors.muted }]}>With Targets</Text>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  statsBanner: {
    flexDirection: "row",
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  statItem: {
    flex: 1,
    alignItems: "center",
  },
  statValue: {
    fontSize: 24,
    fontWeight: "800",
  },
  statLabel: {
    fontSize: 11,
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    alignSelf: "stretch",
    marginHorizontal: 8,
  },
});
