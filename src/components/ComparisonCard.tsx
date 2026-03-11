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
import type { QuickScanResult, CurrencyCode } from '@/data/types';

const TIFFANY = '#81D8D0';
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
          { color: highlightHigher === 'a' ? '#22C55E' : colors.text },
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
          { color: highlightHigher === 'b' ? '#22C55E' : colors.text, textAlign: 'right' },
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
            <View style={[styles.imageBadge, { backgroundColor: TIFFANY }]}>
              <Text style={styles.imageBadgeText}>A</Text>
            </View>
          </View>
          <View style={styles.imageWrapper}>
            <Image source={{ uri: imageUriB }} style={styles.compImage} resizeMode="cover" />
            <View style={[styles.imageBadge, { backgroundColor: '#8B5CF6' }]}>
              <Text style={styles.imageBadgeText}>B</Text>
            </View>
          </View>
        </View>

        {/* Price delta banner */}
        {priceDelta !== 0 && (
          <View
            style={[
              styles.deltaBanner,
              { backgroundColor: priceDelta > 0 ? '#22C55E15' : '#EF444415' },
            ]}
          >
            <Ionicons
              name={priceDelta > 0 ? 'arrow-up' : 'arrow-down'}
              size={16}
              color={priceDelta > 0 ? '#22C55E' : '#EF4444'}
            />
            <Text
              style={[styles.deltaText, { color: priceDelta > 0 ? '#22C55E' : '#EF4444' }]}
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
            label="Name"
            valueA={itemA.prediction.name || 'Unknown'}
            valueB={itemB.prediction.name || 'Unknown'}
          />
          <ComparisonRow
            label="Value"
            valueA={formatPrice(priceA, currency)}
            valueB={formatPrice(priceB, currency)}
            highlightHigher={priceHigher}
          />
          <ComparisonRow
            label="Category"
            valueA={(itemA.attributes.category || '').replace(/_/g, ' ')}
            valueB={(itemB.attributes.category || '').replace(/_/g, ' ')}
          />
          <ComparisonRow
            label="Condition"
            valueA={itemA.attributes.conditionGuess ?? 'N/A'}
            valueB={itemB.attributes.conditionGuess ?? 'N/A'}
          />
          <ComparisonRow
            label="Confidence"
            valueA={`${confA}%`}
            valueB={`${confB}%`}
            highlightHigher={confHigher}
          />
          {(itemA.attributes.editionGuess || itemB.attributes.editionGuess) && (
            <ComparisonRow
              label="Rarity"
              valueA={itemA.attributes.editionGuess ?? 'N/A'}
              valueB={itemB.attributes.editionGuess ?? 'N/A'}
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
            style={[styles.actionBtn, { backgroundColor: TIFFANY }]}
            onPress={onKeepA}
            accessibilityRole="button"
            accessibilityLabel="Keep item A"
          >
            <Text style={styles.actionBtnText}>Keep A</Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={[styles.actionBtn, { backgroundColor: '#8B5CF6' }]}
            onPress={onKeepB}
            accessibilityRole="button"
            accessibilityLabel="Keep item B"
          >
            <Text style={styles.actionBtnText}>Keep B</Text>
          </AnimatedPressable>
        </View>
        <View style={styles.btnRow}>
          <AnimatedPressable
            style={[styles.secondaryBtn, { borderColor: colors.border }]}
            onPress={onKeepBoth}
            accessibilityRole="button"
          >
            <Text style={[styles.secondaryBtnText, { color: colors.text }]}>Keep Both</Text>
          </AnimatedPressable>
          <AnimatedPressable
            style={[styles.secondaryBtn, { borderColor: colors.border }]}
            onPress={onRetake}
            accessibilityRole="button"
          >
            <Text style={[styles.secondaryBtnText, { color: colors.text }]}>Retake</Text>
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
    color: '#FFFFFF',
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
    color: '#FFFFFF',
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
