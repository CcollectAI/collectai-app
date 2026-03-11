/**
 * Active-filter summary row showing filter chips and a clear button.
 *
 * Extracted from app/(tabs)/items.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';

interface ItemsFilterSummaryProps {
  categoryParam?: string;
  collectionParam?: string;
  filterCategory: string | null;
  query: string;
  filteredItemCount: number;
  onClearFilters: () => void;
}

export const ItemsFilterSummary = React.memo(function ItemsFilterSummary({
  categoryParam,
  collectionParam,
  filterCategory,
  query,
  filteredItemCount,
  onClearFilters,
}: ItemsFilterSummaryProps) {
  const { colors } = useAppTheme();

  const hasAnyFilter =
    !!categoryParam ||
    !!collectionParam ||
    !!filterCategory ||
    query.trim().length > 0;

  return (
    <>
      {hasAnyFilter && (
        <View style={styles.filterSummaryRow}>
          <Text style={[styles.filterSummaryText, { color: colors.muted }]}>
            Filtered by:
          </Text>
          <View style={styles.filterChipsRow}>
            {categoryParam && (
              <View style={[styles.filterChip, { borderColor: colors.border, backgroundColor: colors.accent + '15' }]}>
                <Text style={[styles.filterChipText, { color: colors.text }]}>
                  Category: {categoryParam}
                </Text>
              </View>
            )}
            {collectionParam && (
              <View style={[styles.filterChip, { borderColor: colors.border, backgroundColor: colors.accent + '15' }]}>
                <Text style={[styles.filterChipText, { color: colors.text }]}>
                  Collection: {collectionParam}
                </Text>
              </View>
            )}
            {filterCategory && !categoryParam && (
              <View style={[styles.filterChip, { borderColor: colors.border, backgroundColor: colors.accent + '15' }]}>
                <Text style={[styles.filterChipText, { color: colors.text }]}>
                  Category: {filterCategory}
                </Text>
              </View>
            )}
            {query.trim().length > 0 && (
              <View style={[styles.filterChip, { borderColor: colors.border, backgroundColor: colors.accent + '15' }]}>
                <Text style={[styles.filterChipText, { color: colors.text }]}>
                  Search: &quot;{query.trim()}&quot;
                </Text>
              </View>
            )}
          </View>
          <AnimatedPressable
            onPress={onClearFilters}
            style={styles.filterClearButton}
            accessibilityRole="button"
            accessibilityLabel="Clear all filters"
          >
            <Text style={[styles.filterClearText, { color: colors.muted }]}>
              Clear
            </Text>
          </AnimatedPressable>
        </View>
      )}

      <Text style={[styles.itemCount, { color: colors.muted }]}>
        {filteredItemCount} item{filteredItemCount !== 1 ? 's' : ''}
      </Text>
    </>
  );
});

const styles = StyleSheet.create({
  filterSummaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 4,
    marginBottom: 6,
  },
  filterSummaryText: {
    fontSize: 11,
    fontWeight: '500',
  },
  filterChipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
    flex: 1,
    paddingHorizontal: 4,
  },
  filterChip: {
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderWidth: StyleSheet.hairlineWidth,
  },
  filterChipText: {
    fontSize: 10,
  },
  filterClearButton: {
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  filterClearText: {
    fontSize: 11,
    textDecorationLine: 'underline',
  },
  itemCount: {
    fontSize: 13,
    fontWeight: '500',
    paddingHorizontal: 16,
    paddingVertical: 4,
  },
});
