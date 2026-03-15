/**
 * BarcodeResultCard — displays the product found after a barcode/ISBN scan.
 */

import React from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { formatPrice } from '@/lib/format';
import { fireHaptic, HapticIntent } from '@/haptics';
import type { BarcodeLookupResult } from '@/data';
import type { CurrencyCode } from '@/data/types';
import type { IntakeResultResponse } from '@/api/collectorsApi';

interface BarcodeResultCardProps {
  lookupResult: BarcodeLookupResult;
  intakeResult: IntakeResultResponse | null;
  scannedCode: { type: string; value: string } | null;
  affiliateLink: { url: string; label: string } | null;
  isSaving: boolean;
  currency: CurrencyCode;
  hapticsEnabled: boolean;
  onRescan: () => void;
  onSave: () => void;
  onAddToWatchlist: () => void;
}

export const BarcodeResultCard = React.memo(function BarcodeResultCard({
  lookupResult,
  intakeResult,
  scannedCode,
  affiliateLink,
  isSaving,
  currency,
  hapticsEnabled,
  onRescan,
  onSave,
  onAddToWatchlist,
}: BarcodeResultCardProps) {
  const { colors } = useAppTheme();

  return (
    <ScrollView style={styles.resultContainer} contentContainerStyle={styles.resultContent}>
      {/* Product card */}
      <View style={[styles.productCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.productHeader}>
          <Ionicons name="checkmark-circle" size={32} color={colors.accent} />
          <Text style={[styles.productFound, { color: colors.text }]}>Product Found</Text>
        </View>

        <Text style={[styles.productTitle, { color: colors.text }]}>
          {lookupResult.title || 'Unknown Product'}
        </Text>

        {lookupResult.categoryId && (
          <View style={styles.productMeta}>
            <Ionicons name="folder-outline" size={16} color={colors.muted} />
            <Text style={[styles.productMetaText, { color: colors.muted }]}>
              {lookupResult.categoryId}
              {intakeResult ? ` (${Math.round(intakeResult.category_confidence * 100)}% confidence)` : ''}
            </Text>
          </View>
        )}

        {intakeResult?.identification_method && (
          <View style={styles.productMeta}>
            <Ionicons name="bulb-outline" size={16} color={colors.muted} />
            <Text style={[styles.productMetaText, { color: colors.muted }]}>
              Identified via: {intakeResult.identification_method.replace(/_/g, ' ')}
            </Text>
          </View>
        )}

        {lookupResult.collections && lookupResult.collections.length > 0 && (
          <View style={styles.collectionsRow}>
            {lookupResult.collections.map((tag) => (
              <View key={tag} style={[styles.collectionTag, { backgroundColor: colors.accent + '20' }]}>
                <Text style={[styles.collectionTagText, { color: colors.accent }]}>{tag}</Text>
              </View>
            ))}
          </View>
        )}

        {lookupResult.priceBand && (
          <View style={[styles.priceCard, { backgroundColor: colors.background }]}>
            <Text style={[styles.priceLabel, { color: colors.muted }]}>Estimated Price</Text>
            <Text style={[styles.priceValue, { color: colors.text }]}>
              {formatPrice(lookupResult.priceBand.q50, currency)}
            </Text>
            <Text style={[styles.priceRange, { color: colors.muted }]}>
              Range: {formatPrice(lookupResult.priceBand.q10, currency)} – {formatPrice(lookupResult.priceBand.q90, currency)}
            </Text>
          </View>
        )}

        {scannedCode && (
          <Text style={[styles.barcodeInfo, { color: colors.muted }]}>
            {scannedCode.type.toUpperCase()}: {scannedCode.value}
          </Text>
        )}
      </View>

      {/* Action buttons */}
      <View style={styles.actionButtonsRow}>
        <AnimatedPressable
          style={[styles.secondaryButtonHalf, { borderColor: colors.border }]}
          onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled }); onRescan(); }}
          accessibilityRole="button"
          accessibilityLabel="Scan another barcode"
        >
          <Ionicons name="scan-outline" size={18} color={colors.text} />
          <Text style={[styles.secondaryButtonText, { color: colors.text }]}>Scan Another</Text>
        </AnimatedPressable>

        <AnimatedPressable
          style={[styles.primaryButtonHalf, { backgroundColor: colors.accent, opacity: isSaving ? 0.7 : 1 }]}
          onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: hapticsEnabled }); onSave(); }}
          disabled={isSaving}
          accessibilityRole="button"
          accessibilityLabel="Save to collection"
        >
          {isSaving ? (
            <ActivityIndicator size="small" color={colors.card} />
          ) : (
            <>
              <Ionicons name="add-circle-outline" size={18} color={colors.card} />
              <Text style={[styles.primaryButtonText, { color: colors.card }]}>Save</Text>
            </>
          )}
        </AnimatedPressable>
      </View>

      <AnimatedPressable
        style={[styles.watchlistButton, { borderColor: colors.border }]}
        onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled }); onAddToWatchlist(); }}
        accessibilityRole="button"
        accessibilityLabel="Add to watchlist instead"
      >
        <Ionicons name="eye-outline" size={18} color={colors.muted} />
        <Text style={[styles.watchlistButtonText, { color: colors.muted }]}>Add to Watchlist Instead</Text>
      </AnimatedPressable>

      {affiliateLink && (
        <AnimatedPressable
          style={[styles.watchlistButton, { borderColor: colors.border, marginTop: 8 }]}
          onPress={() => {
            fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled });
            Linking.openURL(affiliateLink.url).catch(() => {});
          }}
          accessibilityRole="link"
          accessibilityLabel={affiliateLink.label}
        >
          <Ionicons name="open-outline" size={18} color={colors.accent} />
          <Text style={[styles.watchlistButtonText, { color: colors.accent }]}>{affiliateLink.label}</Text>
        </AnimatedPressable>
      )}
    </ScrollView>
  );
});

const styles = StyleSheet.create({
  resultContainer: {
    flex: 1,
  },
  resultContent: {
    padding: 16,
  },
  productCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  productHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  productFound: {
    fontSize: 16,
    fontWeight: '600',
  },
  productTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 8,
  },
  productMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  productMetaText: {
    fontSize: 14,
  },
  collectionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 12,
  },
  collectionTag: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  collectionTagText: {
    fontSize: 12,
    fontWeight: '500',
  },
  priceCard: {
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  priceLabel: {
    fontSize: 12,
    marginBottom: 4,
  },
  priceValue: {
    fontSize: 24,
    fontWeight: '700',
  },
  priceRange: {
    fontSize: 12,
    marginTop: 4,
  },
  barcodeInfo: {
    fontSize: 12,
    fontFamily: 'monospace',
    marginTop: 8,
  },
  actionButtonsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  primaryButtonHalf: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 16,
    borderRadius: 12,
  },
  primaryButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryButtonHalf: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 16,
    borderRadius: 12,
    borderWidth: 1,
  },
  secondaryButtonText: {
    fontSize: 16,
    fontWeight: '500',
  },
  watchlistButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 12,
    marginTop: 8,
  },
  watchlistButtonText: {
    fontSize: 13,
  },
});
