import React, { useMemo, useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  LayoutChangeEvent,
  PanResponder,
  GestureResponderEvent,
} from "react-native";
import Svg, { Polyline, Line, Circle } from "react-native-svg";

export type PortfolioPoint = {
  timestamp: string; // ISO string or anything Date() can parse
  value: number;
};

type Props = {
  data: PortfolioPoint[];
  height?: number;
};

export const PortfolioChartV2: React.FC<Props> = ({ data, height = 220 }) => {
  const [width, setWidth] = useState(0);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const onLayout = useCallback((e: LayoutChangeEvent) => {
    setWidth(e.nativeEvent.layout.width);
  }, []);

  const { min, max, points, ticksY, ticksX } = useMemo(() => {
    if (!data || data.length === 0) {
      return {
        min: 0,
        max: 0,
        points: [] as { x: number; y: number }[],
        ticksY: [] as number[],
        ticksX: [] as number[],
      };
    }

    const values = data.map((d) => d.value);
    let minVal = Math.min(...values);
    let maxVal = Math.max(...values);
    if (minVal === maxVal) {
      // Avoid division by zero; give a bit of range
      const delta = Math.max(1, Math.abs(minVal) * 0.05);
      minVal = minVal - delta;
      maxVal = maxVal + delta;
    }

    const ticksY = [0, 0.25, 0.5, 0.75, 1].map(
      (t) => minVal + t * (maxVal - minVal),
    );

    const indexes = [0];
    if (data.length > 2) {
      indexes.push(Math.floor(data.length / 2));
    }
    if (data.length > 1) {
      indexes.push(data.length - 1);
    }
    const ticksX = Array.from(new Set(indexes)).sort((a, b) => a - b);

    // points will be mapped later once we know width/height
    return {
      min: minVal,
      max: maxVal,
      points: [] as { x: number; y: number }[],
      ticksY,
      ticksX,
    };
  }, [data]);

  const chartPadding = { top: 16, bottom: 24 };
  const chartHeight = height - chartPadding.top - chartPadding.bottom;

  const computePoints = useCallback(
    (w: number) => {
      if (!data || data.length === 0 || w <= 0 || chartHeight <= 0) return [];
      const n = data.length;
      return data.map((d, i) => {
        const t = n === 1 ? 0.5 : i / (n - 1);
        const x = t * w;
        const ratio = (d.value - min) / (max - min || 1);
        const y = chartPadding.top + (1 - ratio) * chartHeight;
        return { x, y };
      });
    },
    [data, chartHeight, max, min],
  );

  const computedPoints = useMemo(
    () => computePoints(width),
    [computePoints, width],
  );

  const handleTouch = useCallback(
    (evt: GestureResponderEvent) => {
      if (!data || data.length === 0 || width <= 0) return;
      const { locationX } = evt.nativeEvent;
      const clampedX = Math.max(0, Math.min(width, locationX));
      const t = data.length === 1 ? 0 : clampedX / width;
      const index = Math.round(t * (data.length - 1));
      const safeIndex = Math.max(0, Math.min(data.length - 1, index));
      setHoverIndex(safeIndex);
    },
    [data, width],
  );

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: handleTouch,
        onPanResponderMove: handleTouch,
        onPanResponderRelease: () => setHoverIndex(null),
        onPanResponderTerminate: () => setHoverIndex(null),
      }),
    [handleTouch],
  );

  const hoverPoint =
    hoverIndex != null && computedPoints[hoverIndex]
      ? computedPoints[hoverIndex]
      : null;
  const hoverData =
    hoverIndex != null && data[hoverIndex] ? data[hoverIndex] : null;

  return (
    <View>
      {/* Y axis + chart */}
      <View style={styles.row}>
        <View style={styles.yAxis}>
          {ticksY
            .slice()
            .reverse()
            .map((v) => (
              <Text key={v.toString()} style={styles.axisLabel}>
                €{v.toFixed(0)}
              </Text>
            ))}
        </View>

        <View
          style={styles.chartContainer}
          onLayout={onLayout}
          {...panResponder.panHandlers}
        >
          {width > 0 && (
            <Svg width={width} height={height}>
              {/* Base gridline (middle) */}
              <Line
                x1={0}
                x2={width}
                y1={chartPadding.top + chartHeight / 2}
                y2={chartPadding.top + chartHeight / 2}
                stroke="#D0E6F5"
                strokeWidth={1}
              />

              {/* Main line */}
              {computedPoints.length > 1 && (
                <Polyline
                  points={computedPoints.map((p) => `${p.x},${p.y}`).join(" ")}
                  fill="none"
                  stroke="#02B5C4" // Tiffany-ish
                  strokeWidth={2}
                />
              )}

              {/* Hover vertical line + dot */}
              {hoverPoint && (
                <>
                  <Line
                    x1={hoverPoint.x}
                    x2={hoverPoint.x}
                    y1={chartPadding.top}
                    y2={chartPadding.top + chartHeight}
                    stroke="#7EC9D8"
                    strokeDasharray="4 4"
                    strokeWidth={1}
                  />
                  <Circle
                    cx={hoverPoint.x}
                    cy={hoverPoint.y}
                    r={4}
                    fill="#02B5C4"
                  />
                </>
              )}
            </Svg>
          )}
        </View>
      </View>

      {/* X axis dates */}
      <View style={styles.xAxisRow}>
        {ticksX.map((idx) => {
          const d = data[idx];
          const date = new Date(d.timestamp);
          const label = `${date.getDate()}/${date.getMonth() + 1}`;
          return (
            <Text key={idx} style={styles.axisLabel}>
              {label}
            </Text>
          );
        })}
      </View>

      {/* Hover tooltip */}
      {hoverData && (
        <View style={styles.tooltip}>
          <Text style={styles.tooltipValue}>
            €{hoverData.value.toFixed(2)}
          </Text>
          <Text style={styles.tooltipDate}>
            {new Date(hoverData.timestamp).toLocaleDateString()}
          </Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "stretch",
  },
  yAxis: {
    justifyContent: "space-between",
    marginRight: 8,
  },
  chartContainer: {
    flex: 1,
  },
  axisLabel: {
    fontSize: 10,
    color: "#496C86",
  },
  xAxisRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 8,
    paddingLeft: 24, // space for y-axis
  },
  tooltip: {
    marginTop: 8,
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: "white",
    shadowColor: "#000",
    shadowOpacity: 0.08,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  tooltipValue: {
    fontSize: 14,
    fontWeight: "600",
    color: "#0B2342",
  },
  tooltipDate: {
    fontSize: 11,
    color: "#496C86",
  },
});
