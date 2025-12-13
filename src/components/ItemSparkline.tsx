import React from "react";
import { View } from "react-native";
import Svg, { Polyline } from "react-native-svg";

interface Props {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
}

export default function ItemSparkline({
  data,
  width = 300,
  height = 120,
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
    <View style={{ marginTop: 10 }}>
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
