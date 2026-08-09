import React, { useMemo, useState } from "react";
import { LayoutChangeEvent, Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Line, Path, Text as SvgText } from "react-native-svg";
import { formatPrice } from "@/lib/format";

export type TimeSeriesPoint = {
  t: string; // ISO timestamp
  v: number; // portfolio value
};

export type PortfolioLineChartProps = {
  series: TimeSeriesPoint[];
  accentColor?: string;

  /** If false, removes internal "value header" inside chart */
  showValueHeader?: boolean;

  /** If true, shows axis labels */
  showAxisLabels?: boolean;

  /** Optional override for axis label color */
  axisLabelColor?: string;

  /** Optional override for grid line color */
  gridColor?: string;

  /** Optional override for value/date header text */
  textColor?: string;

  /** Fill color for the hover dot (defaults to parent card background) */
  dotFillColor?: string;

  /**
   * The series is empty because the request FAILED, not because there is no
   * history. Without this the chart claims "No history yet" for both, so a
   * cold-start 401 reads as "you own nothing" — the exact confusion the
   * ui-playbook's "Empty is not loading" rule exists to prevent.
   */
  loadFailed?: boolean;

  /** Retry handler shown alongside the failure message. */
  onRetry?: () => void;

  /**
   * Fires with the point under the user's finger while scrubbing, and with null
   * on release. Lets the screen's big "COLLECTION VALUE" figure track the
   * scrubber instead of sitting frozen on the latest value.
   */
  onScrubChange?: (point: TimeSeriesPoint | null) => void;
};

/** Vertical inset of the plot area, in px. Must clear the hover dot (r=4 plus a
 *  2px stroke) and half the 2.5px line stroke, or both clip against the frame. */
const PLOT_PAD_Y = 10;

/** Width reserved for the floating value label, used to clamp it on-canvas. */
const VALUE_LABEL_W = 96;

function formatDateShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

/**
 * "Nice" y-axis domain + ticks. Rounds the axis to human numbers (…,20,40,60…)
 * instead of the raw data min/max, and adds headroom so the line never glues to
 * an edge. A flat series (min===max, e.g. a portfolio whose items carry a stored
 * value but no dated history) gets a sensible band AROUND the value so the line
 * sits mid-chart with gridlines above and below rather than pinned to the frame.
 */
export function niceScale(dataMin: number, dataMax: number, targetTicks = 4): {
  yMin: number;
  yMax: number;
  ticks: number[];
} {
  let min = dataMin;
  let max = dataMax;

  // A series can be "flat enough" without being exactly flat, and that case used
  // to render as a broken chart. A portfolio that moved EUR 0.01 on EUR 55 has a
  // genuine spread, so the old `min === max` check missed it — but the domain it
  // produced was ~0.01 wide, which meant:
  //   - every gridline label printed the SAME "EUR 55", because formatPrice is
  //     0-decimals app-wide (deliberate, see lib/format.ts) — so a sub-euro
  //     domain CANNOT produce distinct labels, and
  //   - the line spanned the full canvas height over a 1-cent move, gluing it to
  //     the top and bottom frame.
  // Treat anything inside 2% of the value as flat and give it a band around the
  // value instead, so the axis reads low → high in real numbers.
  const magnitude = Math.max(Math.abs(min), Math.abs(max));
  const flatEnough = max - min <= (magnitude > 0 ? magnitude * 0.02 : Number.EPSILON);
  if (flatEnough) {
    const v = (min + max) / 2;
    const pad = v === 0 ? 1 : Math.abs(v) * 0.6;
    min = v - pad;
    max = v + pad;
  }
  // Non-negative measures (portfolio value) shouldn't dip below zero.
  if (dataMin >= 0 && min < 0) min = 0;

  const range = max - min || 1;
  const rawStep = range / Math.max(targetTicks, 1);
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const norm = rawStep / mag;
  // Floored at 1: ticks closer together than one currency unit render as
  // duplicate labels once formatPrice drops the decimals.
  const niceStep = Math.max((norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag, 1);

  const yMin = Math.floor(min / niceStep) * niceStep;
  const yMax = Math.ceil(max / niceStep) * niceStep;
  const ticks: number[] = [];
  for (let t = yMin; t <= yMax + niceStep * 0.5; t += niceStep) {
    ticks.push(Number(t.toFixed(6)));
  }
  return { yMin, yMax: yMax === yMin ? yMin + niceStep : yMax, ticks };
}

export const PortfolioLineChart: React.FC<PortfolioLineChartProps> = React.memo(({
  series,
  accentColor = "#14b8a6",
  showValueHeader = false,
  showAxisLabels = true,
  axisLabelColor = "#94a3b8",
  gridColor = "#e5e7eb",
  textColor = "#0b1f3a",
  dotFillColor = "#ffffff",
  loadFailed = false,
  onRetry,
  onScrubChange,
}) => {
  const [width, setWidth] = useState(0);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const sorted = useMemo(
    () =>
      [...series].sort(
        (a, b) => new Date(a.t).getTime() - new Date(b.t).getTime()
      ),
    [series]
  );

  const height = 190; // taller = more "real chart"

  // Nice, rounded y-domain + gridline ticks (see niceScale).
  const { yMin, yMax, ticks } = useMemo(() => {
    if (!sorted.length) return { yMin: 0, yMax: 1, ticks: [0, 1] };
    const values = sorted.map((p) => p.v);
    return niceScale(Math.min(...values), Math.max(...values));
  }, [sorted]);

  // The plot area is inset vertically so a value sitting at the very top or
  // bottom of the domain still draws in full. Without this the 2.5px stroke and
  // the r=4 hover dot are clipped by the SVG frame — the line looks sliced off
  // at the top and the tracker dot loses its upper half.
  const yToPixel = (v: number) => {
    const span = yMax - yMin || 1;
    const usable = height - PLOT_PAD_Y * 2;
    return PLOT_PAD_Y + usable - ((v - yMin) / span) * usable;
  };

  const path = useMemo(() => {
    if (!sorted.length || width <= 0) return "";
    const n = sorted.length;
    const step = n > 1 ? width / (n - 1) : 0;
    let d = "";
    sorted.forEach((p, idx) => {
      const x = n > 1 ? step * idx : width / 2;
      const y = yToPixel(p.v);
      d += idx === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
    });
    // A single point renders as a short flat segment so there is a visible line.
    if (sorted.length === 1) d += ` L ${width} ${yToPixel(sorted[0].v)}`;
    return d;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sorted, width, yMin, yMax]);

  const handleLayout = (e: LayoutChangeEvent) => {
    setWidth(e.nativeEvent.layout.width);
  };

  const handleTouch = (x: number) => {
    if (!sorted.length || width <= 0) return;
    const n = sorted.length;
    const ratio = x / width;
    const idx = Math.round(ratio * (n - 1));
    const safeIdx = Math.min(Math.max(idx, 0), n - 1);
    setHoverIndex(safeIdx);
    onScrubChange?.(sorted[safeIdx] ?? null);
  };

  const handleRelease = () => {
    setHoverIndex(null);
    onScrubChange?.(null);
  };

  if (!sorted.length) {
    // Distinguish "we could not load it" from "there is nothing to show".
    if (loadFailed) {
      return (
        <View style={styles.emptyContainer}>
          <Text style={[styles.emptyText, { color: axisLabelColor }]}>
            Couldn&apos;t load your chart.
          </Text>
          {onRetry ? (
            <Pressable
              onPress={onRetry}
              accessibilityRole="button"
              accessibilityLabel="Retry loading the portfolio chart"
              hitSlop={8}
            >
              <Text style={[styles.emptyText, { color: accentColor, fontWeight: '700', marginTop: 6 }]}>
                Retry
              </Text>
            </Pressable>
          ) : null}
        </View>
      );
    }
    return (
      <View style={styles.emptyContainer}>
        <Text style={[styles.emptyText, { color: axisLabelColor }]}>
          No history yet. Add items to see your portfolio curve.
        </Text>
      </View>
    );
  }

  const n = sorted.length;
  const step = n > 1 ? (width || 1) / (n - 1) : 0;

  const currentIndex =
    hoverIndex != null && sorted[hoverIndex] ? hoverIndex : sorted.length - 1;
  const currentPoint = sorted[currentIndex];

  const hoverX = width > 0 ? (n > 1 ? step * currentIndex : width / 2) : 0;
  const hoverY = yToPixel(currentPoint.v);

  // 4 evenly-spaced x-axis dates.
  const tickCount = Math.min(4, sorted.length);
  const xTickLabels: string[] = Array.from({ length: tickCount }, (_, i) => {
    const idx = Math.round((i / Math.max(tickCount - 1, 1)) * (sorted.length - 1));
    return formatDateShort(sorted[idx].t);
  });

  const gridColorLight = gridColor + "80"; // recessive gridlines

  return (
    <View
      style={styles.container}
      onLayout={handleLayout}
      onStartShouldSetResponder={() => true}
      onMoveShouldSetResponder={() => true}
      onResponderGrant={(evt) => handleTouch(evt.nativeEvent.locationX)}
      onResponderMove={(evt) => handleTouch(evt.nativeEvent.locationX)}
      onResponderRelease={handleRelease}
      onResponderTerminate={handleRelease}
    >
      {width > 0 && (
        <View style={styles.chartWrap}>
          <Svg height={height} width={width}>
            {/* Recessive horizontal gridlines + nice y-axis labels at each tick.
                Labels sit just below their gridline, clamped to stay on-canvas. */}
            {ticks.map((tick, i) => {
              const y = yToPixel(tick);
              const isBaseline = i === 0; // yMin — the axis floor, slightly stronger
              const labelY = Math.min(Math.max(y - 4, 11), height - 2);
              return (
                <React.Fragment key={`grid-${tick}`}>
                  <Line
                    x1={0}
                    y1={y}
                    x2={width}
                    y2={y}
                    stroke={isBaseline ? gridColor : gridColorLight}
                    strokeWidth={1}
                  />
                  {showAxisLabels && (
                    <SvgText
                      x={2}
                      y={labelY}
                      fill={axisLabelColor}
                      fontSize={10}
                      fontWeight="600"
                    >
                      {formatPrice(tick)}
                    </SvgText>
                  )}
                </React.Fragment>
              );
            })}

            {path ? (
              <Path d={path} fill="none" stroke={accentColor} strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
            ) : null}

            {/* hover cursor */}
            <Line
              x1={hoverX}
              y1={0}
              x2={hoverX}
              y2={height}
              stroke={gridColor}
              strokeDasharray="3 4"
              strokeWidth={1}
            />
            <Circle cx={hoverX} cy={hoverY} r={4} fill={dotFillColor} stroke={accentColor} strokeWidth={2} />
          </Svg>

          {/* Value label rides WITH the tracker instead of sitting in a fixed
              top-left header. Parked top-left it collided with the y-axis tick
              labels drawn in the same corner (bold "EUR 8.070" over "EUR 10.000"),
              which made both unreadable. Anchored to the dot it also answers the
              question the user is actually asking while scrubbing: "what was it
              worth HERE?" Clamped so it never leaves the canvas at either end. */}
          {showValueHeader && (
            <View
              pointerEvents="none"
              style={[
                styles.floatingValue,
                {
                  left: Math.min(Math.max(hoverX - VALUE_LABEL_W / 2, 0), Math.max(width - VALUE_LABEL_W, 0)),
                  top: Math.min(Math.max(hoverY - 30, 0), height - 20),
                  width: VALUE_LABEL_W,
                  backgroundColor: dotFillColor,
                },
              ]}
            >
              <Text
                numberOfLines={1}
                style={[styles.valueText, { color: textColor }]}
              >
                {formatPrice(currentPoint.v)}
              </Text>
            </View>
          )}

          {showAxisLabels && (
            <View pointerEvents="none" style={styles.xLabels}>
              {xTickLabels.map((lbl, i) => (
                <Text
                  key={`${lbl}-${i}`}
                  style={[styles.axisText, { color: axisLabelColor }]}
                >
                  {lbl}
                </Text>
              ))}
            </View>
          )}
        </View>
      )}
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    marginTop: 0,
  },
  floatingValue: {
    position: "absolute",
    alignItems: "center",
    paddingHorizontal: 4,
    paddingVertical: 1,
    borderRadius: 6,
    zIndex: 30,
  },
  valueText: {
    fontSize: 15,
    fontWeight: "800",
    textAlign: "center",
  },
  chartWrap: {
    position: "relative",
    paddingBottom: 18, // room for x labels overlay
  },
  xLabels: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    justifyContent: "space-between",
    zIndex: 20,
  },
  axisText: {
    fontSize: 11,
    fontWeight: "700",
  },
  emptyContainer: {
    paddingVertical: 16,
  },
  emptyText: {
    fontSize: 14,
  },
});

PortfolioLineChart.displayName = "PortfolioLineChart";
