/**
 * WinnersLosersSection — Shows top winners and losers by 24h price change.
 * Extracted from analytics.tsx.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import type { PortfolioItemSnapshot } from '@/analytics/portfolioMetrics';
import { radius, text, fontWeight, shadow } from '@/theme/tokens';

const COLORS = {
  card: '#FFFFFF',
  navy: '#0F172A',
  muted: '#64748B',
  border: '#E2E8F0',
  success: '#10B981',
  danger: '#EF4444',
};

function formatPct(p: number, includeSign = true): string {
  const sign = includeSign && p > 0 ? '+' : '';
  return `${sign}${(p * 100).toFixed(2)}%`;
}

type Props = {
  winners: PortfolioItemSnapshot[];
  losers: PortfolioItemSnapshot[];
};

function WinnersLosersSectionInner({ winners, losers }: Props) {
  const { colors } = useAppTheme();

  if (winners.length === 0 && losers.length === 0) return null;

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>Movers</Text>
        <Text style={styles.cardSubtitle}>24h change</Text>
      </View>

      {/* Winners */}
      {winners.length > 0 && (
        <View style={styles.moversSection}>
          <View style={styles.moversSectionHeader}>
            <Ionicons name="trending-up" size={16} color={colors.success} />
            <Text style={[styles.moversSectionTitle, { color: colors.success }]}>Winners</Text>
          </View>
          {winners.slice(0, 3).map((item) => (
            <View key={item.id} style={styles.moverRow}>
              <Text style={styles.moverName} numberOfLines={1}>{item.name}</Text>
              <Text style={[styles.moverPct, styles.textSuccess]}>
                {formatPct(item.change1dPct ?? 0)}
              </Text>
            </View>
          ))}
        </View>
      )}

      {/* Losers */}
      {losers.length > 0 && (
        <View style={styles.moversSection}>
          <View style={styles.moversSectionHeader}>
            <Ionicons name="trending-down" size={16} color={colors.error} />
            <Text style={[styles.moversSectionTitle, { color: colors.error }]}>Losers</Text>
          </View>
          {losers.slice(0, 3).map((item) => (
            <View key={item.id} style={styles.moverRow}>
              <Text style={styles.moverName} numberOfLines={1}>{item.name}</Text>
              <Text style={[styles.moverPct, styles.textDanger, { color: colors.danger }]}>
                {formatPct(item.change1dPct ?? 0)}
              </Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

export const WinnersLosersSection = React.memo(WinnersLosersSectionInner);

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
  cardSubtitle: {
    fontSize: text.md,
    color: COLORS.muted,
  },
  moversSection: {
    marginBottom: 16,
  },
  moversSectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  moversSectionTitle: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
  },
  moverRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  moverName: {
    flex: 1,
    fontSize: text.md,
    color: COLORS.navy,
    marginRight: 12,
  },
  moverPct: {
    fontSize: text.md,
    fontWeight: fontWeight.bold,
  },
  textSuccess: {
    color: COLORS.success,
  },
  textDanger: {
    color: COLORS.danger,
  },
});
