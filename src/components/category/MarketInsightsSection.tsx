/**
 * MarketInsightsSection — the mockup's single compact "CATEGORY MARKET VALUE"
 * card (web/category-redesign-preview.html `.insights`): big average price,
 * trend % beside it, and a tiffany gradient sparkline strip. The old
 * 4-subsection layout (avg card / trend card / Top Traded / Top Movers) is
 * deliberately gone — the redesign keeps insights to one glanceable card.
 */
import React, { useState } from 'react';
import { View, Text, ActivityIndicator, StyleSheet, type LayoutChangeEvent } from 'react-native';
import Svg, { Polyline, Polygon, Circle, Defs, LinearGradient, Stop } from 'react-native-svg';
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
const SPARK_HEIGHT = 44;

const MarketInsightsSection: React.FC<Props> = ({ deepDive, deepDiveLoading, colors }) => {
  const [chartWidth, setChartWidth] = useState(0);

  // Backend contract (GET /analytics/categories/{cat}/deep-dive):
  //   avg_market_price: number                  (MEAN — legacy, see below)
  //   median_market_price / p10 / p90: number|null   (added 2026-08-11)
  //   value_distribution: { ts, value }[]       (daily avg-price timeseries)
  //
  // The headline is the MEDIAN, not the mean. Measured on 30d of prod
  // market_hits: watches mean EUR 7,171.94 vs median EUR 914.24 (7.8x), pokemon
  // mean 14.93 vs median 0.70 (21x). This card said a watch was worth EUR 7,172
  // when a typical one is EUR 914 — a mean over a dispersed catalogue describes
  // no object anyone owns.
  //
  // `avg_market_price` is still read as the fallback so this renders on a server
  // that has not been deployed yet; the field is deliberately kept server-side
  // for builds <= 126 that only know about it.
  const median = typeof deepDive?.median_market_price === 'number' ? (deepDive.median_market_price as number) : null;
  const p10 = typeof deepDive?.p10_market_price === 'number' ? (deepDive.p10_market_price as number) : null;
  const p90 = typeof deepDive?.p90_market_price === 'number' ? (deepDive.p90_market_price as number) : null;
  const avgOnly = typeof deepDive?.avg_market_price === 'number' ? (deepDive.avg_market_price as number) : 0;
  const avgPrice = median ?? avgOnly;
  // p10-p90, not min-max: market_hits carries mis-scraped rows at both ends, and
  // a raw range would be defined by exactly those. Only shown when the two ends
  // actually differ — on a thin category they collapse and would just repeat the
  // median.
  const hasSpread = p10 != null && p90 != null && p90 > p10;
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

  // Full-width sparkline geometry (only computed when we have a real series):
  //   line — the polyline points
  //   area — line + baseline corners, for the soft gradient fill underneath
  //   last — the final point, for the endpoint dot
  const spark =
    hasTrend && chartWidth > 0
      ? (() => {
          const max = Math.max(...series);
          const min = Math.min(...series);
          const range = max - min || 1;
          // Inset so neither the 2.5px stroke nor the 3px endpoint dot clips at
          // the top/bottom/left/right edges of the Svg viewport.
          const PAD = 4;
          const w = chartWidth - PAD * 2;
          const h = SPARK_HEIGHT - PAD * 2;
          const pts = series.map((v, i) => ({
            x: PAD + (i / (series.length - 1)) * w,
            y: PAD + h - ((v - min) / range) * h,
          }));
          const line = pts.map((p) => `${p.x},${p.y}`).join(' ');
          // Close the shape down to the baseline so the gradient fills the area
          // beneath the line, not the whole box.
          const first = pts[0];
          const lastP = pts[pts.length - 1];
          const area = `${line} ${lastP.x},${SPARK_HEIGHT} ${first.x},${SPARK_HEIGHT}`;
          return { line, area, last: lastP };
        })()
      : null;

  return (
    <View style={[styles.card, { backgroundColor: colors.card, borderColor: colors.border }]}>
      <Text style={[styles.label, { color: colors.muted }]}>
        {median != null ? 'TYPICAL MARKET VALUE' : 'CATEGORY MARKET VALUE'}
      </Text>
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
          {/* The spread is the point. A single number hides that watches run
              from EUR 244 to EUR 9,708 — which is exactly why the mean was
              misleading here. */}
          {hasSpread && (
            <Text style={[styles.spread, { color: colors.muted }]}>
              most between {formatPrice(p10 as number)} and {formatPrice(p90 as number)}
            </Text>
          )}
          {/* The context the bare number was missing: what it measures + window.
              Says "median" only when we actually served one — on an undeployed
              server this falls back to the mean and must not mislabel it. */}
          <Text style={[styles.caption, { color: colors.muted }]}>
            {median != null
              ? `Median item price · past ${WINDOW_DAYS} days`
              : `Avg item price · past ${WINDOW_DAYS} days`}
          </Text>
          {/* Real sparkline plotting value_distribution — the line matches the
              %. Hidden when the series is too thin to draw a credible line. */}
          {hasTrend && (
            <View
              style={styles.spark}
              onLayout={(e: LayoutChangeEvent) => setChartWidth(e.nativeEvent.layout.width)}
            >
              {spark && (
                <Svg width={chartWidth} height={SPARK_HEIGHT}>
                  <Defs>
                    <LinearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                      <Stop offset="0" stopColor={trendColor} stopOpacity={0.24} />
                      <Stop offset="1" stopColor={trendColor} stopOpacity={0} />
                    </LinearGradient>
                  </Defs>
                  {/* Soft area fill under the line for depth. */}
                  <Polygon points={spark.area} fill="url(#sparkFill)" stroke="none" />
                  {/* The trend line itself. */}
                  <Polyline
                    points={spark.line}
                    fill="none"
                    stroke={trendColor}
                    strokeWidth="2.5"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                  />
                  {/* Endpoint marker — anchors the eye at the latest value. */}
                  <Circle cx={spark.last.x} cy={spark.last.y} r="3" fill={trendColor} />
                  <Circle cx={spark.last.x} cy={spark.last.y} r="5.5" fill={trendColor} fillOpacity={0.18} />
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
  // 14pt (md), not the 12pt caption: the spread is the substance of this card,
  // not a footnote — docs/ui-playbook.md "a new screen starts at md for body".
  spread: {
    fontSize: 14,
    lineHeight: 19,
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
