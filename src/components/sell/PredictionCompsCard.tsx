/**
 * PredictionCompsCard — Actuals vs Predicted comparison card for seller dashboard.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { formatPrice } from '@/lib/format';
import { radius, text, fontWeight, gap } from '@/theme/tokens';
import type { CurrencyCode } from '@/data/types';

interface PredictionComp {
  item_key: string;
  predicted: number;
  actual: number;
  category: string;
}

interface PredictionCompsCardProps {
  comparisons: PredictionComp[];
  currency: CurrencyCode;
}

export const PredictionCompsCard = React.memo(function PredictionCompsCard({
  comparisons,
  currency,
}: PredictionCompsCardProps) {
  const { colors } = useAppTheme();

  if (comparisons.length === 0) return null;

  return (
    <View style={[styles.predCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.predCardHeader}>
        <Ionicons name="analytics-outline" size={16} color={colors.accent} />
        <Text style={[styles.predCardTitle, { color: colors.text }]}>Actuals vs Predicted</Text>
      </View>
      {comparisons.map((comp) => {
        const diff = comp.actual - comp.predicted;
        const diffPct = comp.predicted > 0 ? (diff / comp.predicted) * 100 : 0;
        const isOver = diff >= 0;
        return (
          <View key={comp.item_key} style={[styles.predCompRow, { borderBottomColor: colors.border }]}>
            <View style={{ flex: 2 }}>
              <Text style={[styles.predCompName, { color: colors.text }]} numberOfLines={1}>
                {comp.item_key.replace(/-/g, ' ')}
              </Text>
              <Text style={{ fontSize: text.sm, color: colors.muted, textTransform: 'capitalize' }}>
                {comp.category.replace(/_/g, ' ')}
              </Text>
            </View>
            <View style={{ flex: 1, alignItems: 'flex-end' }}>
              <Text style={{ fontSize: text.sm, color: colors.muted }}>
                {formatPrice(comp.predicted, currency)}
              </Text>
              <Text style={{ fontSize: text.md, fontWeight: fontWeight.bold, color: isOver ? colors.success : colors.danger }}>
                {formatPrice(comp.actual, currency)} ({isOver ? '+' : ''}{diffPct.toFixed(0)}%)
              </Text>
            </View>
          </View>
        );
      })}
    </View>
  );
});

const styles = StyleSheet.create({
  predCard: { borderRadius: radius.md, borderWidth: 1, padding: 14, marginTop: 16 },
  predCardHeader: { flexDirection: 'row', alignItems: 'center', gap: gap.md, marginBottom: 10 },
  predCardTitle: { fontSize: text.lg, fontWeight: fontWeight.bold },
  predCompRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: gap.md, borderBottomWidth: StyleSheet.hairlineWidth },
  predCompName: { fontSize: text.md, fontWeight: fontWeight.semibold },
});
