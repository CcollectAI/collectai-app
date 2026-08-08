/**
 * WishlistSortControls — action row (alerts pill + add pill) and sort/filter for the wishlist.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { radius, text, fontWeight } from '@/theme/tokens';

interface WishlistSortControlsProps {
  onAlertsPress: () => void;
  onAddPress: () => void;
  /** CSV export. Recovered onto this screen when watchlist-builder was deleted —
   *  the screen was redundant, the export was not. */
  onExportPress: () => void;
}

export const WishlistSortControls = React.memo(function WishlistSortControls({
  onAlertsPress,
  onAddPress,
  onExportPress,
}: WishlistSortControlsProps) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.actionRow}>
      <AnimatedPressable
        style={[styles.alertsPill, { backgroundColor: colors.card, borderColor: colors.border }]}
        onPress={onAlertsPress}
        accessibilityRole="button"
        accessibilityLabel="Open your notifications"
      >
        <Ionicons name="notifications-outline" size={16} color={colors.accent} />
        <Text style={[styles.alertsPillText, { color: colors.accent }]}>Inbox</Text>
      </AnimatedPressable>

      <View style={styles.rightGroup}>
        {/* Icon-only: export is a power action, and a third worded pill would
            crowd the row the Bulk pill was removed from. */}
        <AnimatedPressable
          style={[styles.exportPill, { backgroundColor: colors.card, borderColor: colors.border }]}
          onPress={onExportPress}
          accessibilityRole="button"
          accessibilityLabel="Export your watchlist as a CSV file"
        >
          <Ionicons name="download-outline" size={17} color={colors.accent} />
        </AnimatedPressable>

        <AnimatedPressable
          style={[styles.addPill, { backgroundColor: colors.accent }]}
          onPress={onAddPress}
          accessibilityRole="button"
          accessibilityLabel="Add item to watchlist"
        >
          <Ionicons name="add" size={18} color={colors.accentText} />
          <Text style={[styles.addPillText, { color: colors.accentText }]}>Add</Text>
        </AnimatedPressable>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  actionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  rightGroup: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  exportPill: {
    alignItems: 'center', justifyContent: 'center',
    width: 42, height: 42, borderRadius: radius.pill,
    borderWidth: StyleSheet.hairlineWidth,
  },
  alertsPill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: radius.pill,
    borderWidth: 1,
    gap: 6,
  },
  alertsPillText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  addPill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: radius.pill,
    gap: 6,
  },
  addPillText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
});
