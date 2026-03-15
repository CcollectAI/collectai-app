/**
 * WishlistStatsBar — summary stats for the wishlist (total items, categories, target value).
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { formatPrice } from '@/lib/format';
import { radius, text, fontWeight } from '@/theme/tokens';
import type { WatchlistItem } from '@/data';
import type { CurrencyCode } from '@/data/types';

interface WishlistStatsBarProps {
  items: WatchlistItem[];
  currency: CurrencyCode;
}

export const WishlistStatsBar = React.memo(function WishlistStatsBar({
  items,
  currency,
}: WishlistStatsBarProps) {
  const { colors } = useAppTheme();

  if (items.length === 0) return null;

  const totalItems = items.length;
  const totalTargetValue = items.reduce((sum, i) => sum + (i.targetPrice ?? 0), 0);
  const uniqueCategories = new Set(items.map((i) => i.category).filter(Boolean)).size;
  const highPriority = items.filter((i) => i.priority === 'high').length;

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.stat}>
        <Ionicons name="layers-outline" size={14} color={colors.accent} />
        <Text style={[styles.statValue, { color: colors.text }]}>{totalItems}</Text>
        <Text style={[styles.statLabel, { color: colors.muted }]}>items</Text>
      </View>

      <View style={[styles.divider, { backgroundColor: colors.border }]} />

      <View style={styles.stat}>
        <Ionicons name="grid-outline" size={14} color={colors.accent} />
        <Text style={[styles.statValue, { color: colors.text }]}>{uniqueCategories}</Text>
        <Text style={[styles.statLabel, { color: colors.muted }]}>categories</Text>
      </View>

      <View style={[styles.divider, { backgroundColor: colors.border }]} />

      <View style={styles.stat}>
        <Ionicons name="pricetag-outline" size={14} color={colors.accent} />
        <Text style={[styles.statValue, { color: colors.text }]}>
          {totalTargetValue > 0 ? formatPrice(totalTargetValue, currency) : '\u2014'}
        </Text>
        <Text style={[styles.statLabel, { color: colors.muted }]}>target</Text>
      </View>

      {highPriority > 0 && (
        <>
          <View style={[styles.divider, { backgroundColor: colors.border }]} />
          <View style={styles.stat}>
            <Ionicons name="flame-outline" size={14} color={colors.danger} />
            <Text style={[styles.statValue, { color: colors.text }]}>{highPriority}</Text>
            <Text style={[styles.statLabel, { color: colors.muted }]}>urgent</Text>
          </View>
        </>
      )}
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: radius.md,
    borderWidth: 1,
    marginBottom: 12,
    gap: 8,
  },
  stat: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  statValue: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  statLabel: {
    fontSize: text.sm,
  },
  divider: {
    width: 1,
    height: 16,
  },
});
