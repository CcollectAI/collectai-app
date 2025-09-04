import React, { useMemo } from "react";
import { View, Text } from "react-native";
import Svg, { Polyline } from "react-native-svg";

type Props = {
  data?: number[];             // e.g., portfolio values over time
  width?: number;              // px
  height?: number;             // px
  strokeWidth?: number;
  label?: string;              // optional label shown above chart
};

export default function PortfolioChart({
  data,
  width = 300,
  height = 120,
  strokeWidth = 2,
  label,
}: Props) {
  // graceful default so Home renders even before you wire real data
  const series = data && data.length > 1
    ? data
    : [100, 101, 99, 105, 110, 108, 115, 117, 112, 120];

  // map data to polyline points
  const points = useMemo(() => {
    const min = Math.min(...series);
    const max = Math.max(...series);
    const range = max - min || 1;
    const stepX = series.length > 1 ? width / (series.length - 1) : width;

    return series.map((v, i) => {
      const x = i * stepX;
      // SVG Y=0 is top, so invert: higher value -> lower y
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    }).join(" ");
  }, [series, width, height]);

  return (
    <View style={{ width, paddingVertical: 8 }}>
      {label ? (
        <Text style={{ fontSize: 14, fontWeight: "600", marginBottom: 6 }}>
          {label}
        </Text>
      ) : null}
      <Svg width={width} height={height}>
        <Polyline
          points={points}
          fill="none"
          stroke="#2563eb"
          strokeWidth={strokeWidth}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </Svg>
    </View>
  );
}
