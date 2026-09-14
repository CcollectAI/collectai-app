/**
 * ItemsSectionFooter — Category section footer showing the section's total.
 *
 * Renders nothing for a one-item section: its total IS that item's price, which
 * the row directly above already shows (walked on Android 2026-09-14 — three of
 * four sections printed their only item's price a second time). A grouped list
 * should not repeat what a member row already says (docs/ui-playbook.md).
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { formatPrice } from '@/lib/format';
import { useTranslation } from 'react-i18next';

interface ItemsSectionFooterProps {
  total: number;
  /** Items in the section. */
  count: number;
}

export const ItemsSectionFooter = React.memo(function ItemsSectionFooter({
  total,
  count,
}: ItemsSectionFooterProps) {
  const { colors } = useAppTheme();
  const { t } = useTranslation();

  if (count < 2) return null;

  return (
    <View style={styles.categoryFooterRow}>
      <View style={{ flex: 1 }} />
      <View style={{ alignItems: 'flex-end' }}>
        <Text style={[styles.categoryTotalLabel, { color: colors.muted }]}>
          {t('items.section_total', { defaultValue: 'Total' })}
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
