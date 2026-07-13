/**
 * Page header for the Marketplace screen showing title, subtitle, and action icons.
 *
 * Extracted from app/(tabs)/marketplace.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { InboxHeaderButton } from '@/components/InboxHeaderButton';

export const MarketplacePageHeader = React.memo(function MarketplacePageHeader() {
  const { colors } = useAppTheme();

  return (
    <View style={styles.headerRow}>
      <View style={styles.headerLeft}>
        <Text style={[styles.headerTitle, { color: colors.text }]}>
          Search
        </Text>
        <Text style={[styles.headerSubtitle, { color: colors.muted }]}>
          Find items, collections, and categories.
        </Text>
      </View>
      <View style={styles.headerIcons}>
        <InboxHeaderButton color={colors.text} size={22} />
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  headerLeft: {
    flex: 1,
  },
  headerTitle: {
    fontSize: 22,
    fontWeight: '700',
  },
  headerSubtitle: {
    fontSize: 12,
    marginTop: 4,
  },
  headerIcons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
});
