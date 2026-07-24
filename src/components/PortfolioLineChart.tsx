import React, { useMemo, useState } from "react";
import { LayoutChangeEvent, StyleSheet, Text, View } from "react-native";
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
};

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
function niceScale(dataMin: number, dataMax: number, targetTicks = 4): {
  yMin: number;
  yMax: number;
  ticks: number[];
} {
  let min = dataMin;
  let max = dataMax;
  if (min === max) {
    const v = min;
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
  const niceStep = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;

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

  const yToPixel = (v: number) => {
    const span = yMax - yMin || 1;
    return height - ((v - yMin) / span) * height;
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
  };

  if (!sorted.length) {
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
      onResponderRelease={() => setHoverIndex(null)}
    >
      {showValueHeader && (
        <View style={styles.valueRow}>
          <Text style={[styles.valueText, { color: textColor }]}>{formatPrice(currentPoint.v)}</Text>
          <Text style={[styles.dateText, { color: axisLabelColor }]}>{formatDateShort(currentPoint.t)}</Text>
        </View>
      )}

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
  valueRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  valueText: {
    fontSize: 16,
    fontWeight: "800",
  },
  dateText: {
    fontSize: 12,
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
