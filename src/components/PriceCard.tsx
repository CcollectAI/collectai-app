/**
 * PriceCard Component
 * Displays price estimate with confidence badge and "Why this price?" link.
 */

import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { RangeBar } from './RangeBar';
import {
  PriceEstimate,
  getConfidenceLabel,
  getConfidenceColor,
} from '@/types/priceExplanation';

type PriceCardProps = {
  estimate: PriceEstimate;
  onWhyThisPrice?: () => void;
  showRangeBar?: boolean;
  compact?: boolean;
};

function formatPrice(value: number, currency: string = 'EUR'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function PriceCard({
  estimate,
  onWhyThisPrice,
  showRangeBar = true,
  compact = false,
}: PriceCardProps) {
  const { colors } = useAppTheme();
  const confidenceColor = getConfidenceColor(estimate.confidenceTier);
  const confidenceLabel = getConfidenceLabel(estimate.confidenceTier);

  return (
    <View
      style={[
        styles.card,
        { backgroundColor: colors.card, borderColor: colors.border },
        compact && styles.cardCompact,
      ]}
      accessibilityRole="summary"
      accessibilityLabel={`Price estimate: ${formatPrice(estimate.priceBand.q50, estimate.currency)}. ${confidenceLabel}`}
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={[styles.label, { color: colors.muted }]}>Estimated Value</Text>
        <View style={[styles.confidenceBadge, { backgroundColor: confidenceColor + '20' }]}>
          <View style={[styles.confidenceDot, { backgroundColor: confidenceColor }]} />
          <Text style={[styles.confidenceText, { color: confidenceColor }]}>
            {confidenceLabel}
          </Text>
        </View>
      </View>

      {/* Main price */}
      <Text style={[styles.mainPrice, { color: colors.text }]}>
        {formatPrice(estimate.priceBand.q50, estimate.currency)}
      </Text>

      {/* Range text */}
      <Text style={[styles.rangeText, { color: colors.muted }]}>
        Range: {formatPrice(estimate.priceBand.q10, estimate.currency)} – {formatPrice(estimate.priceBand.q90, estimate.currency)}
      </Text>

      {/* Range bar */}
      {showRangeBar && !compact && (
        <View style={styles.rangeBarContainer}>
          <RangeBar
            priceBand={estimate.priceBand}
            confidenceTier={estimate.confidenceTier}
            currency={estimate.currency}
            showLabels={false}
            size="medium"
          />
        </View>
      )}

      {/* Why this price link */}
      {onWhyThisPrice && (
        <Pressable
          style={styles.whyLink}
          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT); onWhyThisPrice?.(); }}
          accessibilityRole="button"
          accessibilityLabel="Learn why this price was estimated"
          accessibilityHint="Opens explanation of how this price was calculated"
        >
          <Ionicons name="information-circle-outline" size={16} color={colors.accent} />
          <Text style={[styles.whyLinkText, { color: colors.accent }]}>
            Why this price?
          </Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
  },
  cardCompact: {
    padding: 12,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  label: {
    fontSize: 13,
    fontWeight: '500',
  },
  confidenceBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 6,
  },
  confidenceDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  confidenceText: {
    fontSize: 12,
    fontWeight: '600',
  },
  mainPrice: {
    fontSize: 32,
    fontWeight: '700',
    marginBottom: 4,
  },
  rangeText: {
    fontSize: 13,
    marginBottom: 12,
  },
  rangeBarContainer: {
    marginBottom: 12,
  },
  whyLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(0,0,0,0.1)',
  },
  whyLinkText: {
    fontSize: 14,
    fontWeight: '500',
  },
});

export default PriceCard;
