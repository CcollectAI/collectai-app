/**
 * ItemsSectionFooter — Category section footer showing collection total.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { formatPrice } from '@/lib/format';

interface ItemsSectionFooterProps {
  total: number;
}

export const ItemsSectionFooter = React.memo(function ItemsSectionFooter({
  total,
}: ItemsSectionFooterProps) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.categoryFooterRow}>
      <View style={{ flex: 1 }} />
      <View style={{ alignItems: 'flex-end' }}>
        <Text style={[styles.categoryTotalLabel, { color: colors.muted }]}>
          Collection total
        </Text>
        <Text style={[styles.categoryTotalValue, { color: colors.text }]}>
          {formatPrice(total)}
        </Text>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  categoryFooterRow: {
    flexDirection: 'row',
    marginTop: 6,
  },
  categoryTotalLabel: {
    fontSize: 11,
    fontWeight: '500',
  },
  categoryTotalValue: {
    fontSize: 13,
    fontWeight: '700',
  },
});
