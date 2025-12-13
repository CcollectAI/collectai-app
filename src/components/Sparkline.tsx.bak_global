import React from "react";
import { View } from "react-native";
import Svg, { Polyline } from "react-native-svg";

interface Props {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
}

export default function Sparkline({
  data,
  width = 120,
  height = 40,
  stroke = "#2A7FFF",
}: Props) {
  if (!data || data.length === 0) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <View style={{ marginTop: 8 }}>
      <Svg width={width} height={height}>
        <Polyline
          points={points}
          fill="none"
          stroke={stroke}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </Svg>
    </View>
  );
}
