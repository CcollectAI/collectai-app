/**
 * PriceExplanationSheet Component
 * Bottom sheet displaying detailed price explanation.
 */

import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { fireHaptic, HapticIntent } from '@/haptics';
import { BottomSheetModal } from './BottomSheetModal';
import {
  PriceExplanation,
  PriceBand,
  getConfidenceLabel,
  getConfidenceColor,
} from '@/types/priceExplanation';
import type { CurrencyCode } from '@/data/types';
import { formatPrice } from '@/lib/format';
import { RangeBar } from './RangeBar';

type AffiliateLink = {
  source: string;
  url: string;
  affiliate_url: string;
  label: string;
};

type PriceExplanationSheetProps = {
  visible: boolean;
  onClose: () => void;
  explanation: PriceExplanation | null;
  priceBand?: PriceBand;
  currency?: CurrencyCode;
  affiliateLinks?: AffiliateLink[];
};

export function PriceExplanationSheet({
  visible,
  onClose,
  explanation,
  priceBand,
  currency = 'EUR',
  affiliateLinks = [],
}: PriceExplanationSheetProps) {
  const { colors } = useAppTheme();

  const handleClose = useCallback(() => {
    fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
    onClose();
  }, [onClose]);

  if (!explanation) return null;

  const confidenceColor = getConfidenceColor(explanation.confidenceTier);
  const confidenceLabel = getConfidenceLabel(explanation.confidenceTier);

  return (
    <BottomSheetModal
      visible={visible}
      onClose={handleClose}
      title="Price Explanation"
      colors={colors}
      mode="pageSheet"
    >
        <ScrollView
          style={styles.content}
          contentContainerStyle={styles.contentContainer}
          showsVerticalScrollIndicator={false}
        >
          {/* Summary */}
          <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.sectionHeader}>
              <Ionicons name="bulb-outline" size={20} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Summary</Text>
            </View>
            <Text style={[styles.summaryText, { color: colors.text }]}>
              {explanation.summary}
            </Text>
          </View>

          {/* Price Range Visualization */}
          {priceBand && (
            <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.sectionHeader}>
                <Ionicons name="analytics-outline" size={20} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Price Range</Text>
              </View>
              <RangeBar
                priceBand={priceBand}
                confidenceTier={explanation.confidenceTier}
                currency={currency}
                showLabels={true}
                size="large"
              />
            </View>
          )}

          {/* Confidence */}
          <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <View style={styles.sectionHeader}>
              <Ionicons name="shield-checkmark-outline" size={20} color={colors.accent} />
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Confidence Level</Text>
            </View>
            <View style={styles.confidenceRow}>
              <View style={[styles.confidenceBadge, { backgroundColor: confidenceColor + '20' }]}>
                <View style={[styles.confidenceDot, { backgroundColor: confidenceColor }]} />
                <Text style={[styles.confidenceText, { color: confidenceColor }]}>
                  {confidenceLabel}
                </Text>
              </View>
              <Text style={[styles.confidencePercent, { color: colors.muted }]}>
                {explanation.confidencePercent}%
              </Text>
            </View>
          </View>

          {/* Key Factors */}
          {explanation.keyFactors.length > 0 && (
            <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.sectionHeader}>
                <Ionicons name="list-outline" size={20} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Key Factors</Text>
              </View>
              {explanation.keyFactors.map((factor, index) => (
                <View key={index} style={styles.factorRow}>
                  <View style={[styles.factorBullet, { backgroundColor: colors.accent }]} />
                  <Text style={[styles.factorText, { color: colors.text }]}>{factor}</Text>
                </View>
              ))}
            </View>
          )}

          {/* Comparable Sources */}
          {explanation.compSources.length > 0 && (
            <View style={[styles.section, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <View style={styles.sectionHeader}>
                <Ionicons name="layers-outline" size={20} color={colors.accent} />
                <Text style={[styles.sectionTitle, { color: colors.text }]}>Data Sources</Text>
              </View>
              {explanation.compSources.map((source, index) => {
                const matchedLink = affiliateLinks.find(
                  (l) => source.source.toLowerCase().includes(l.source.toLowerCase())
                );
                return (
                  <View
                    key={index}
                    style={[
                      styles.sourceRow,
                      index < explanation.compSources.length - 1 && {
                        borderBottomWidth: StyleSheet.hairlineWidth,
                        borderBottomColor: colors.border,
                      },
                    ]}
                  >
                    <View style={styles.sourceInfo}>
                      {matchedLink ? (
                        <Pressable
                          onPress={() => {
                            fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
                            Linking.openURL(matchedLink.affiliate_url).catch(() => {});
                          }}
                          style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}
                          accessibilityRole="link"
                        >
                          <Text style={[styles.sourceName, { color: colors.accent }]}>{source.source}</Text>
                          <Text style={{ color: colors.accent, fontSize: 12 }}>↗</Text>
                        </Pressable>
                      ) : (
                        <Text style={[styles.sourceName, { color: colors.text }]}>{source.source}</Text>
                      )}
                      <Text style={[styles.sourceCount, { color: colors.muted }]}>
                        {source.count} comparable sales
                        {source.dateRange && ` • ${source.dateRange}`}
                      </Text>
                    </View>
                    <Text style={[styles.sourcePrice, { color: colors.text }]}>
                      {formatPrice(source.avgPrice, currency)}
                    </Text>
                  </View>
                );
              })}
            </View>
          )}

          {/* Disclaimer */}
          <View style={[styles.disclaimerSection, { backgroundColor: colors.background }]}>
            <Ionicons name="information-circle-outline" size={16} color={colors.muted} />
            <Text style={[styles.disclaimerText, { color: colors.muted }]}>
              {explanation.disclaimer}
            </Text>
          </View>

          {/* Calculated timestamp */}
          <Text style={[styles.timestamp, { color: colors.muted }]}>
            Calculated: {new Date(explanation.calculatedAt).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </Text>
        </ScrollView>
    </BottomSheetModal>
  );
}

const styles = StyleSheet.create({
  content: {
    flex: 1,
  },
  contentContainer: {
    padding: 16,
    gap: 16,
  },
  section: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  summaryText: {
    fontSize: 15,
    lineHeight: 22,
  },
  confidenceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  confidenceBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    gap: 8,
  },
  confidenceDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  confidenceText: {
    fontSize: 14,
    fontWeight: '600',
  },
  confidencePercent: {
    fontSize: 14,
    fontWeight: '500',
  },
  factorRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginBottom: 8,
  },
  factorBullet: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginTop: 7,
  },
  factorText: {
    flex: 1,
    fontSize: 14,
    lineHeight: 20,
  },
  sourceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
  },
  sourceInfo: {
    flex: 1,
  },
  sourceName: {
    fontSize: 14,
    fontWeight: '500',
  },
  sourceCount: {
    fontSize: 12,
    marginTop: 2,
  },
  sourcePrice: {
    fontSize: 14,
    fontWeight: '600',
  },
  disclaimerSection: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    padding: 12,
    borderRadius: 8,
  },
  disclaimerText: {
    flex: 1,
    fontSize: 12,
    lineHeight: 18,
  },
  timestamp: {
    fontSize: 11,
    textAlign: 'center',
    marginBottom: 16,
  },
});

export default PriceExplanationSheet;
