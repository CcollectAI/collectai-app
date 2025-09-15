#!/usr/bin/env bash
set -euo pipefail

# Backup existing chart (if present)
if [ -f "src/components/LineChart.tsx" ]; then
  cp "src/components/LineChart.tsx" "src/components/LineChart.tsx.bak"
fi

# Write polished chart with touch tooltips + hi/low badges
cat > "src/components/LineChart.tsx" <<'TSX'
import { useMemo, useState, useCallback } from 'react';
import { View, useWindowDimensions } from 'react-native';
import Svg, { Path, Line, Circle, Rect, Text as SvgText } from 'react-native-svg';
import { theme } from '@/theme';

type Point = { t: number; v: number };
type Props = {
  data: Point[];
  height?: number;
  gridLines?: number;
  showTooltips?: boolean;
};

const fmtEUR = (n: number) =>
  new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(n);

const fmtTime = (ms: number) =>
  new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit' }).format(ms);

export default function LineChart({
  data,
  height = 200,
  gridLines = 4,
  showTooltips = true,
}: Props) {
  const { width } = useWindowDimensions();
  const pad = 16;
  const innerW = Math.max(320, Math.min(width, 700)) - pad * 2;
  const w = innerW + pad * 2;
  const h = height;

  // Compute scales, path, points
  const { d, min, max, minIdx, maxIdx, pts, scaleX, scaleY } = useMemo(() => {
    if (!data?.length) {
      return {
        d: '',
        min: 0,
        max: 0,
        minIdx: 0,
        maxIdx: 0,
        pts: [] as { x: number; y: number; t: number; v: number }[],
        scaleX: (t: number) => t,
        scaleY: (v: number) => v,
      };
    }
    const xs = data.map((p) => p.t);
    const ys = data.map((p) => p.v);
    const minX = Math.min(...xs),
      maxX = Math.max(...xs);
    const minY = Math.min(...ys),
      maxY = Math.max(...ys);

    const scaleX = (t: number) => pad + ((t - minX) / (maxX - minX || 1)) * innerW;
    const scaleY = (v: number) => pad + (1 - (v - minY) / (maxY - minY || 1)) * (h - pad * 2);

    const pts = data.map((p) => ({ x: scaleX(p.t), y: scaleY(p.v), t: p.t, v: p.v }));
    const d = pts.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ');

    const minIdx = ys.indexOf(minY);
    const maxIdx = ys.indexOf(maxY);

    return { d, min: minY, max: maxY, minIdx, maxIdx, pts, scaleX, scaleY };
  }, [data, innerW, h]);

  // Hover state (index into pts)
  const [hover, setHover] = useState<number | null>(null);
  const nearestIdx = useCallback(
    (x: number) => {
      if (!pts.length) return null;
      let best = 0;
      let bestDist = Math.abs(pts[0].x - x);
      for (let i = 1; i < pts.length; i++) {
        const d = Math.abs(pts[i].x - x);
        if (d < bestDist) {
          best = i;
          bestDist = d;
        }
      }
      return best;
    },
    [pts]
  );

  const onStart = useCallback(
    (e: any) => {
      if (!showTooltips || !pts.length) return;
      const x = e.nativeEvent.locationX;
      const idx = nearestIdx(x);
      if (idx !== null) setHover(idx);
    },
    [nearestIdx, pts.length, showTooltips]
  );

  const onMove = useCallback(
    (e: any) => {
      if (!showTooltips || !pts.length) return;
      const x = e.nativeEvent.locationX;
      const idx = nearestIdx(x);
      if (idx !== null) setHover(idx);
    },
    [nearestIdx, pts.length, showTooltips]
  );

  const onEnd = useCallback(() => {
    // Keep the tooltip visible after release; comment out next line to keep persistent
    // setHover(null);
  }, []);

  // Grid Y positions
  const gridYs = Array.from({ length: gridLines }, (_, i) =>
    pad + (i * (h - pad * 2)) / (gridLines - 1 || 1)
  );

  // Tooltip info
  const tip = hover !== null && pts[hover] ? pts[hover] : null;
  const tipLabel = tip ? `${fmtEUR(tip.v)} • ${fmtTime(tip.t)}` : '';
  // Tooltip box size (approx; keeps square-cornered)
  const TIP_W = 120;
  const TIP_H = 34;
  const tipLeft = tip ? Math.min(Math.max(tip.x - TIP_W / 2, pad), w - pad - TIP_W) : 0;
  const tipTop = tip ? Math.max(tip.y - TIP_H - 12, 4) : 0;

  // Hi/Low badge rect sizes
  const badgePadX = 4;
  const badgePadY = 2;

  return (
    <View style={{ position: 'relative', backgroundColor: theme.colors.card }}>
      <Svg
        width={w}
        height={h}
        onStartShouldSetResponder={() => true}
        onMoveShouldSetResponder={() => true}
        onResponderGrant={onStart}
        onResponderMove={onMove}
        onResponderRelease={onEnd}
      >
        {/* Grid */}
        {gridYs.map((gy, i) => (
          <Line
            key={i}
            x1={pad}
            x2={w - pad}
            y1={gy}
            y2={gy}
            stroke={theme.colors.border}
            strokeWidth={0.75}
          />
        ))}

        {/* Line */}
        {d ? <Path d={d} fill="none" stroke={theme.colors.navy} strokeWidth={1.5} /> : null}

        {/* High badge */}
        {pts.length ? (
          <>
            <Circle cx={pts[maxIdx].x} cy={pts[maxIdx].y} r={2} fill={theme.colors.up} />
            <Rect
              x={pts[maxIdx].x + 6}
              y={Math.max(pts[maxIdx].y - 16, 2)}
              width={56}
              height={14}
              fill="#fff"
              stroke={theme.colors.border}
              strokeWidth={1}
            />
            <SvgText
              x={pts[maxIdx].x + 6 + badgePadX}
              y={Math.max(pts[maxIdx].y - 16, 2) + 10}
              fontSize="10"
              fill={theme.colors.up}
            >
              {`H ${fmtEUR(max)}`}
            </SvgText>

            {/* Low badge */}
            <Circle cx={pts[minIdx].x} cy={pts[minIdx].y} r={2} fill={theme.colors.down} />
            <Rect
              x={pts[minIdx].x + 6}
              y={Math.min(pts[minIdx].y + 2, h - 16)}
              width={56}
              height={14}
              fill="#fff"
              stroke={theme.colors.border}
              strokeWidth={1}
            />
            <SvgText
              x={pts[minIdx].x + 6 + badgePadX}
              y={Math.min(pts[minIdx].y + 2, h - 16) + 10}
              fontSize="10"
              fill={theme.colors.down}
            >
              {`L ${fmtEUR(min)}`}
            </SvgText>
          </>
        ) : null}

        {/* Tooltip (guide line + marker) */}
        {tip ? (
          <>
            <Line
              x1={tip.x}
              x2={tip.x}
              y1={pad}
              y2={h - pad}
              stroke={theme.colors.border}
              strokeDasharray="3,3"
              strokeWidth={1}
            />
            <Circle cx={tip.x} cy={tip.y} r={3} fill={theme.colors.navy} />
          </>
        ) : null}
      </Svg>

      {/* RN overlay tooltip box (square corners) */}
      {tip ? (
        <View
          style={{
            position: 'absolute',
            left: tipLeft,
            top: tipTop,
            backgroundColor: theme.colors.card,
            borderColor: theme.colors.border,
            borderWidth: 1,
            paddingHorizontal: 8,
            paddingVertical: 6,
          }}
        >
          <View>
            {/* Single-line label for cleanliness */}
            {/* Square corners per design; no rounded */}
          </View>
          <View>
            {/* Text rendered via RN to avoid SVG text wrapping quirks */}
          </View>
          <View>
            {/* eslint-disable-next-line react-native/no-inline-styles */}
            <View>
            </View>
          </View>
          {/* We can't use RN Text without importing; add simple inline using SvgText? */}
        </View>
      ) : null}
    </View>
  );
}
TSX

# Also add a tiny RN Text inside tooltip overlay (append import and content)
# We'll patch the file to insert Text usage without retyping whole file.
node - <<'NODE'
const fs = require('fs');
const p = 'src/components/LineChart.tsx';
let s = fs.readFileSync(p, 'utf8');
s = s.replace(
  "import { View, useWindowDimensions } from 'react-native';",
  "import { View, Text, useWindowDimensions } from 'react-native';"
);
s = s.replace(
  /\/\* RN overlay tooltip box.*?\}\)\n      : null\}\)\n    <\/View>\n  \);\n}\nTSX/s,
  `/* RN overlay tooltip box (square corners) */
      {tip ? (
        <View
          style={{
            position: 'absolute',
            left: tipLeft,
            top: tipTop,
            backgroundColor: theme.colors.card,
            borderColor: theme.colors.border,
            borderWidth: 1,
            paddingHorizontal: 8,
            paddingVertical: 6,
          }}
        >
          <Text style={{ color: theme.colors.navy, fontWeight: '700', fontSize: 12 }}>
            ${'${'}tipLabel{'}'}
          </Text>
        </View>
      ) : null}
    </View>
  );
}
TSX`
);
fs.writeFileSync(p, s);
NODE

echo "→ Portfolio chart polished with tooltips + refined badges."
