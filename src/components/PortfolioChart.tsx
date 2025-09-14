import React, { useMemo } from "react";
import { View, Text } from "react-native";
import Svg, { Path, Circle, Rect, Line } from "react-native-svg";
import { theme } from "@/theme";
import { fmtMoney } from "@/utils/format";

export type Pt = { t: number; v: number };

// Catmull–Rom to cubic Bézier smoothing
function toSmoothPath(points: {x:number;y:number}[], tension = 0.5) {
  if (points.length < 2) return "";
  const cps = (p0:any, p1:any, p2:any, t:number) => {
    const d01 = Math.hypot(p1.x - p0.x, p1.y - p0.y);
    const d12 = Math.hypot(p2.x - p1.x, p2.y - p1.y);
    const fa = (t * d01) / (d01 + d12 || 1);
    const fb = (t * d12) / (d01 + d12 || 1);
    const p1x = p1.x - fa * (p2.x - p0.x);
    const p1y = p1.y - fa * (p2.y - p0.y);
    const p2x = p1.x + fb * (p2.x - p0.x);
    const p2y = p1.y + fb * (p2.y - p0.y);
    return { p1x, p1y, p2x, p2y };
  };

  let d = `M ${points[0].x},${points[0].y}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] || points[i];
    const p1 = points[i];
    const p2 = points[i + 1] || points[i];
    const p3 = points[i + 2] || p2;
    const { p1x, p1y } = cps(p0, p1, p2, tension);
    const { p2x, p2y } = cps(p1, p2, p3, tension);
    d += ` C ${p1x},${p1y} ${p2x},${p2y} ${p2.x},${p2.y}`;
  }
  return d;
}

export default function PortfolioChart({
  data,
  width = 340,
  height = 200,
  showDot = true,
  gridLines = 4,
}: { data: Pt[]; width?: number; height?: number; showDot?: boolean; gridLines?: number }) {
  const padding = 10;
  const pts = data && data.length ? data : [{ t: 0, v: 0 }, { t: 1, v: 0 }];

  const { min, max, tMin, tMax } = useMemo(() => {
    let min = Infinity, max = -Infinity, tMin = Infinity, tMax = -Infinity;
    for (const p of pts) {
      if (p.v < min) min = p.v;
      if (p.v > max) max = p.v;
      if (p.t < tMin) tMin = p.t;
      if (p.t > tMax) tMax = p.t;
    }
    if (!isFinite(min) || !isFinite(max) || min === max) { min = (min === Infinity ? 0 : min - 1); max = (max === -Infinity ? 1 : max + 1); }
    if (!isFinite(tMin) || !isFinite(tMax) || tMin === tMax) { tMin = 0; tMax = 1; }
    return { min, max, tMin, tMax };
  }, [pts]);

  const innerW = width - padding * 2;
  const innerH = height - padding * 2;

  const toX = (t: number) => padding + innerW * (t - tMin) / (tMax - tMin);
  const toY = (v: number) => padding + innerH * (1 - (v - min) / (max - min));

  const xy = pts.map(p => ({ x: toX(p.t), y: toY(p.v) }));
  const path = toSmoothPath(xy, 0.6);
  const last = xy[xy.length - 1];

  return (
    <View style={{ width: "100%", backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border, padding: 10 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 6 }}>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Low €{fmtMoney(min)}</Text>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>High €{fmtMoney(max)}</Text>
      </View>
      <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
        <Rect x={0} y={0} width={width} height={height} fill="transparent" />
        {Array.from({ length: gridLines }).map((_, i) => {
          const y = padding + innerH * ((i + 1) / (gridLines + 1));
          return <Line key={i} x1={padding} y1={y} x2={width - padding} y2={y} stroke={theme.colors.border} strokeDasharray="3 3" strokeWidth={1} />;
        })}
        <Path d={path} fill="none" stroke={theme.colors.brand.base} strokeWidth={2.5} />
        {showDot && last ? <Circle cx={last.x} cy={last.y} r={3.5} fill={theme.colors.brand.base} /> : null}
      </Svg>
    </View>
  );
}
