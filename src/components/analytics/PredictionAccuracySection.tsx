/**
 * PredictionAccuracySection — MAPE/R-squared table per category.
 * Extracted from analytics.tsx.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { text, fontWeight, radius, shadow } from '@/theme/tokens';

const COLORS = {
  card: '#FFFFFF',
  navy: '#0F172A',
  muted: '#64748B',
  border: '#E2E8F0',
};

export type PredictionAccuracyEntry = {
  category: string;
  mae: number;
  mape: number;
  r2: number;
};

type Props = {
  data: PredictionAccuracyEntry[];
};

function PredictionAccuracySectionInner({ data }: Props) {
  const { colors } = useAppTheme();

  if (!data || data.length === 0) return null;

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <View style={styles.cardHeader}>
        <Ionicons name="analytics-outline" size={18} color={colors.accent} />
        <Text style={[styles.cardTitle, { color: colors.text }]}>Prediction Accuracy</Text>
      </View>
      <View style={styles.predHeader}>
        <Text style={[styles.predHeaderText, { color: colors.muted, flex: 2 }]}>Category</Text>
        <Text style={[styles.predHeaderText, { color: colors.muted, flex: 1, textAlign: 'right' }]}>MAPE</Text>
        <Text style={[styles.predHeaderText, { color: colors.muted, flex: 1, textAlign: 'right' }]}>R²</Text>
      </View>
      {data.slice(0, 8).map((cat) => {
        const r2Color = cat.r2 >= 0.8 ? colors.success : cat.r2 >= 0.5 ? colors.warning : colors.danger;
        return (
          <View key={cat.category} style={[styles.predRow, { borderBottomColor: colors.border }]}>
            <Text style={[styles.predCategory, { color: colors.text }]} numberOfLines={1}>
              {cat.category.replace(/_/g, ' ')}
            </Text>
            <Text style={[styles.predValue, { color: colors.muted }]}>
              {(cat.mape * 100).toFixed(1)}%
            </Text>
            <Text style={[styles.predValue, { color: r2Color, fontWeight: fontWeight.bold }]}>
              {cat.r2.toFixed(2)}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

export const PredictionAccuracySection = React.memo(PredictionAccuracySectionInner);

const styles = StyleSheet.create({
  card: {
    backgroundColor: COLORS.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 16,
    marginBottom: 16,
    ...shadow.card,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: text.lg,
    fontWeight: fontWeight.bold,
    color: COLORS.navy,
  },
  predHeader: {
    flexDirection: 'row',
    paddingBottom: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: COLORS.border,
    marginBottom: 4,
  },
  predHeaderText: {
    fontSize: text.sm,
    fontWeight: fontWeight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  predRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  predCategory: {
    flex: 2,
    fontSize: text.md,
    fontWeight: fontWeight.semibold,
    textTransform: 'capitalize',
  },
  predValue: {
    flex: 1,
    fontSize: text.md,
    textAlign: 'right',
  },
});
