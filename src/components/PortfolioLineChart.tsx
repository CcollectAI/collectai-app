import React, { useMemo, useState } from "react";
import { LayoutChangeEvent, StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Line, Path } from "react-native-svg";
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

  const { path, min, max } = useMemo(() => {
    if (!sorted.length || width <= 0) return { path: "", min: 0, max: 1 };
    const values = sorted.map((p) => p.v);
    const localMin = Math.min(...values);
    const localMax = Math.max(...values);
    const span = localMax - localMin || 1;

    const n = sorted.length;
    const step = n > 1 ? width / (n - 1) : 0;

    let d = "";
    sorted.forEach((p, idx) => {
      const x = step * idx;
      const norm = (p.v - localMin) / span;
      const y = height - norm * height;
      d += idx === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`;
    });

    return { path: d, min: localMin, max: localMax };
  }, [sorted, width]);

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

  // Lighter grid for the midline
  const gridColorLight = gridColor + '60';

  if (!sorted.length) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={[styles.emptyText, { color: axisLabelColor }]}>
          No history yet. Add items to see your portfolio curve.
        </Text>
      </View>
    );
  }

  const span = max - min || 1;
  const n = sorted.length;
  const step = n > 1 ? (width || 1) / (n - 1) : 0;

  const currentIndex =
    hoverIndex != null && sorted[hoverIndex] ? hoverIndex : sorted.length - 1;

  const currentPoint = sorted[currentIndex];

  const hoverX = width > 0 ? step * currentIndex : 0;
  const hoverY =
    span > 0
      ? (() => {
          const v = currentPoint.v;
          const norm = (v - min) / span;
          return height - norm * height;
        })()
      : height;

  const startLabel = formatDateShort(sorted[0].t);
  const endLabel = formatDateShort(sorted[sorted.length - 1].t);

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
          {showAxisLabels && (
            <>
              <View pointerEvents="none" style={styles.yLabels}>
                <Text style={[styles.axisText, { color: axisLabelColor }]}>
                  {formatPrice(max)}
                </Text>
                <Text style={[styles.axisText, { color: axisLabelColor }]}>
                  {formatPrice(min)}
                </Text>
              </View>

              <View pointerEvents="none" style={styles.xLabels}>
                <Text style={[styles.axisText, { color: axisLabelColor }]}>
                  {startLabel}
                </Text>
                <Text style={[styles.axisText, { color: axisLabelColor }]}>
                  {endLabel}
                </Text>
              </View>
            </>
          )}

          <Svg height={height} width={width}>
            {/* baseline + mid gridline */}
            <Line x1={0} y1={height} x2={width} y2={height} stroke={gridColor} strokeWidth={1} />
            <Line x1={0} y1={height / 2} x2={width} y2={height / 2} stroke={gridColorLight} strokeWidth={1} />

            {path ? (
              <Path d={path} fill="none" stroke={accentColor} strokeWidth={3} />
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
  yLabels: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 2,
    bottom: 18,
    justifyContent: "space-between",
    zIndex: 20,
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
