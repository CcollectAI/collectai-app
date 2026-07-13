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

// Window the deep-dive aggregates over (server default `days=30`). Surfaced so
// the average and the % change are not context-free numbers.
const WINDOW_DAYS = 30;

const MarketInsightsSection: React.FC<Props> = ({ deepDive, deepDiveLoading, colors }) => {
  // Backend contract (GET /analytics/categories/{cat}/deep-dive):
  //   avg_market_price: number                 (mean of marketplace listings + sold comps, last 30d)
  //   value_distribution: { ts, value }[]      (daily avg-price timeseries)
  //   volume_trend: { ts, value }[]            (daily observation counts → sample size)
  const avgPrice = typeof deepDive?.avg_market_price === 'number' ? (deepDive.avg_market_price as number) : 0;
  const dist = Array.isArray(deepDive?.value_distribution)
    ? (deepDive!.value_distribution as { value?: number }[])
    : [];
  const volume = Array.isArray(deepDive?.volume_trend)
    ? (deepDive!.volume_trend as { value?: number }[])
    : [];
  // How many market observations (listings + sales) the average is based on.
  const sampleCount = volume.reduce((sum, p) => sum + (Number(p?.value) || 0), 0);

  // Trend % = first vs last non-zero point of the daily price timeseries, i.e.
  // how the average has moved across the window ("vs. 30 days ago").
  const firstVal = Number(dist.find((p) => Number(p?.value) > 0)?.value ?? 0);
  const lastVal = Number([...dist].reverse().find((p) => Number(p?.value) > 0)?.value ?? 0);
  const trendPct = firstVal > 0 && lastVal > 0 ? ((lastVal - firstVal) / firstVal) * 100 : 0;
  const trend: 'up' | 'down' | 'flat' = trendPct > 2 ? 'up' : trendPct < -2 ? 'down' : 'flat';
  const hasData = avgPrice > 0 || dist.length > 0;

  // No insights → no section. An empty "no market value available" banner on
  // every thin category looked broken; the section simply doesn't render.
  if (!deepDiveLoading && !hasData) return null;

  const basisLine =
    sampleCount > 0
      ? `Avg. of ${sampleCount.toLocaleString()} marketplace listings & sales · last ${WINDOW_DAYS} days`
      : `Avg. of marketplace listings & sales · last ${WINDOW_DAYS} days`;

  return (
    <View style={styles.section}>
      <Text style={[styles.sectionTitle, { color: colors.text }]}>Market Value</Text>
      <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
        {deepDiveLoading ? (
          <ActivityIndicator size="small" color={colors.accent} style={{ marginVertical: 12 }} />
        ) : (
          <>
            <View style={styles.bigRow}>
              <Text style={[styles.big, { color: colors.text }]}>
                {avgPrice > 0 ? formatPrice(avgPrice) : '—'}
              </Text>
              <Text style={[styles.avgSuffix, { color: colors.muted }]}>avg</Text>
              {trend !== 'flat' && (
                <Text style={[styles.trend, { color: trend === 'up' ? colors.success : colors.error }]}>
                  {trend === 'up' ? '▲' : '▼'} {Math.abs(trendPct).toFixed(0)}%
                </Text>
              )}
            </View>

            {/* Context: what the number is, what it's based on, and what the %
                is measured against — so it doesn't read as a bare figure. */}
            <Text style={[styles.caption, { color: colors.muted }]}>{basisLine}</Text>
            {trend !== 'flat' && (
              <Text style={[styles.caption, { color: colors.muted }]}>
                {`${trend === 'up' ? 'Up' : 'Down'} ${Math.abs(trendPct).toFixed(0)}% vs. ${WINDOW_DAYS} days ago`}
              </Text>
            )}

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
        )}
      </View>
    </View>
  );
};

export default React.memo(MarketInsightsSection);

const styles = StyleSheet.create({
  // Match the page's other sections (CategoryEventsSection / RelatedCategories):
  // Title Case header at 15/700, then a card wrapper, 20 bottom gap.
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
  },
  bigRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 6,
  },
  big: {
    fontSize: 26,
    fontWeight: '900',
  },
  avgSuffix: {
    fontSize: 13,
    fontWeight: '600',
  },
  trend: {
    fontSize: 13,
    fontWeight: '700',
    marginLeft: 2,
  },
  caption: {
    fontSize: 12,
    marginTop: 4,
    lineHeight: 16,
  },
  spark: {
    height: 34,
    marginTop: 10,
    borderBottomWidth: 2,
    borderBottomColor: tokens.brand.base,
    borderRadius: 4,
  },
});
