/**
 * InsightsCard Component
 * Displays portfolio insights with key metrics.
 */

import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { PortfolioInsights, ItemMover } from '@/types/insights';

type InsightsCardProps = {
  insights: PortfolioInsights;
  onViewDetails?: () => void;
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function MoverItem({ item, colors }: { item: ItemMover; colors: any }) {
  const isPositive = item.percentChange >= 0;

  return (
    <View style={styles.moverRow}>
      <View style={styles.moverInfo}>
        <Text style={[styles.moverName, { color: colors.text }]} numberOfLines={1}>
          {item.name}
        </Text>
        <Text style={[styles.moverCategory, { color: colors.muted }]}>
          {item.category}
        </Text>
      </View>
      <View style={styles.moverValue}>
        <Text style={[styles.moverPrice, { color: colors.text }]}>
          {formatCurrency(item.currentValue)}
        </Text>
        <Text
          style={[
            styles.moverChange,
            { color: isPositive ? '#0BA86C' : '#EF4444' },
          ]}
        >
          {formatPercent(item.percentChange)}
        </Text>
      </View>
    </View>
  );
}

export function InsightsCard({ insights, onViewDetails }: InsightsCardProps) {
  const { colors } = useAppTheme();
  const isPositive = insights.percentChange >= 0;

  return (
    <View
      style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}
      accessibilityRole="summary"
      accessibilityLabel={`Portfolio insights: ${formatCurrency(insights.totalValue)} total value, ${formatPercent(insights.percentChange)} change`}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Ionicons name="analytics-outline" size={18} color={colors.accent} />
          <Text style={[styles.title, { color: colors.text }]}>Portfolio Insights</Text>
        </View>
        <Text style={[styles.period, { color: colors.muted }]}>
          Last {insights.period === '7d' ? '7 days' : insights.period === '30d' ? '30 days' : '90 days'}
        </Text>
      </View>

      {/* Main Stats */}
      <View style={styles.statsRow}>
        <View style={styles.statBlock}>
          <Text style={[styles.statLabel, { color: colors.muted }]}>Total Value</Text>
          <Text style={[styles.statValue, { color: colors.text }]}>
            {formatCurrency(insights.totalValue)}
          </Text>
        </View>
        <View style={styles.statBlock}>
          <Text style={[styles.statLabel, { color: colors.muted }]}>Change</Text>
          <View style={styles.changeRow}>
            <Ionicons
              name={isPositive ? 'trending-up' : 'trending-down'}
              size={16}
              color={isPositive ? '#0BA86C' : '#EF4444'}
            />
            <Text
              style={[
                styles.changeValue,
                { color: isPositive ? '#0BA86C' : '#EF4444' },
              ]}
            >
              {formatPercent(insights.percentChange)}
            </Text>
          </View>
        </View>
      </View>

      {/* Top Movers */}
      {insights.topGainers.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Top Gainers</Text>
          {insights.topGainers.slice(0, 2).map((item) => (
            <MoverItem key={item.itemId} item={item} colors={colors} />
          ))}
        </View>
      )}

      {insights.topLosers.length > 0 && (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Top Losers</Text>
          {insights.topLosers.slice(0, 2).map((item) => (
            <MoverItem key={item.itemId} item={item} colors={colors} />
          ))}
        </View>
      )}

      {/* Watchlist Summary */}
      {insights.watchlistSummary.belowTargetCount > 0 && (
        <View style={[styles.watchlistBanner, { backgroundColor: colors.accent + '15' }]}>
          <Ionicons name="eye-outline" size={16} color={colors.accent} />
          <Text style={[styles.watchlistText, { color: colors.text }]}>
            {insights.watchlistSummary.belowTargetCount} item
            {insights.watchlistSummary.belowTargetCount > 1 ? 's' : ''} below target price
          </Text>
        </View>
      )}

      {/* View Details */}
      {onViewDetails && (
        <Pressable
          style={styles.viewDetails}
          onPress={onViewDetails}
          accessibilityRole="button"
          accessibilityLabel="View full insights"
        >
          <Text style={[styles.viewDetailsText, { color: colors.accent }]}>
            View Full Insights
          </Text>
          <Ionicons name="chevron-forward" size={16} color={colors.accent} />
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
  },
  period: {
    fontSize: 12,
  },
  statsRow: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  statBlock: {
    flex: 1,
  },
  statLabel: {
    fontSize: 12,
    marginBottom: 4,
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
  },
  changeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  changeValue: {
    fontSize: 18,
    fontWeight: '600',
  },
  section: {
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  moverRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
  },
  moverInfo: {
    flex: 1,
    marginRight: 12,
  },
  moverName: {
    fontSize: 13,
    fontWeight: '500',
  },
  moverCategory: {
    fontSize: 11,
  },
  moverValue: {
    alignItems: 'flex-end',
  },
  moverPrice: {
    fontSize: 13,
    fontWeight: '500',
  },
  moverChange: {
    fontSize: 12,
    fontWeight: '600',
  },
  watchlistBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 10,
    borderRadius: 8,
    marginTop: 4,
    marginBottom: 12,
  },
  watchlistText: {
    fontSize: 13,
    fontWeight: '500',
  },
  viewDetails: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(0,0,0,0.1)',
  },
  viewDetailsText: {
    fontSize: 14,
    fontWeight: '600',
  },
});

export default InsightsCard;
