/**
 * RangeBar Component
 * Visual representation of price range with q10/q50/q90 markers.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useAppTheme } from '@/hooks/useAppTheme';
import { PriceBand, ConfidenceTier, getConfidenceColor } from '@/types/priceExplanation';
import type { CurrencyCode } from '@/data/types';

type RangeBarProps = {
  priceBand: PriceBand;
  confidenceTier: ConfidenceTier;
  currency?: CurrencyCode;
  showLabels?: boolean;
  size?: 'small' | 'medium' | 'large';
};

function formatPrice(value: number, currency: CurrencyCode = 'EUR'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function RangeBar({
  priceBand,
  confidenceTier,
  currency = 'EUR',
  showLabels = true,
  size = 'medium',
}: RangeBarProps) {
  const { colors } = useAppTheme();
  const accentColor = getConfidenceColor(confidenceTier);

  const { q10, q50, q90 } = priceBand;
  const range = q90 - q10;

  // Calculate marker position (q50 relative to range)
  const markerPosition = range > 0 ? ((q50 - q10) / range) * 100 : 50;

  const barHeight = size === 'small' ? 8 : size === 'large' ? 16 : 12;
  const markerSize = size === 'small' ? 12 : size === 'large' ? 20 : 16;
  const fontSize = size === 'small' ? 10 : size === 'large' ? 13 : 11;

  return (
    <View style={styles.container}>
      {/* Labels row */}
      {showLabels && (
        <View style={styles.labelsRow}>
          <Text style={[styles.labelText, { color: colors.muted, fontSize }]}>
            {formatPrice(q10, currency)}
          </Text>
          <Text style={[styles.labelText, styles.labelCenter, { color: colors.text, fontSize, fontWeight: '600' }]}>
            {formatPrice(q50, currency)}
          </Text>
          <Text style={[styles.labelText, { color: colors.muted, fontSize }]}>
            {formatPrice(q90, currency)}
          </Text>
        </View>
      )}

      {/* Bar */}
      <View style={[styles.barContainer, { height: barHeight, backgroundColor: colors.border }]}>
        {/* Gradient fill */}
        <View
          style={[
            styles.barFill,
            {
              backgroundColor: accentColor + '40',
              height: barHeight,
            },
          ]}
        />

        {/* Median marker */}
        <View
          style={[
            styles.marker,
            {
              left: `${markerPosition}%`,
              width: markerSize,
              height: markerSize,
              borderRadius: markerSize / 2,
              backgroundColor: accentColor,
              marginLeft: -markerSize / 2,
              top: (barHeight - markerSize) / 2,
            },
          ]}
        />

        {/* Q10 tick */}
        <View style={[styles.tick, styles.tickStart, { backgroundColor: colors.muted }]} />

        {/* Q90 tick */}
        <View style={[styles.tick, styles.tickEnd, { backgroundColor: colors.muted }]} />
      </View>

      {/* Descriptor labels */}
      {showLabels && (
        <View style={styles.descriptorRow}>
          <Text style={[styles.descriptorText, { color: colors.muted, fontSize: fontSize - 1 }]}>
            Low
          </Text>
          <Text style={[styles.descriptorText, { color: colors.muted, fontSize: fontSize - 1 }]}>
            Median
          </Text>
          <Text style={[styles.descriptorText, { color: colors.muted, fontSize: fontSize - 1 }]}>
            High
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
  },
  labelsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  labelText: {
    flex: 1,
  },
  labelCenter: {
    textAlign: 'center',
  },
  barContainer: {
    width: '100%',
    borderRadius: 999,
    overflow: 'visible',
    position: 'relative',
  },
  barFill: {
    position: 'absolute',
    left: 0,
    right: 0,
    borderRadius: 999,
  },
  marker: {
    position: 'absolute',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 2,
    elevation: 2,
  },
  tick: {
    position: 'absolute',
    top: -2,
    bottom: -2,
    width: 2,
    borderRadius: 1,
  },
  tickStart: {
    left: 0,
  },
  tickEnd: {
    right: 0,
  },
  descriptorRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 4,
  },
  descriptorText: {},
});

export default RangeBar;
