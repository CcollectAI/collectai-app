/**
 * PriceTrendChart — renders a price trend line chart for an item.
 *
 * Uses react-native-svg (already installed) to draw:
 * - q50 line (primary Tiffany Blue)
 * - q10-q90 shaded band (light accent fill)
 * - Date axis labels
 * - Direction indicator and percentage change
 *
 * Fetches data via the useItemPriceTrend hook (already wired to
 * GET /predict/trend/{item_id}).
 */

import React, { useMemo, useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  Pressable,
  LayoutChangeEvent,
} from "react-native";
import Svg, { Path, Line, Circle } from "react-native-svg";
import { Ionicons } from "@expo/vector-icons";
import { useAppTheme } from "@/hooks/useAppTheme";
import { useItemPriceTrend } from "@/hooks/useItemPriceTrend";
import { formatPrice } from "@/lib/format";
import { fireHaptic, HapticIntent } from "@/haptics";
import { useSettings } from "@/lib/settings";
import { radius, text as textTokens, fontWeight, gap } from "@/theme/tokens";

// ── Types ────────────────────────────────────────────────────────────────

interface PriceTrendChartProps {
  itemId: string;
}

// ── Range options ────────────────────────────────────────────────────────

const RANGE_OPTIONS = [
  { label: "30D", days: 30 },
  { label: "90D", days: 90 },
  { label: "1Y", days: 365 },
] as const;

// ── Helpers ──────────────────────────────────────────────────────────────

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

function buildLinePath(
  values: number[],
  width: number,
  height: number,
  min: number,
  span: number,
): string {
  if (!values.length || width <= 0) return "";
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  let d = "";
  values.forEach((v, i) => {
    const x = step * i;
    const norm = span > 0 ? (v - min) / span : 0.5;
    const y = height - norm * height;
    d += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
  });
  return d;
}

function buildBandPath(
  q10s: (number | null)[],
  q90s: (number | null)[],
  q50s: number[],
  width: number,
  height: number,
  min: number,
  span: number,
): string {
  if (!q50s.length || width <= 0 || span <= 0) return "";
  const step = q50s.length > 1 ? width / (q50s.length - 1) : 0;
  const toY = (v: number) => height - ((v - min) / span) * height;

  // Upper edge (q90, left to right)
  let d = "";
  q50s.forEach((_, i) => {
    const x = step * i;
    const upper = q90s[i] ?? q50s[i];
    const y = toY(upper);
    d += i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
  });

  // Lower edge (q10, right to left)
  for (let i = q50s.length - 1; i >= 0; i--) {
    const x = step * i;
    const lower = q10s[i] ?? q50s[i];
    const y = toY(lower);
    d += ` L ${x} ${y}`;
  }

  d += " Z";
  return d;
}

// ── Component ────────────────────────────────────────────────────────────

function PriceTrendChartInner({ itemId }: PriceTrendChartProps) {
  const { colors } = useAppTheme();
  const { settings } = useSettings();
  const [chartWidth, setChartWidth] = useState(0);

  const trend = useItemPriceTrend(itemId, false);
  const {
    priceTrendData,
    priceTrendLoading,
    priceTrendRange,
    priceTrendVisible,
    setPriceTrendVisible,
    handleRangeChange,
  } = trend;

  // Auto-expand on mount
  React.useEffect(() => {
    if (!priceTrendVisible) {
      setPriceTrendVisible(true);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const CHART_HEIGHT = 160;

  const handleLayout = useCallback((e: LayoutChangeEvent) => {
    setChartWidth(e.nativeEvent.layout.width);
  }, []);

  // Extract data arrays
  const { q50s, q10s, q90s, dates } = useMemo(() => {
    const points = priceTrendData?.data_points ?? [];
    return {
      q50s: points.map((p) => p.q50),
      q10s: points.map((p) => (p.q10 != null ? p.q10 : null)),
      q90s: points.map((p) => (p.q90 != null ? p.q90 : null)),
      dates: points.map((p) => p.date),
    };
  }, [priceTrendData]);

  // Compute min/max across all quantiles for consistent scaling
  const { min, max, span } = useMemo(() => {
    if (!q50s.length) return { min: 0, max: 1, span: 1 };
    const allVals = [
      ...q50s,
      ...q10s.filter((v): v is number => v != null),
      ...q90s.filter((v): v is number => v != null),
    ];
    const localMin = Math.min(...allVals);
    const localMax = Math.max(...allVals);
    const localSpan = localMax - localMin || 1;
    return { min: localMin, max: localMax, span: localSpan };
  }, [q50s, q10s, q90s]);

  // SVG paths
  const linePath = useMemo(
    () => buildLinePath(q50s, chartWidth, CHART_HEIGHT, min, span),
    [q50s, chartWidth, min, span],
  );

  const bandPath = useMemo(
    () => buildBandPath(q10s, q90s, q50s, chartWidth, CHART_HEIGHT, min, span),
    [q10s, q90s, q50s, chartWidth, min, span],
  );

  // Direction indicator
  const direction = priceTrendData?.direction ?? "flat";
  const pctChange = priceTrendData?.pct_change ?? 0;
  const directionIcon =
    direction === "up" ? "trending-up" : direction === "down" ? "trending-down" : "remove-outline";
  const directionColor =
    direction === "up" ? colors.success : direction === "down" ? colors.danger : colors.muted;

  const hasData = q50s.length >= 2;

  return (
    <View style={[styles.container, { backgroundColor: colors.card, borderColor: colors.border }]}>
      {/* Header */}
      <View style={styles.headerRow}>
        <View style={styles.headerLeft}>
          <Ionicons name="analytics-outline" size={18} color={colors.accent} />
          <Text style={[styles.headerTitle, { color: colors.text }]}>Price Trend</Text>
        </View>
        {hasData && (
          <View style={[styles.directionBadge, { backgroundColor: directionColor + "15" }]}>
            <Ionicons name={directionIcon as keyof typeof Ionicons.glyphMap} size={14} color={directionColor} />
            <Text style={[styles.directionText, { color: directionColor }]}>
              {pctChange > 0 ? "+" : ""}
              {pctChange.toFixed(1)}%
            </Text>
          </View>
        )}
      </View>

      {/* Range selector */}
      <View style={styles.rangeRow}>
        {RANGE_OPTIONS.map((opt) => {
          const active = priceTrendRange === opt.days;
          return (
            <Pressable
              key={opt.label}
              onPress={() => handleRangeChange(opt.days)}
              style={[
                styles.rangeBtn,
                {
                  backgroundColor: active ? colors.accent : colors.background,
                  borderColor: active ? colors.accent : colors.border,
                },
              ]}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              accessibilityLabel={`Show ${opt.label} price trend`}
            >
              <Text
                style={[
                  styles.rangeBtnText,
                  { color: active ? colors.accentText : colors.muted },
                ]}
              >
                {opt.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {/* Chart area */}
      {priceTrendLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color={colors.accent} />
          <Text style={[styles.loadingText, { color: colors.muted }]}>Loading price data...</Text>
        </View>
      ) : !hasData ? (
        <View style={styles.emptyContainer}>
          <Ionicons name="bar-chart-outline" size={32} color={colors.muted + "60"} />
          <Text style={[styles.emptyText, { color: colors.muted }]}>
            Not enough price data yet
          </Text>
          <Text style={[styles.emptySubtext, { color: colors.muted + "80" }]}>
            Price history will appear as more data is collected
          </Text>
        </View>
      ) : (
        <View onLayout={handleLayout} style={styles.chartContainer}>
          {chartWidth > 0 && (
            <>
              {/* Y-axis labels */}
              <View pointerEvents="none" style={styles.yLabels}>
                <Text style={[styles.axisText, { color: colors.muted }]}>
                  {formatPrice(max)}
                </Text>
                <Text style={[styles.axisText, { color: colors.muted }]}>
                  {formatPrice(min)}
                </Text>
              </View>

              <Svg height={CHART_HEIGHT} width={chartWidth}>
                {/* Grid lines */}
                <Line
                  x1={0} y1={CHART_HEIGHT} x2={chartWidth} y2={CHART_HEIGHT}
                  stroke={colors.border} strokeWidth={1}
                />
                <Line
                  x1={0} y1={CHART_HEIGHT / 2} x2={chartWidth} y2={CHART_HEIGHT / 2}
                  stroke={colors.border + "60"} strokeWidth={1}
                />

                {/* q10-q90 confidence band */}
                {bandPath ? (
                  <Path d={bandPath} fill={colors.accent + "18"} stroke="none" />
                ) : null}

                {/* q50 line */}
                {linePath ? (
                  <Path d={linePath} fill="none" stroke={colors.accent} strokeWidth={2.5} />
                ) : null}

                {/* End dot */}
                {q50s.length > 0 && (() => {
                  const lastIdx = q50s.length - 1;
                  const step = lastIdx > 0 ? chartWidth / lastIdx : 0;
                  const cx = step * lastIdx;
                  const norm = span > 0 ? (q50s[lastIdx] - min) / span : 0.5;
                  const cy = CHART_HEIGHT - norm * CHART_HEIGHT;
                  return (
                    <Circle cx={cx} cy={cy} r={4} fill={colors.card} stroke={colors.accent} strokeWidth={2} />
                  );
                })()}
              </Svg>

              {/* X-axis labels */}
              <View style={styles.xLabels}>
                <Text style={[styles.axisText, { color: colors.muted }]}>
                  {formatDateLabel(dates[0])}
                </Text>
                <Text style={[styles.axisText, { color: colors.muted }]}>
                  {formatDateLabel(dates[dates.length - 1])}
                </Text>
              </View>
            </>
          )}
        </View>
      )}

      {/* Current price footer */}
      {hasData && priceTrendData?.current_q50 != null && (
        <View style={[styles.footer, { borderTopColor: colors.border }]}>
          <Text style={[styles.footerLabel, { color: colors.muted }]}>Current estimate</Text>
          <Text style={[styles.footerValue, { color: colors.text }]}>
            {formatPrice(priceTrendData.current_q50)}
          </Text>
        </View>
      )}
    </View>
  );
}

export const PriceTrendChart = React.memo(PriceTrendChartInner);
PriceTrendChart.displayName = "PriceTrendChart";

// ── Styles ───────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 16,
    marginTop: 12,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  headerTitle: {
    fontSize: textTokens.lg,
    fontWeight: fontWeight.bold,
  },
  directionBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radius.xs,
  },
  directionText: {
    fontSize: textTokens.sm,
    fontWeight: fontWeight.semibold,
  },
  rangeRow: {
    flexDirection: "row",
    gap: gap.sm,
    marginBottom: 12,
  },
  rangeBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: radius.xs,
    borderWidth: 1,
  },
  rangeBtnText: {
    fontSize: textTokens.sm,
    fontWeight: fontWeight.semibold,
  },
  chartContainer: {
    position: "relative",
    paddingBottom: 20,
    minHeight: 180,
  },
  yLabels: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 2,
    bottom: 20,
    justifyContent: "space-between",
    zIndex: 20,
  },
  xLabels: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 4,
  },
  axisText: {
    fontSize: 10,
    fontWeight: fontWeight.semibold,
  },
  loadingContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 40,
    gap: 8,
  },
  loadingText: {
    fontSize: textTokens.sm,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 32,
    gap: 6,
  },
  emptyText: {
    fontSize: textTokens.md,
    fontWeight: fontWeight.medium,
    marginTop: 4,
  },
  emptySubtext: {
    fontSize: textTokens.sm,
    textAlign: "center",
    maxWidth: 240,
  },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: 10,
    marginTop: 10,
  },
  footerLabel: {
    fontSize: textTokens.sm,
    fontWeight: fontWeight.medium,
  },
  footerValue: {
    fontSize: textTokens.lg,
    fontWeight: fontWeight.bold,
  },
});
