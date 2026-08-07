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
  /** Symbol for the currency the bounds are read as, e.g. '€'. Shown in the
   *  labels and inside each field. Without it the inputs are two bare numbers:
   *  a JPY user typing 50 means ¥50, a EUR user means €50, and the screen
   *  applying the filter cannot tell them apart either. Optional so existing
   *  callers keep the unlabelled behaviour rather than being forced to guess. */
  currencySymbol?: string;
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
  currencySymbol,
  colors,
}: PriceRangeFilterProps) {
  const unit = currencySymbol ? ` (${currencySymbol})` : '';
  return (
    <View style={styles.priceInputRow}>
      <View style={styles.priceInputWrapper}>
        <Text style={[styles.priceLabel, { color: colors.muted }]}>{`Min${unit}`}</Text>
        <View style={styles.field}>
          {currencySymbol ? (
            <Text style={[styles.affix, { color: colors.muted }]}>{currencySymbol}</Text>
          ) : null}
          <TextInput
            style={[
              styles.priceInput,
              styles.fieldInput,
              { borderColor: colors.border, color: colors.text },
              currencySymbol ? styles.fieldInputWithAffix : null,
            ]}
            placeholder="0"
            placeholderTextColor={colors.muted}
            keyboardType="numeric"
            value={priceMin?.toString() || ''}
            onChangeText={(v) => onPriceChange('priceMin', v)}
            accessibilityLabel={
              currencySymbol ? `Minimum price in ${currencySymbol}` : 'Minimum price'
            }
            returnKeyType="done"
          />
        </View>
      </View>
      <Text style={[styles.priceDash, { color: colors.muted }]}>—</Text>
      <View style={styles.priceInputWrapper}>
        <Text style={[styles.priceLabel, { color: colors.muted }]}>{`Max${unit}`}</Text>
        <View style={styles.field}>
          {currencySymbol ? (
            <Text style={[styles.affix, { color: colors.muted }]}>{currencySymbol}</Text>
          ) : null}
          <TextInput
            style={[
              styles.priceInput,
              styles.fieldInput,
              { borderColor: colors.border, color: colors.text },
              currencySymbol ? styles.fieldInputWithAffix : null,
            ]}
            placeholder="No limit"
            placeholderTextColor={colors.muted}
            keyboardType="numeric"
            value={priceMax?.toString() || ''}
            onChangeText={(v) => onPriceChange('priceMax', v)}
            accessibilityLabel={
              currencySymbol ? `Maximum price in ${currencySymbol}` : 'Maximum price'
            }
            returnKeyType="done"
          />
        </View>
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
  // The symbol is overlaid rather than concatenated into the value, so it can
  // never be typed over, selected, or sent to the parser as part of the number.
  field: { position: 'relative', justifyContent: 'center' },
  fieldInput: { flex: 0 },
  fieldInputWithAffix: { paddingLeft: 26 },
  affix: {
    position: 'absolute', left: 12, zIndex: 1,
    fontSize: 14, fontWeight: '600',
  },
  priceDash: {
    fontSize: 16,
    marginTop: 16,
  },
});
