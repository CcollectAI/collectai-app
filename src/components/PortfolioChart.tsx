import React, { useMemo } from "react";
import { View, Text } from "react-native";
import Svg, { Path, Circle, Rect, Line } from "react-native-svg";
import { theme } from "@/theme";
import { fmtMoney } from "@/utils/format";

export type Pt = { t: number; v: number };
export default function PortfolioChart({
  data,
  width = 340,
  height = 180,
  showDot = true,
  gridLines = 4,
}: { data: Pt[]; width?: number; height?: number; showDot?: boolean; gridLines?: number }) {
  const padding = 10;
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
    <View style={{ width, backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border, padding: 8 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 6 }}>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Low €{fmtMoney(min)}</Text>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>High €{fmtMoney(max)}</Text>
      </View>
      <Svg width={width - 16} height={height}>
        <Rect x={0} y={0} width={width - 16} height={height} fill="transparent" />
        {/* horizontal grid */}
        {Array.from({ length: gridLines }).map((_, i) => {
          const y = (height / (gridLines + 1)) * (i + 1);
          return <Line key={i} x1={0} y1={y} x2={width - 16} y2={y} stroke={theme.colors.border} strokeDasharray="3 3" strokeWidth={1} />;
        })}
        {/* price line */}
        <Path d={d} fill="none" stroke={theme.colors.brand.base} strokeWidth={stroke} />
        {showDot && last ? <Circle cx={toX(last.t) - 8} cy={toY(last.v)} r={3} fill={theme.colors.brand.base} /> : null}
      </Svg>
    </View>
  );
}
