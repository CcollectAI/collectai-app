/**
 * Empty/no-results state for the Marketplace screen.
 *
 * Extracted from app/(tabs)/marketplace.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';

export const MarketplaceEmptyState = React.memo(function MarketplaceEmptyState() {
  const { colors } = useAppTheme();

  return (
    <View style={styles.noResultsBlock}>
      <Ionicons name="search-outline" size={32} color={colors.muted} style={{ marginBottom: 8 }} />
      <Text style={[styles.noResultsTitle, { color: colors.text }]}>
        No results found
      </Text>
      <Text style={[styles.emptyText, { color: colors.muted }]}>
        Try a different search term or browse by category below.
      </Text>
    </View>
  );
});

const styles = StyleSheet.create({
  noResultsBlock: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  noResultsTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  emptyText: {
    fontSize: 13,
    marginTop: 4,
    textAlign: 'center',
  },
});
