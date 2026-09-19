/**
 * WishlistSortControls — action row (alerts pill + add pill) and sort/filter for the wishlist.
 *
 * The CSV export pill was removed 2026-08-09 as unnecessary. It had been
 * recovered here when watchlist-builder was deleted; the collection export on
 * app/(tabs)/items.tsx is unaffected and still server-side via
 * exportItemsOverview().
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { radius, text, fontWeight } from '@/theme/tokens';
import { useTranslation } from 'react-i18next';

interface WishlistSortControlsProps {
  onAddPress: () => void;
}

export const WishlistSortControls = React.memo(function WishlistSortControls({
  onAddPress,
}: WishlistSortControlsProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  /* Sits INSIDE the screen's header row (right of the title) rather than on a
     full-width row of its own. The tab used to stack four separate blocks
     before any content — title row, this action row, a bordered stats card,
     then the Deal Agent banner — which is what read as messy.
     The notifications bell that used to sit here is GONE (2026-09-14): the
     header row now carries the shared HeaderActions cluster, whose bell opens
     the same /notifications, and two bells side by side is the drift that
     component exists to end. */
  return (
    <View style={styles.rightGroup}>
      <AnimatedPressable
        style={[styles.addPill, { backgroundColor: colors.accent }]}
        onPress={onAddPress}
        accessibilityRole="button"
        accessibilityLabel={t('wishlist.add_item_a11y', { defaultValue: 'Add item to watchlist' })}
      >
        <Ionicons name="add" size={18} color={colors.accentText} />
        <Text style={[styles.addPillText, { color: colors.accentText }]}>Add</Text>
      </AnimatedPressable>
    </View>
  );
});

const styles = StyleSheet.create({
  rightGroup: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  addPill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 9,
    borderRadius: radius.pill,
    gap: 6,
  },
  addPillText: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
});
