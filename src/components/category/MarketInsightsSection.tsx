/**
 * MarketInsightsSection — the mockup's single compact "CATEGORY MARKET VALUE"
 * card (web/category-redesign-preview.html `.insights`): big average price,
 * trend % beside it, and a tiffany gradient sparkline strip. The old
 * 4-subsection layout (avg card / trend card / Top Traded / Top Movers) is
 * deliberately gone — the redesign keeps insights to one glanceable card.
 */
import React from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { formatPrice } from '@/lib/format';
import { colors as tokens } from '@/theme/tokens';
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
  const avgPrice = typeof deepDive?.avg_market_price === 'number' ? (deepDive.avg_market_price as number) : 0;
  const dist = Array.isArray(deepDive?.value_distribution)
    ? (deepDive!.value_distribution as { value?: number }[])
    : [];
  // Trend % from the first vs last non-zero point of the price timeseries.
  const firstVal = Number(dist.find((p) => Number(p?.value) > 0)?.value ?? 0);
  const lastVal = Number([...dist].reverse().find((p) => Number(p?.value) > 0)?.value ?? 0);
  const trendPct = firstVal > 0 && lastVal > 0 ? ((lastVal - firstVal) / firstVal) * 100 : 0;
  const trend: 'up' | 'down' | 'flat' = trendPct > 2 ? 'up' : trendPct < -2 ? 'down' : 'flat';
  const hasData = avgPrice > 0 || dist.length > 0;

  // No insights → no card. An empty "no market value available" banner on
  // every thin category looked broken; the section simply doesn't render.
  if (!deepDiveLoading && !hasData) return null;

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <Text style={[styles.label, { color: colors.muted }]}>CATEGORY MARKET VALUE</Text>
      {deepDiveLoading ? (
        <ActivityIndicator size="small" color={colors.accent} style={{ marginVertical: 12 }} />
      ) : hasData ? (
        <>
          <View style={styles.bigRow}>
            <Text style={[styles.big, { color: colors.text }]}>
              {avgPrice > 0 ? `${formatPrice(avgPrice)} avg` : '—'}
            </Text>
            {trend !== 'flat' && (
              <Text style={[styles.trend, { color: trend === 'up' ? colors.success : colors.error }]}>
                {trend === 'up' ? '▲' : '▼'} {Math.abs(trendPct).toFixed(0)}%
              </Text>
            )}
          </View>
          {/* Mockup `.spark`: 34px gradient strip with a tiffany baseline. */}
          {dist.length > 0 && (
            <LinearGradient
              colors={['#81D8D020', '#81D8D000']}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={styles.spark}
            />
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
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    marginBottom: 20,
  },
  label: {
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.4,
  },
  bigRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 8,
    marginTop: 2,
  },
  big: {
    fontSize: 24,
    fontWeight: '900',
  },
  trend: {
    fontSize: 12,
    fontWeight: '700',
  },
  spark: {
    height: 34,
    marginTop: 6,
    borderBottomWidth: 2,
    borderBottomColor: tokens.brand.base,
    borderRadius: 4,
  },
  emptyText: {
    fontSize: 13,
    marginTop: 6,
  },
});
