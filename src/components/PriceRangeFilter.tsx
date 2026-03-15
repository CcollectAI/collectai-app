/**
 * PriceRangeFilter — Min/max price input sub-section for FilterSheet.
 *
 * Extracted from FilterSheet.tsx to reduce file size.
 */
import React from 'react';
import { View, Text, TextInput, StyleSheet } from 'react-native';

interface PriceRangeFilterProps {
  priceMin: number | null;
  priceMax: number | null;
  onPriceChange: (field: 'priceMin' | 'priceMax', value: string) => void;
  colors: {
    text: string;
    muted: string;
    border: string;
  };
}

function PriceRangeFilterInner({
  priceMin,
  priceMax,
  onPriceChange,
  colors,
}: PriceRangeFilterProps) {
  return (
    <View style={styles.priceInputRow}>
      <View style={styles.priceInputWrapper}>
        <Text style={[styles.priceLabel, { color: colors.muted }]}>Min</Text>
        <TextInput
          style={[
            styles.priceInput,
            { borderColor: colors.border, color: colors.text },
          ]}
          placeholder="0"
          placeholderTextColor={colors.muted}
          keyboardType="numeric"
          value={priceMin?.toString() || ''}
          onChangeText={(v) => onPriceChange('priceMin', v)}
          accessibilityLabel="Minimum price"
          returnKeyType="done"
        />
      </View>
      <Text style={[styles.priceDash, { color: colors.muted }]}>—</Text>
      <View style={styles.priceInputWrapper}>
        <Text style={[styles.priceLabel, { color: colors.muted }]}>Max</Text>
        <TextInput
          style={[
            styles.priceInput,
            { borderColor: colors.border, color: colors.text },
          ]}
          placeholder="No limit"
          placeholderTextColor={colors.muted}
          keyboardType="numeric"
          value={priceMax?.toString() || ''}
          onChangeText={(v) => onPriceChange('priceMax', v)}
          accessibilityLabel="Maximum price"
          returnKeyType="done"
        />
      </View>
    </View>
  );
}

export const PriceRangeFilter = React.memo(PriceRangeFilterInner);

const styles = StyleSheet.create({
  priceInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  priceInputWrapper: {
    flex: 1,
  },
  priceLabel: {
    fontSize: 11,
    fontWeight: '600',
    marginBottom: 4,
  },
  priceInput: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
  },
  priceDash: {
    fontSize: 16,
    marginTop: 16,
  },
});
