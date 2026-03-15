/**
 * ItemPriceSection — Price card, legacy price bands, confidence gauge,
 * explanation, scarcity badge, and comparable sales.
 */

import React, { useMemo } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { PriceCard } from '@/components/PriceCard';
import { PriceConfidenceGauge } from '@/components/PriceConfidenceGauge';
import { featureFlags } from '@/config/featureFlags';
import { radius, text, fontWeight, gap } from '@/theme/tokens';
import { formatPrice } from '@/lib/format';
import type { PriceEstimate } from '@/types/priceExplanation';
import type { CurrencyCode } from '@/data/types';

interface ScarcityData {
  scarcity_score: number;
  listing_count: number;
  supply_trend: string;
}

interface MarketComp {
  title: string;
  source: string;
  price: number;
  currency: string;
}

interface ItemPriceSectionProps {
  priceEstimate: PriceEstimate | null;
  onWhyThisPrice: () => void;
  // Legacy fields (when feature flag is off)
  q10?: string;
  q50?: string;
  q90?: string;
  confidence?: string;
  explanation?: string;
  explanationExpanded: boolean;
  onToggleExplanation: () => void;
  // Scarcity
  scarcityData: ScarcityData | null;
  // Market comps
  marketComps: MarketComp[];
  // Helpers
  toNum: (value: string | number | undefined | null) => number | undefined;
}

export const ItemPriceSection = React.memo(function ItemPriceSection({
  priceEstimate,
  onWhyThisPrice,
  q10,
  q50,
  q90,
  confidence,
  explanation,
  explanationExpanded,
  onToggleExplanation,
  scarcityData,
  marketComps,
  toNum,
}: ItemPriceSectionProps) {
  const { colors: theme } = useAppTheme();

  return (
    <>
      {/* New Explainable AI Interface - PriceCard with visual RangeBar */}
      {featureFlags.FEATURE_EXPLAINABLE_AI_INTERFACES && priceEstimate && (
        <View style={styles.priceCardSection}>
          <PriceCard
            estimate={priceEstimate}
            onWhyThisPrice={onWhyThisPrice}
            showRangeBar={true}
            compact={false}
          />
        </View>
      )}

      {/* Legacy Price bands (q10/q50/q90) — shown when feature flag is off */}
      {!featureFlags.FEATURE_EXPLAINABLE_AI_INTERFACES && (q10 || q50 || q90) && (
        <View style={styles.priceBandsRow}>
          <Text style={[styles.label, { color: theme.muted }]}>
            Price range
          </Text>
          <Text style={{ fontSize: text.md, fontWeight: fontWeight.medium, color: theme.text }}>
            {formatPrice(toNum(q10))} – {formatPrice(toNum(q50))} – {formatPrice(toNum(q90))}
          </Text>
        </View>
      )}

      {/* Legacy Confidence Gauge — shown when feature flag is off */}
      {!featureFlags.FEATURE_EXPLAINABLE_AI_INTERFACES && confidence && (
        <View style={styles.confidenceSection}>
          <PriceConfidenceGauge
            confidence={parseFloat(confidence)}
            size="medium"
            colors={{
              text: theme.text,
              muted: theme.muted,
              background: theme.border,
            }}
          />
        </View>
      )}

      {/* Legacy Explanation — expandable "Why this price?" section */}
      {!featureFlags.FEATURE_EXPLAINABLE_AI_INTERFACES && explanation && (
        <View style={[styles.explanationBlock, { borderTopColor: theme.border }]}>
          <Pressable
            onPress={onToggleExplanation}
            style={styles.explanationHeaderRow}
            accessibilityRole="button"
            accessibilityLabel={`Why this price${explanationExpanded ? ', expanded' : ', collapsed'}`}
          >
            <View style={styles.explanationHeaderLeft}>
              <Ionicons name="help-circle-outline" size={18} color={theme.accent} />
              <Text style={[styles.explanationHeader, { color: theme.text }]}>
                Why this price?
              </Text>
            </View>
            <Ionicons
              name={explanationExpanded ? "chevron-up" : "chevron-down"}
              size={18}
              color={theme.muted}
            />
          </Pressable>
          {explanationExpanded && (
            <View style={[styles.explanationContent, { backgroundColor: theme.background }]}>
              <Text style={[styles.explanationText, { color: theme.muted }]}>
                {explanation}
              </Text>
            </View>
          )}
        </View>
      )}

      {/* Scarcity Badge */}
      {scarcityData && (
        <View style={[styles.scarcityBadge, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <View style={styles.scarcityRow}>
            <Ionicons name="diamond-outline" size={16} color={scarcityData.scarcity_score >= 7 ? theme.error : scarcityData.scarcity_score >= 4 ? theme.warning : theme.success} />
            <Text style={[styles.scarcityLabel, { color: theme.text }]}>
              {scarcityData.scarcity_score >= 7 ? 'Rare' : scarcityData.scarcity_score >= 4 ? 'Moderate' : 'Common'}
            </Text>
            <Text style={[styles.scarcityMeta, { color: theme.muted }]}>
              {scarcityData.listing_count} listings · Supply {scarcityData.supply_trend}
            </Text>
          </View>
        </View>
      )}

      {/* Market Comps */}
      {marketComps.length > 0 && (
        <View style={[styles.compsSection, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <Text style={[styles.compsTitle, { color: theme.text }]}>
            <Ionicons name="stats-chart-outline" size={14} color={theme.accent} /> Comparable Sales
          </Text>
          {marketComps.map((comp, i) => (
            <View key={i} style={[styles.compRow, i > 0 && { borderTopColor: theme.border, borderTopWidth: StyleSheet.hairlineWidth }]}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.compTitle, { color: theme.text }]} numberOfLines={1}>{comp.title}</Text>
                <Text style={[styles.compSource, { color: theme.muted }]}>{comp.source}</Text>
              </View>
              <Text style={[styles.compPrice, { color: theme.accent }]}>{formatPrice(comp.price, comp.currency as CurrencyCode)}</Text>
            </View>
          ))}
        </View>
      )}
    </>
  );
});

const styles = StyleSheet.create({
  priceCardSection: {
    marginTop: 16,
    marginBottom: 4,
  },
  priceBandsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 6,
  },
  label: {
    fontSize: text.md,
  },
  confidenceSection: {
    marginTop: 12,
  },
  explanationBlock: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
  },
  explanationHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
  },
  explanationHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: gap.md,
  },
  explanationHeader: {
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
  },
  explanationContent: {
    marginTop: 10,
    padding: 12,
    borderRadius: radius.sm,
  },
  explanationText: {
    fontSize: text.md,
    lineHeight: 19,
  },
  scarcityBadge: { borderRadius: radius.md, borderWidth: 1, padding: 10, marginTop: 10, marginBottom: 4 },
  scarcityRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  scarcityLabel: { fontSize: text.md, fontWeight: fontWeight.semibold },
  scarcityMeta: { fontSize: text.sm, flex: 1, textAlign: 'right' },
  compsSection: { borderRadius: radius.md, borderWidth: 1, padding: 12, marginTop: 10 },
  compsTitle: { fontSize: text.md, fontWeight: fontWeight.semibold, marginBottom: 8 },
  compRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8 },
  compTitle: { fontSize: text.sm, fontWeight: fontWeight.medium },
  compSource: { fontSize: text.xs, marginTop: 1 },
  compPrice: { fontSize: text.md, fontWeight: fontWeight.bold, marginLeft: 8 },
});
