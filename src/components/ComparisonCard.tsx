/**
 * ComparisonCard — side-by-side comparison of two scanned items.
 * Shows images, name/value/condition/confidence/rarity, and price delta.
 */

import React from 'react';
import { View, Text, StyleSheet, Image, ScrollView, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { formatPrice } from '@/lib/format';
import { fireHaptic, HapticIntent } from '@/haptics';
import { useSettings } from '@/lib/settings';
import { useTranslation } from 'react-i18next';
import type { QuickScanResult, CurrencyCode } from '@/data/types';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const HALF_WIDTH = (SCREEN_WIDTH - 48) / 2;

type Props = {
  itemA: QuickScanResult;
  itemB: QuickScanResult;
  imageUriA: string;
  imageUriB: string;
  currency: CurrencyCode;
  onKeepA: () => void;
  onKeepB: () => void;
  onKeepBoth: () => void;
  onRetake: () => void;
};

function ComparisonRow({
  label,
  valueA,
  valueB,
  highlightHigher,
}: {
  label: string;
  valueA: string;
  valueB: string;
  highlightHigher?: 'a' | 'b' | null;
}) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.compRow}>
      <Text
        style={[
          styles.compValue,
          { color: highlightHigher === 'a' ? colors.success : colors.text },
        ]}
        numberOfLines={2}
      >
        {valueA}
      </Text>
      <View style={[styles.compLabelContainer, { backgroundColor: colors.border + '40' }]}>
        <Text style={[styles.compLabel, { color: colors.muted }]}>{label}</Text>
      </View>
      <Text
        style={[
          styles.compValue,
          { color: highlightHigher === 'b' ? colors.success : colors.text, textAlign: 'right' },
        ]}
        numberOfLines={2}
      >
        {valueB}
      </Text>
    </View>
  );
}

function ComparisonCardInner({
  itemA,
  itemB,
  imageUriA,
  imageUriB,
  currency,
  onKeepA,
  onKeepB,
  onKeepBoth,
  onRetake,
}: Props) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const { t } = useTranslation();
  const haptic = (intent: HapticIntent) => fireHaptic(intent, { enabled: settings.hapticsEnabled });

  const priceA = itemA.prediction.estimatedMid;
  const priceB = itemB.prediction.estimatedMid;
  const priceDelta = priceB - priceA;
  const priceDeltaPct = priceA > 0 ? Math.round((priceDelta / priceA) * 100) : 0;
  const priceHigher = priceDelta > 0 ? 'b' : priceDelta < 0 ? 'a' : null;

  const confA = Math.round(itemA.prediction.confidence * 100);
  const confB = Math.round(itemB.prediction.confidence * 100);
  const confHigher = confA > confB ? 'a' : confB > confA ? 'b' : null;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <ScrollView contentContainerStyle={styles.scroll} bounces={false}>
        {/* Side-by-side images */}
        <View style={styles.imagesRow}>
          <View style={styles.imageWrapper}>
            <Image source={{ uri: imageUriA }} style={styles.compImage} resizeMode="cover" />
            <View style={[styles.imageBadge, { backgroundColor: colors.brand.base }]}>
              <Text style={styles.imageBadgeText}>A</Text>
            </View>
          </View>
          <View style={styles.imageWrapper}>
            <Image source={{ uri: imageUriB }} style={styles.compImage} resizeMode="cover" />
            <View style={[styles.imageBadge, { backgroundColor: '#8B5CF6' }]}>{/* Purple for B-item distinction */}
              <Text style={styles.imageBadgeText}>B</Text>
            </View>
          </View>
        </View>

        {/* Price delta banner */}
        {priceDelta !== 0 && (
          <View
            style={[
              styles.deltaBanner,
              { backgroundColor: priceDelta > 0 ? colors.success + '15' : colors.danger + '15' },
            ]}
          >
            <Ionicons
              name={priceDelta > 0 ? 'arrow-up' : 'arrow-down'}
              size={16}
              color={priceDelta > 0 ? colors.success : colors.danger}
            />
            <Text
              style={[styles.deltaText, { color: priceDelta > 0 ? colors.success : colors.danger }]}
            >
              {priceDelta > 0 ? '+' : ''}
              {formatPrice(Math.abs(priceDelta), currency)} ({priceDeltaPct > 0 ? '+' : ''}
              {priceDeltaPct}%)
            </Text>
          </View>
        )}

        {/* Comparison table */}
        <View style={[styles.table, { backgroundColor: colors.card, borderColor: colors.border }]}>
          <ComparisonRow
            label={t('scan.comparison.name')}
            valueA={itemA.prediction.name || t('scan.unknown')}
            valueB={itemB.prediction.name || t('scan.unknown')}
          />
          <ComparisonRow
            label={t('scan.comparison.value')}
            valueA={formatPrice(priceA, currency)}
            valueB={formatPrice(priceB, currency)}
            highlightHigher={priceHigher}
          />
          <ComparisonRow
            label={t('scan.comparison.category')}
            valueA={(itemA.attributes.category || '').replace(/_/g, ' ')}
            valueB={(itemB.attributes.category || '').replace(/_/g, ' ')}
          />
          <ComparisonRow
            label={t('scan.comparison.condition')}
            valueA={itemA.attributes.conditionGuess ?? t('scan.na')}
            valueB={itemB.attributes.conditionGuess ?? t('scan.na')}
          />
          <ComparisonRow
            label={t('scan.comparison.confidence')}
            valueA={`${confA}%`}
            valueB={`${confB}%`}
            highlightHigher={confHigher}
          />
          {(itemA.attributes.editionGuess || itemB.attributes.editionGuess) && (
            <ComparisonRow
              label={t('scan.comparison.rarity')}
              valueA={itemA.attributes.editionGuess ?? t('scan.na')}
              valueB={itemB.attributes.editionGuess ?? t('scan.na')}
            />
          )}
        </View>
      </ScrollView>

      {/* Action buttons */}
      <View
        style={[styles.bottomBar, { backgroundColor: colors.background, borderTopColor: colors.border }]}
      >
        <View style={styles.btnRow}>
          <AnimatedPressable
            style={[styles.actionBtn, { backgroundColor: colors.brand.base }]}
            onPress={() => { haptic(HapticIntent.JUDGMENT_LOCKED); onKeepA(); }}
            accessibilityRole="button"
            accessibilityLabel={t('scan.comparison.keep_a_a11y')}
          >
            <Text style={styles.actionBtnText}>{t('scan.comparison.keep_a')}</Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={[styles.actionBtn, { backgroundColor: '#8B5CF6' }]}
            onPress={() => { haptic(HapticIntent.JUDGMENT_LOCKED); onKeepB(); }}
            accessibilityRole="button"
            accessibilityLabel={t('scan.comparison.keep_b_a11y')}
          >
            <Text style={styles.actionBtnText}>{t('scan.comparison.keep_b')}</Text>
          </AnimatedPressable>
        </View>
        <View style={styles.btnRow}>
          <AnimatedPressable
            style={[styles.secondaryBtn, { borderColor: colors.border }]}
            onPress={() => { haptic(HapticIntent.JUDGMENT_LOCKED); onKeepBoth(); }}
            accessibilityRole="button"
          >
            <Text style={[styles.secondaryBtnText, { color: colors.text }]}>{t('scan.comparison.keep_both')}</Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={[styles.secondaryBtn, { borderColor: colors.border }]}
            onPress={() => { haptic(HapticIntent.CONFIRMATION_LIGHT); onRetake(); }}
            accessibilityRole="button"
          >
            <Text style={[styles.secondaryBtnText, { color: colors.text }]}>{t('scan.retake')}</Text>
          </AnimatedPressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scroll: {
    paddingBottom: 160,
  },
  imagesRow: {
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  imageWrapper: {
    flex: 1,
    position: 'relative',
  },
  compImage: {
    width: '100%',
    height: HALF_WIDTH * 1.2,
    borderRadius: 14,
  },
  imageBadge: {
    position: 'absolute',
    top: 8,
    left: 8,
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  imageBadgeText: {
    color: '#FFFFFF', // Badge text on colored circle — always white
    fontSize: 14,
    fontWeight: '800',
  },
  deltaBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginHorizontal: 16,
    marginTop: 12,
    paddingVertical: 10,
    borderRadius: 10,
  },
  deltaText: {
    fontSize: 14,
    fontWeight: '700',
  },
  table: {
    marginTop: 12,
    marginHorizontal: 16,
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
  },
  compRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: 'rgba(128,128,128,0.15)',
  },
  compValue: {
    flex: 1,
    fontSize: 13,
    fontWeight: '600',
  },
  compLabelContainer: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    marginHorizontal: 6,
  },
  compLabel: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  bottomBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: 16,
    paddingBottom: 40,
    paddingTop: 12,
    borderTopWidth: 1,
    gap: 8,
  },
  btnRow: {
    flexDirection: 'row',
    gap: 10,
  },
  actionBtn: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    borderRadius: 14,
  },
  actionBtnText: {
    color: '#FFFFFF', // Button text on brand/accent background — always white
    fontSize: 16,
    fontWeight: '700',
  },
  secondaryBtn: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
  },
  secondaryBtnText: {
    fontSize: 14,
    fontWeight: '600',
  },
});

export const ComparisonCard = React.memo(ComparisonCardInner);
export default ComparisonCard;
