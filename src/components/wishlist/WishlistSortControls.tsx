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
}

export const WishlistSortControls = React.memo(function WishlistSortControls({
  onAlertsPress,
  onAddPress,
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
