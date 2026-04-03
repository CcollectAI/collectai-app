/**
 * WatchlistBulkBar — Bulk action bar for multi-select mode (delete, export, cancel).
 */
import React from "react";
import { View, Text, Platform, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { AnimatedPressable } from "@/motion";
import { fireHaptic, HapticIntent } from "@/haptics";

type ThemeColors = {
  text: string;
  card: string;
  border: string;
  accent: string;
  danger: string;
};

type Props = {
  colors: ThemeColors;
  selectedCount: number;
  onBulkDelete: () => void;
  onExportCSV: () => void;
  onCancel: () => void;
};

export const WatchlistBulkBar = React.memo(function WatchlistBulkBar({
  colors,
  selectedCount,
  onBulkDelete,
  onExportCSV,
  onCancel,
}: Props) {
  return (
    <View style={[styles.bulkBar, { backgroundColor: colors.card, borderTopColor: colors.border }]}>
      <AnimatedPressable
        style={[styles.bulkBtn, styles.bulkBtnDelete, { backgroundColor: colors.danger }]}
        onPress={() => { fireHaptic(HapticIntent.ALERT_TRIGGERED); onBulkDelete(); }}
        disabled={selectedCount === 0}
        accessibilityRole="button"
        accessibilityLabel={`Delete ${selectedCount} selected items`}
      >
        <Ionicons name="trash-outline" size={16} color={selectedCount > 0 ? "#FFFFFF" : "#FFFFFF80"} />
        <Text style={[styles.bulkBtnText, { color: selectedCount > 0 ? "#FFFFFF" : "#FFFFFF80" }]}>
          Delete ({selectedCount})
        </Text>
      </AnimatedPressable>

      <AnimatedPressable
        style={[styles.bulkBtn, { backgroundColor: colors.accent }]}
        onPress={onExportCSV}
        accessibilityRole="button"
        accessibilityLabel="Export watchlist as CSV"
      >
        <Ionicons name="download-outline" size={16} color="#FFFFFF" />
        <Text style={styles.bulkBtnText}>Export CSV</Text>
      </AnimatedPressable>

      <AnimatedPressable
        style={[styles.bulkBtn, { backgroundColor: colors.border }]}
        onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onCancel(); }}
        accessibilityRole="button"
        accessibilityLabel="Cancel selection"
      >
        <Text style={[styles.bulkBtnText, { color: colors.text }]}>Cancel</Text>
      </AnimatedPressable>
    </View>
  );
});

const styles = StyleSheet.create({
  bulkBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    paddingBottom: Platform.OS === "ios" ? 28 : 12,
    borderTopWidth: 1,
  },
  bulkBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
  },
  bulkBtnDelete: {},
  bulkBtnText: {
    color: "#FFFFFF", // Button text on brand background
    fontSize: 13,
    fontWeight: "700",
  },
});
