import React from 'react';
import { View, Text, ScrollView, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { formatPrice } from '@/lib/format';
import type { AppTheme } from '@/hooks/useAppTheme';

type Props = {
  deepDive: Record<string, unknown> | null;
  deepDiveLoading: boolean;
  colors: AppTheme['colors'];
};

const MarketInsightsSection: React.FC<Props> = ({ deepDive, deepDiveLoading, colors }) => {
  // Backend contract (GET /analytics/categories/{cat}/deep-dive):
  //   avg_market_price: number
  //   value_distribution: { ts, value }[]   (daily avg-price timeseries)
  //   top_traded_items:   { item_id, name, trades }[]
  //   top_movers:         { item_id, name, change_pct }[]
  // This component previously read `average_market_price` / `value_distribution.trend`
  // / `trade_count` — none of which the backend emits — so real data rendered blank.
  const avgPrice = typeof deepDive?.avg_market_price === 'number' ? (deepDive.avg_market_price as number) : 0;
  const dist = Array.isArray(deepDive?.value_distribution)
    ? (deepDive!.value_distribution as { value?: number }[])
    : [];
  // Derive a trend from the first vs last non-zero point of the price timeseries.
  const firstVal = Number(dist.find((p) => Number(p?.value) > 0)?.value ?? 0);
  const lastVal = Number([...dist].reverse().find((p) => Number(p?.value) > 0)?.value ?? 0);
  const trend: 'up' | 'down' | 'flat' =
    firstVal > 0 && lastVal > 0
      ? lastVal > firstVal * 1.02
        ? 'up'
        : lastVal < firstVal * 0.98
        ? 'down'
        : 'flat'
      : 'flat';
  const topTraded = Array.isArray(deepDive?.top_traded_items)
    ? (deepDive!.top_traded_items as Record<string, unknown>[])
    : [];
  const topMovers = Array.isArray(deepDive?.top_movers)
    ? (deepDive!.top_movers as Record<string, unknown>[])
    : [];
  const hasAnyData = avgPrice > 0 || dist.length > 0 || topTraded.length > 0 || topMovers.length > 0;

  return (
  <View style={styles.section}>
    <Text style={[styles.sectionTitle, { color: colors.text }]}>Market Insights</Text>
    {deepDiveLoading ? (
      <ActivityIndicator size="small" color={colors.accent} style={{ marginVertical: 12 }} />
    ) : deepDive && hasAnyData ? (
      <>
        {/* Average Market Price */}
        {avgPrice > 0 && (
          <View style={[styles.insightCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[styles.insightLabel, { color: colors.muted }]}>Average Market Price</Text>
            <Text style={[styles.insightValue, { color: colors.text }]}>
              {formatPrice(avgPrice)}
            </Text>
          </View>
        )}

        {/* Price Trend */}
        {dist.length > 0 && (
          <View style={[styles.insightCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <Text style={[styles.insightLabel, { color: colors.muted }]}>Price Trend</Text>
            <View style={styles.trendRow}>
              <Ionicons
                name={trend === 'up' ? 'trending-up' : trend === 'down' ? 'trending-down' : 'remove-outline'}
                size={18}
                color={trend === 'up' ? colors.success : trend === 'down' ? colors.error : colors.muted}
              />
              <Text style={[styles.trendText, {
                color: trend === 'up' ? colors.success : trend === 'down' ? colors.error : colors.muted,
              }]}>
                {trend === 'up' ? 'Prices trending up' : trend === 'down' ? 'Prices trending down' : 'Prices stable'}
              </Text>
            </View>
          </View>
        )}

        {/* Top Traded Items */}
        {topTraded.length > 0 && (
          <View style={styles.insightSubSection}>
            <Text style={[styles.insightSubTitle, { color: colors.text }]}>Top Traded Items</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.topTradedRow}>
              {topTraded.map((item, idx) => (
                <View
                  key={String(item.item_id ?? item.id ?? idx)}
                  style={[styles.topTradedCard, { backgroundColor: colors.card, borderColor: colors.border }]}
                >
                  <Text style={[styles.topTradedName, { color: colors.text }]} numberOfLines={2}>
                    {String(item.name ?? item.title ?? 'Unknown')}
                  </Text>
                  <Text style={[styles.topTradedCount, { color: colors.muted }]}>
                    {String(item.trades ?? item.trade_count ?? 0)} trades
                  </Text>
                </View>
              ))}
            </ScrollView>
          </View>
        )}

        {/* Top Movers */}
        {topMovers.length > 0 && (
          <View style={styles.insightSubSection}>
            <Text style={[styles.insightSubTitle, { color: colors.text }]}>Top Movers</Text>
            {topMovers.map((mover, idx) => {
              const changePct = Number(mover.change_pct ?? mover.changePct ?? 0) * 100;
              const isPositive = changePct >= 0;
              return (
                <View
                  key={String(mover.item_id ?? mover.id ?? idx)}
                  style={[styles.moverRow, { borderBottomColor: colors.border }]}
                >
                  <Text style={[styles.moverName, { color: colors.text }]} numberOfLines={1}>
                    {String(mover.name ?? mover.title ?? 'Unknown')}
                  </Text>
                  <Text style={[styles.moverPct, { color: isPositive ? colors.success : colors.error }]}>
                    {isPositive ? '+' : ''}{changePct.toFixed(1)}%
                  </Text>
                </View>
              );
            })}
          </View>
        )}
      </>
    ) : (
      <Text style={[styles.emptyText, { color: colors.muted }]}>
        No market insights available for this category yet.
      </Text>
    )}
  </View>
  );
};

export default React.memo(MarketInsightsSection);

const styles = StyleSheet.create({
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  emptyText: {
    fontSize: 13,
  },
  insightCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 8,
  },
  insightLabel: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  insightValue: {
    fontSize: 24,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  trendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 4,
  },
  trendText: {
    fontSize: 14,
    fontWeight: '600',
  },
  insightSubSection: {
    marginTop: 8,
  },
  insightSubTitle: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  topTradedRow: {
    gap: 10,
  },
  topTradedCard: {
    width: 140,
    borderRadius: 10,
    borderWidth: 1,
    padding: 10,
  },
  topTradedName: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 4,
  },
  topTradedCount: {
    fontSize: 11,
  },
  moverRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  moverName: {
    flex: 1,
    fontSize: 13,
    fontWeight: '500',
    marginRight: 8,
  },
  moverPct: {
    fontSize: 13,
    fontWeight: '700',
  },
});
