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
import { useTranslation } from 'react-i18next';
import { useScannerTheme } from '@/hooks/useAppTheme';
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
  const { colors } = useScannerTheme();
  const { t } = useTranslation();

  return (
    <ScrollView style={styles.resultContainer} contentContainerStyle={styles.resultContent}>
      {/* Product card */}
      <View style={[styles.productCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
        <View style={styles.productHeader}>
          <Ionicons name="checkmark-circle" size={32} color={colors.accent} />
          <Text style={[styles.productFound, { color: colors.text }]}>{t('barcode.product_found')}</Text>
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
            <Text style={[styles.priceLabel, { color: colors.muted }]}>{t('barcode.estimated_price')}</Text>
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
      {/* AnimatedPressable applies `style` to its inner Animated.View, so the
          `flex: 1` on these halves never reached the outer Pressable and both
          buttons sized to their content. The wrapper Views own the flex. */}
      <View style={styles.actionButtonsRow}>
        <View style={{ flex: 1, minWidth: 0 }}>
          <AnimatedPressable
            style={[styles.secondaryButtonHalf, { borderColor: colors.border }]}
            onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled }); onRescan(); }}
            accessibilityRole="button"
            accessibilityLabel={t('barcode.scan_another_a11y')}
          >
            <Ionicons name="scan-outline" size={18} color={colors.text} />
            <Text
              numberOfLines={1}
              style={[styles.secondaryButtonText, { color: colors.text, flexShrink: 1 }]}
            >
              {t('barcode.scan_another')}
            </Text>
          </AnimatedPressable>
        </View>

        <View style={{ flex: 1, minWidth: 0 }}>
          <AnimatedPressable
            style={[styles.primaryButtonHalf, { backgroundColor: colors.accent, opacity: isSaving ? 0.7 : 1 }]}
            onPress={() => { fireHaptic(HapticIntent.JUDGMENT_LOCKED, { enabled: hapticsEnabled }); onSave(); }}
            disabled={isSaving}
            accessibilityRole="button"
            accessibilityLabel={t('barcode.save_a11y')}
          >
            {isSaving ? (
              <ActivityIndicator size="small" color={colors.accentText} />
            ) : (
              <>
                {/* accentText, NOT colors.card — `card` is a SURFACE token. It
                    only looked right in light mode because card was near-white;
                    on the black scanner theme it rendered dark-on-teal. */}
                <Ionicons name="add-circle-outline" size={18} color={colors.accentText} />
                <Text
                  numberOfLines={1}
                  style={[styles.primaryButtonText, { color: colors.accentText, flexShrink: 1 }]}
                >
                  Save
                </Text>
              </>
            )}
          </AnimatedPressable>
        </View>
      </View>

      <AnimatedPressable
        style={[styles.watchlistButton, { borderColor: colors.border }]}
        onPress={() => { fireHaptic(HapticIntent.CONFIRMATION_LIGHT, { enabled: hapticsEnabled }); onAddToWatchlist(); }}
        accessibilityRole="button"
        accessibilityLabel={t('barcode.add_watchlist_a11y')}
      >
        <Ionicons name="eye-outline" size={18} color={colors.muted} />
        <Text style={[styles.watchlistButtonText, { color: colors.muted }]}>{t('barcode.add_watchlist_btn')}</Text>
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
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingHorizontal: 12,
    borderRadius: 12,
  },
  primaryButtonText: {
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryButtonHalf: {
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingHorizontal: 12,
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
