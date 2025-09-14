import React, { useMemo } from "react";
import { View } from "react-native";
import Svg, { Path, Circle, Rect } from "react-native-svg";
import { theme } from "@/theme";

export type Pt = { t: number; v: number };
export default function PortfolioChart({
  data,
  width = 320,
  height = 160,
  showDot = true,
}: { data: Pt[]; width?: number; height?: number; showDot?: boolean }) {
  const padding = 8;
  const stroke = 2;
  const pts = data && data.length ? data : [{ t: 0, v: 0 }, { t: 1, v: 0 }];

  const { min, max, tMin, tMax } = useMemo(() => {
    let min = Infinity, max = -Infinity, tMin = Infinity, tMax = -Infinity;
    for (const p of pts) {
      if (p.v < min) min = p.v;
      if (p.v > max) max = p.v;
      if (p.t < tMin) tMin = p.t;
      if (p.t > tMax) tMax = p.t;
    }
    if (!isFinite(min) || !isFinite(max) || min === max) { min = min === Infinity ? 0 : min - 1; max = max === -Infinity ? 1 : max + 1; }
    if (!isFinite(tMin) || !isFinite(tMax) || tMin === tMax) { tMin = 0; tMax = 1; }
    return { min, max, tMin, tMax };
  }, [pts]);

  const toX = (t: number) => padding + (width - padding * 2) * (t - tMin) / (tMax - tMin);
  const toY = (v: number) => {
    const n = (v - min) / (max - min);
    return padding + (height - padding * 2) * (1 - n);
  };

  const d = pts.map((p, i) => `${i ? "L" : "M"}${toX(p.t)},${toY(p.v)}`).join(" ");
  const last = pts[pts.length - 1];

  return (
    <View style={{ width, height, backgroundColor: theme.colors.card }}>
      <Svg width={width} height={height}>
        <Rect x={0} y={0} width={width} height={height} fill="transparent" />
        <Path d={d} fill="none" stroke={theme.colors.brand.base} strokeWidth={stroke} />
        {showDot && last ? <Circle cx={toX(last.t)} cy={toY(last.v)} r={3} fill={theme.colors.brand.base} /> : null}
      </Svg>
    </View>
  );
}
