/**
 * PriceExplanationSheet Component
 * Bottom sheet displaying detailed price explanation.
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  ScrollView,
  SafeAreaView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { AnimatedPressable } from '@/motion';
import { fireHaptic, HapticIntent } from '@/haptics';
import {
  PriceExplanation,
  PriceBand,
  getConfidenceLabel,
  getConfidenceColor,
} from '@/types/priceExplanation';
import { RangeBar } from './RangeBar';

type PriceExplanationSheetProps = {
  visible: boolean;
  onClose: () => void;
  explanation: PriceExplanation | null;
  priceBand?: PriceBand;
  currency?: string;
};

function formatPrice(value: number, currency: string = 'EUR'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function PriceExplanationSheet({
  visible,
  onClose,
  explanation,
  priceBand,
  currency = 'EUR',
}: PriceExplanationSheetProps) {
  const { colors } = useAppTheme();

  if (!explanation) return null;

  const confidenceColor = getConfidenceColor(explanation.confidenceTier);
  const confidenceLabel = getConfidenceLabel(explanation.confidenceTier);

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        {/* Header */}
        <View style={[styles.header, { borderBottomColor: colors.border }]}>
          <Text style={[styles.headerTitle, { color: colors.text }]}>
            Price Explanation
          </Text>
          <AnimatedPressable
            onPress={() => {
              fireHaptic(HapticIntent.CONFIRMATION_LIGHT);
              onClose();
            }}
            style={styles.closeButton}
            accessibilityRole="button"
            accessibilityLabel="Close"
          >
            <Ionicons name="close" size={24} color={colors.text} />
          </AnimatedPressable>
        </View>

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
              {explanation.compSources.map((source, index) => (
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
                    <Text style={[styles.sourceName, { color: colors.text }]}>{source.source}</Text>
                    <Text style={[styles.sourceCount, { color: colors.muted }]}>
                      {source.count} comparable sales
                      {source.dateRange && ` • ${source.dateRange}`}
                    </Text>
                  </View>
                  <Text style={[styles.sourcePrice, { color: colors.text }]}>
                    {formatPrice(source.avgPrice, currency)}
                  </Text>
                </View>
              ))}
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
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  closeButton: {
    position: 'absolute',
    right: 16,
    padding: 4,
  },
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
