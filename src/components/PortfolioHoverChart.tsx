import React, { useCallback, useMemo, useState } from "react";
import { View, Text, LayoutChangeEvent, PanResponder, GestureResponderEvent, StyleSheet } from "react-native";
import Svg, { Polyline, Line, Circle } from "react-native-svg";

export type PortfolioPoint = {
  t: number;      // unix ms timestamp
  value: number;  // portfolio value
};

export type HoverPoint = PortfolioPoint;

type Props = {
  points: PortfolioPoint[];
  onPointChange?: (p: HoverPoint | null) => void;
  height?: number;
};

export const PortfolioHoverChart: React.FC<Props> = ({ points, onPointChange, height = 220 }) => {
  const [width, setWidth] = useState(0);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const onLayout = useCallback((e: LayoutChangeEvent) => {
    setWidth(e.nativeEvent.layout.width);
  }, []);

  const { min, max, ticksY, ticksX } = useMemo(() => {
    if (!points || points.length === 0) {
      return { min: 0, max: 0, ticksY: [] as number[], ticksX: [] as number[] };
    }
    const values = points.map((d) => d.value);
    let minVal = Math.min(...values);
    let maxVal = Math.max(...values);
    if (minVal === maxVal) {
      const delta = Math.max(1, Math.abs(minVal) * 0.05);
      minVal -= delta;
      maxVal += delta;
    }
    const ticksY = [0, 0.25, 0.5, 0.75, 1].map((t) => minVal + t * (maxVal - minVal));

    const idxs = [0];
    if (points.length > 2) idxs.push(Math.floor(points.length / 2));
    if (points.length > 1) idxs.push(points.length - 1);
    const ticksX = Array.from(new Set(idxs)).sort((a, b) => a - b);

    return { min: minVal, max: maxVal, ticksY, ticksX };
  }, [points]);

  const chartPadding = { top: 16, bottom: 24 };
  const chartHeight = height - chartPadding.top - chartPadding.bottom;

  const xy = useMemo(() => {
    if (!points || points.length === 0 || width <= 0 || chartHeight <= 0) return [];
    const n = points.length;
    return points.map((d, i) => {
      const frac = n === 1 ? 0.5 : i / (n - 1);
      const x = frac * width;
      const ratio = (d.value - min) / (max - min || 1);
      const y = chartPadding.top + (1 - ratio) * chartHeight;
      return { x, y };
    });
  }, [points, width, chartHeight, min, max]);

  const setHover = useCallback(
    (idx: number | null) => {
      setHoverIndex(idx);
      if (!onPointChange) return;
      if (idx == null || !points[idx]) onPointChange(null);
      else onPointChange(points[idx]);
    },
    [onPointChange, points]
  );

  const handleTouch = useCallback(
    (evt: GestureResponderEvent) => {
      if (!points || points.length === 0 || width <= 0) return;
      const { locationX } = evt.nativeEvent;
      const clampedX = Math.max(0, Math.min(width, locationX));
      const frac = points.length === 1 ? 0 : clampedX / width;
      const index = Math.round(frac * (points.length - 1));
      const safeIndex = Math.max(0, Math.min(points.length - 1, index));
      setHover(safeIndex);
    },
    [points, width, setHover]
  );

  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderGrant: handleTouch,
        onPanResponderMove: handleTouch,
        onPanResponderRelease: () => setHover(null),
        onPanResponderTerminate: () => setHover(null),
      }),
    [handleTouch, setHover]
  );

  const hoverXY = hoverIndex != null && xy[hoverIndex] ? xy[hoverIndex] : null;
  const hoverData = hoverIndex != null && points[hoverIndex] ? points[hoverIndex] : null;

  return (
    <View>
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

        <View style={styles.chart} onLayout={onLayout} {...panResponder.panHandlers}>
          {width > 0 && (
            <Svg width={width} height={height}>
              <Line
                x1={0}
                x2={width}
                y1={chartPadding.top + chartHeight / 2}
                y2={chartPadding.top + chartHeight / 2}
                stroke="#D0E6F5"
                strokeWidth={1}
              />

              {xy.length > 1 && (
                <Polyline
                  points={xy.map((p) => `${p.x},${p.y}`).join(" ")}
                  fill="none"
                  stroke="#02B5C4"
                  strokeWidth={2}
                />
              )}

              {hoverXY && (
                <>
                  <Line
                    x1={hoverXY.x}
                    x2={hoverXY.x}
                    y1={chartPadding.top}
                    y2={chartPadding.top + chartHeight}
                    stroke="#7EC9D8"
                    strokeDasharray="4 4"
                    strokeWidth={1}
                  />
                  <Circle cx={hoverXY.x} cy={hoverXY.y} r={4} fill="#02B5C4" />
                </>
              )}
            </Svg>
          )}
        </View>
      </View>

      <View style={styles.xAxis}>
        {ticksX.map((idx) => {
          const d = points[idx];
          const date = new Date(d.t);
          const label = `${date.getDate()}/${date.getMonth() + 1}`;
          return (
            <Text key={idx} style={styles.axisLabel}>
              {label}
            </Text>
          );
        })}
      </View>

      {hoverData && (
        <View style={styles.tooltip}>
          <Text style={styles.tooltipValue}>€{hoverData.value.toFixed(2)}</Text>
          <Text style={styles.tooltipDate}>{new Date(hoverData.t).toLocaleDateString()}</Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "stretch" },
  yAxis: { justifyContent: "space-between", marginRight: 8 },
  chart: { flex: 1 },
  axisLabel: { fontSize: 10, color: "#496C86" },
  xAxis: { flexDirection: "row", justifyContent: "space-between", marginTop: 8 },
  tooltip: { marginTop: 10, padding: 10, borderRadius: 12, backgroundColor: "#ffffff" },
  tooltipValue: { fontSize: 14, fontWeight: "700", color: "#0b1f3a" },
  tooltipDate: { marginTop: 2, fontSize: 12, color: "#5b6b7a" },
});
