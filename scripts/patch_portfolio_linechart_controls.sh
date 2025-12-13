#!/usr/bin/env bash
set -e

FILE="src/components/PortfolioLineChart.tsx"
[ -f "$FILE" ] || { echo "❌ Missing $FILE"; exit 1; }

TS=$(date +%Y%m%d_%H%M%S)
cp "$FILE" "$FILE.bak_controls_$TS"
echo "✅ Backup: $FILE.bak_controls_$TS"

cat > "$FILE" <<'TSX'
import React, { useMemo, useState } from "react";
import { LayoutChangeEvent, StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Line, Path } from "react-native-svg";

export type TimeSeriesPoint = {
  t: string; // ISO timestamp
  v: number; // portfolio value
};

export type PortfolioLineChartProps = {
  series: TimeSeriesPoint[];
  accentColor?: string;

  /** If false, removes the internal EUR total header inside the chart */
  showValueHeader?: boolean;

  /** If true, shows min/max + start/end labels */
  showAxisLabels?: boolean;
};

function formatCurrencyEUR(value: number): string {
  if (!Number.isFinite(value)) return "—";
  try {
    return new Intl.NumberFormat("de-DE", {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${value.toFixed(0)} EUR`;
  }
}

function formatDateShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

export const PortfolioLineChart: React.FC<PortfolioLineChartProps> = ({
  series,
  accentColor = "#14b8a6",
  showValueHeader = true,
  showAxisLabels = true,
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

  const { path, min, max } = useMemo(() => {
    if (!sorted.length || width <= 0) return { path: "", min: 0, max: 1 };
    const values = sorted.map((p) => p.v);
    const localMin = Math.min(...values);
    const localMax = Math.max(...values);
    const span = localMax - localMin || 1;

    const h = 160;
    const n = sorted.length;
    const step = n > 1 ? width / (n - 1) : 0;

    let d = "";
    sorted.forEach((p, idx) => {
      const x = step * idx;
      const norm = (p.v - localMin) / span;
      const y = h - norm * h;
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

  if (!sorted.length) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyText}>
          No history yet. Add items to see your portfolio curve.
        </Text>
      </View>
    );
  }

  const h = 160;
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
          return h - norm * h;
        })()
      : h;

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
        <View style={styles.tooltipRow}>
          <Text style={styles.tooltipValue}>{formatCurrencyEUR(currentPoint.v)}</Text>
          <Text style={styles.tooltipDate}>{formatDateShort(currentPoint.t)}</Text>
        </View>
      )}

      {width > 0 && (
        <View style={styles.chartBox}>
          {/* Axis labels (min/max + start/end) */}
          {showAxisLabels && (
            <>
              <View style={styles.yAxisOverlay} pointerEvents="none">
                <Text style={styles.axisLabel}>{formatCurrencyEUR(max)}</Text>
                <Text style={styles.axisLabel}>{formatCurrencyEUR(min)}</Text>
              </View>

              <View style={styles.xAxisRow} pointerEvents="none">
                <Text style={styles.axisLabel}>{startLabel}</Text>
                <Text style={styles.axisLabel}>{endLabel}</Text>
              </View>
            </>
          )}

          <Svg height={h} width={width}>
            {/* baseline + mid gridline */}
            <Line x1={0} y1={h} x2={width} y2={h} stroke="#e5e7eb" strokeWidth={1} />
            <Line x1={0} y1={h / 2} x2={width} y2={h / 2} stroke="#f1f5f9" strokeWidth={1} />

            {path ? (
              <Path d={path} fill="none" stroke={accentColor} strokeWidth={2.75} />
            ) : null}

            {/* hover cursor */}
            <Line
              x1={hoverX}
              y1={0}
              x2={hoverX}
              y2={h}
              stroke="#d1d5db"
              strokeDasharray="3 4"
              strokeWidth={1}
            />
            <Circle cx={hoverX} cy={hoverY} r={4} fill="#ffffff" stroke={accentColor} strokeWidth={2} />
          </Svg>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginTop: 0,
  },
  tooltipRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  tooltipValue: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0b1f3a",
  },
  tooltipDate: {
    fontSize: 12,
    color: "#64748b",
  },

  chartBox: {
    position: "relative",
  },

  yAxisOverlay: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 2,
    bottom: 18,
    justifyContent: "space-between",
    zIndex: 10,
  },
  xAxisRow: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    justifyContent: "space-between",
    zIndex: 10,
  },
  axisLabel: {
    fontSize: 11,
    color: "#94a3b8",
  },

  emptyContainer: {
    paddingVertical: 16,
  },
  emptyText: {
    color: "#64748b",
  },
});
TSX

echo "✅ Patched PortfolioLineChart (toggle header, axis labels)."
echo "🛑 SANITY CHECK: npx expo start --tunnel"
