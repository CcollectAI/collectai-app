/**
 * MarketInsightsSection — the mockup's single compact "CATEGORY MARKET VALUE"
 * card (web/category-redesign-preview.html `.insights`): big average price,
 * trend % beside it, and a tiffany gradient sparkline strip. The old
 * 4-subsection layout (avg card / trend card / Top Traded / Top Movers) is
 * deliberately gone — the redesign keeps insights to one glanceable card.
 */
import React, { useState } from 'react';
import { View, Text, ActivityIndicator, StyleSheet, type LayoutChangeEvent } from 'react-native';
import Svg, { Polyline } from 'react-native-svg';
import { formatPrice } from '@/lib/format';
import { colors as tokens } from '@/theme/tokens';
import type { AppTheme } from '@/hooks/useAppTheme';

type Props = {
  deepDive: Record<string, unknown> | null;
  deepDiveLoading: boolean;
  colors: AppTheme['colors'];
};

// The screen fetches the deep-dive with no `days` override, so the backend
// default window applies (trends_and_deepdive_router.py: days=Query(30)). Keep
// this label in sync if that default ever changes.
const WINDOW_DAYS = 30;
// Below this many real (>0) daily points, a single-line "trend" and a plotted
// sparkline are just noise off one or two samples — we show the average alone.
const MIN_POINTS_FOR_TREND = 3;
const SPARK_HEIGHT = 34;

const MarketInsightsSection: React.FC<Props> = ({ deepDive, deepDiveLoading, colors }) => {
  const [chartWidth, setChartWidth] = useState(0);

  // Backend contract (GET /analytics/categories/{cat}/deep-dive):
  //   avg_market_price: number                  (avg item price over WINDOW_DAYS)
  //   value_distribution: { ts, value }[]       (daily avg-price timeseries)
  const avgPrice = typeof deepDive?.avg_market_price === 'number' ? (deepDive.avg_market_price as number) : 0;
  const dist = Array.isArray(deepDive?.value_distribution)
    ? (deepDive!.value_distribution as { value?: number }[])
    : [];

  // Real price series: drop empty/zero days (no data that day) so the line and
  // the trend reflect actual observed prices, not floor-spikes.
  const series = dist
    .map((p) => Number(p?.value))
    .filter((v) => Number.isFinite(v) && v > 0);
  const hasTrend = series.length >= MIN_POINTS_FOR_TREND;

  // Trend % = first vs last real point across the window.
  const firstVal = series[0] ?? 0;
  const lastVal = series[series.length - 1] ?? 0;
  const trendPct = hasTrend && firstVal > 0 ? ((lastVal - firstVal) / firstVal) * 100 : 0;
  const trend: 'up' | 'down' | 'flat' = trendPct > 2 ? 'up' : trendPct < -2 ? 'down' : 'flat';
  const trendColor = trend === 'up' ? colors.success : trend === 'down' ? colors.error : tokens.brand.base;

  const hasData = avgPrice > 0 || series.length > 0;

  // No insights → no card. An empty "no market value available" banner on
  // every thin category looked broken; the section simply doesn't render.
  if (!deepDiveLoading && !hasData) return null;

  // Full-width sparkline points (only plotted when we have a real series).
  const sparkPoints =
    hasTrend && chartWidth > 0
      ? (() => {
          const max = Math.max(...series);
          const min = Math.min(...series);
          const range = max - min || 1;
          return series
            .map((v, i) => {
              const x = (i / (series.length - 1)) * chartWidth;
              const y = SPARK_HEIGHT - ((v - min) / range) * SPARK_HEIGHT;
              return `${x},${y}`;
            })
            .join(' ');
        })()
      : '';

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <Text style={[styles.label, { color: colors.muted }]}>CATEGORY MARKET VALUE</Text>
      {deepDiveLoading ? (
        <ActivityIndicator size="small" color={colors.accent} style={{ marginVertical: 12 }} />
      ) : hasData ? (
        <>
          <View style={styles.bigRow}>
            <Text style={[styles.big, { color: colors.text }]}>
              {avgPrice > 0 ? formatPrice(avgPrice) : '—'}
            </Text>
            {hasTrend && trend !== 'flat' && (
              <Text style={[styles.trend, { color: trendColor }]}>
                {trend === 'up' ? '▲' : '▼'} {Math.abs(trendPct).toFixed(0)}%
              </Text>
            )}
          </View>
          {/* The context the bare number was missing: what it averages + window. */}
          <Text style={[styles.caption, { color: colors.muted }]}>
            {`Avg item price · past ${WINDOW_DAYS} days`}
          </Text>
          {/* Real sparkline plotting value_distribution — the line matches the
              %. Hidden when the series is too thin to draw a credible line. */}
          {hasTrend && (
            <View
              style={styles.spark}
              onLayout={(e: LayoutChangeEvent) => setChartWidth(e.nativeEvent.layout.width)}
            >
              {sparkPoints !== '' && (
                <Svg width={chartWidth} height={SPARK_HEIGHT}>
                  <Polyline
                    points={sparkPoints}
                    fill="none"
                    stroke={trendColor}
                    strokeWidth="2"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                  />
                </Svg>
              )}
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
  caption: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.2,
    marginTop: 2,
  },
  spark: {
    height: SPARK_HEIGHT,
    marginTop: 8,
    justifyContent: 'flex-end',
  },
  emptyText: {
    fontSize: 13,
    marginTop: 6,
  },
});
