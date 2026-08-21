/**
 * Header row for the Items screen showing title, portfolio total, and action icons.
 *
 * Extracted from app/(tabs)/items.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { TabBackButton } from '@/components/TabBackButton';
import { HeaderActions } from '@/components/HeaderActions';
import { formatPrice } from '@/lib/format';

interface ItemsGridHeaderProps {
  portfolioTotal: number;
}

export const ItemsGridHeader = React.memo(function ItemsGridHeader({
  portfolioTotal,
}: ItemsGridHeaderProps) {
  const { colors } = useAppTheme();

  return (
    <View style={styles.headerRow}>
      <TabBackButton />
      <View style={styles.headerLeft}>
        <Text style={[styles.title, { color: colors.text }]}>Items</Text>
        <Text style={[styles.subtitle, { color: colors.muted }]}>
          Portfolio total: {formatPrice(portfolioTotal)}
        </Text>
      </View>
      {/* The one cluster — notifications, messages, settings. This comment used
          to say "the chat icon may hide itself when community is gated"; that
          reuse is gone (MESSAGING_ENABLED), so the row no longer changes shape
          from screen to screen. */}
      <HeaderActions />
    </View>
  );
});

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  headerLeft: {
    flex: 1,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
  },
  subtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  headerIcons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  iconBtn: { padding: 4 },
});
