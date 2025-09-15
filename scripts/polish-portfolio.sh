#!/usr/bin/env bash
set -euo pipefail

echo "→ Ensure folders"
mkdir -p "app/(tabs)" src/components

# 1) Card: subtler border, consistent padding
if [ -f "src/components/Card.tsx" ]; then cp "src/components/Card.tsx" "src/components/Card.tsx.bak"; fi
cat > "src/components/Card.tsx" <<'TSX'
import { View, ViewProps } from 'react-native';
import { theme } from '@/theme';

export default function Card({ style, ...props }: ViewProps) {
  return (
    <View
      style={[{
        backgroundColor: theme.colors.card,
        padding: theme.spacing.xl,      // give elements more breathing room
        borderColor: theme.colors.border,
        borderWidth: 1,                  // keep square cards; subtle border
      }, style]}
      {...props}
    />
  );
}
TSX

# 2) Underline-style range toggle for 1D/7D/30D
if [ -f "src/components/RangeToggle.tsx" ]; then cp "src/components/RangeToggle.tsx" "src/components/RangeToggle.tsx.bak"; fi
cat > "src/components/RangeToggle.tsx" <<'TSX'
import { View, Pressable, Text } from 'react-native';
import { theme } from '@/theme';

type Props = { options: string[]; value: string; onChange: (v: string) => void; };
export default function RangeToggle({ options, value, onChange }: Props) {
  return (
    <View style={{ flexDirection: 'row', gap: theme.spacing.lg }}>
      {options.map((opt) => {
        const active = opt === value;
        return (
          <Pressable key={opt} onPress={() => onChange(opt)} style={{ paddingVertical: theme.spacing.xs }}>
            <Text style={{ fontWeight: active ? '700' : '500', color: active ? theme.colors.navy : theme.colors.subtext }}>
              {opt}
            </Text>
            <View style={{
              height: 2,
              marginTop: 4,
              backgroundColor: active ? theme.colors.navy : 'transparent'
            }} />
          </Pressable>
        );
      })}
    </View>
  );
}
TSX

# 3) Chart: thinner stroke, lighter grid, responsive width
if [ -f "src/components/LineChart.tsx" ]; then cp "src/components/LineChart.tsx" "src/components/LineChart.tsx.bak"; fi
cat > "src/components/LineChart.tsx" <<'TSX'
import { useMemo } from 'react';
import { View, useWindowDimensions } from 'react-native';
import Svg, { Path, Line, Circle, Text as SvgText } from 'react-native-svg';
import { theme } from '@/theme';

type Point = { t: number; v: number };
type Props = { data: Point[]; height?: number; gridLines?: number; };

const fmtEUR = (n: number) =>
  new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n);

export default function LineChart({ data, height = 200, gridLines = 4 }: Props) {
  const { width } = useWindowDimensions();
  const pad = 16;
  const w = Math.max(320, Math.min(width, 700)) - pad * 2; // responsive, keep margins
  const h = height;

  const { d, min, max, minPt, maxPt, minX, maxX, scaleX, scaleY } = useMemo(() => {
    if (!data?.length) {
      return {
        d: '', min: 0, max: 0,
        minPt: { x: pad, y: h - pad }, maxPt: { x: pad, y: pad },
        minX: 0, maxX: 1,
        scaleX: (t: number) => t, scaleY: (v: number) => v,
      };
    }
    const xs = data.map(p => p.t);
    const ys = data.map(p => p.v);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);

    const scaleX = (t: number) => pad + ((t - minX) / (maxX - minX || 1)) * w;
    const scaleY = (v: number) => pad + (1 - (v - minY) / (maxY - minY || 1)) * (h - pad * 2);

    const path = data.map((p, i) => `${i ? 'L' : 'M'} ${scaleX(p.t)} ${scaleY(p.v)}`).join(' ');
    const minIdx = ys.indexOf(minY), maxIdx = ys.indexOf(maxY);

    return {
      d: path,
      min: minY, max: maxY,
      minPt: { x: scaleX(data[minIdx].t), y: scaleY(minY) },
      maxPt: { x: scaleX(data[maxIdx].t), y: scaleY(maxY) },
      minX, maxX, scaleX, scaleY
    };
  }, [data, w, h]);

  const gridYs = Array.from({ length: gridLines }, (_, i) =>
    pad + (i * (h - pad * 2)) / (gridLines - 1 || 1)
  );

  return (
    <View style={{ backgroundColor: theme.colors.card }}>
      <Svg width={w + pad * 2} height={h}>
        {gridYs.map((gy, i) => (
          <Line key={i} x1={pad} x2={w + pad} y1={gy} y2={gy} stroke={theme.colors.border} strokeWidth={0.75} />
        ))}
        {d ? <Path d={d} fill="none" stroke={theme.colors.navy} strokeWidth={1.5} /> : null}

        {/* High marker */}
        <Circle cx={maxPt.x} cy={maxPt.y} r={2} fill={theme.colors.up} />
        <SvgText x={maxPt.x + 6} y={maxPt.y - 6} fontSize="10" fill={theme.colors.up}>
          H {fmtEUR(max)}
        </SvgText>

        {/* Low marker */}
        <Circle cx={minPt.x} cy={minPt.y} r={2} fill={theme.colors.down} />
        <SvgText x={minPt.x + 6} y={minPt.y + 14} fontSize="10" fill={theme.colors.down}>
          L {fmtEUR(min)}
        </SvgText>
      </Svg>
    </View>
  );
}
TSX

# 4) Portfolio screen: refined spacing, typography, new toggle, cleaner layout
if [ -f "app/(tabs)/index.tsx" ]; then cp "app/(tabs)/index.tsx" "app/(tabs)/index.tsx.bak"; fi
cat > "app/(tabs)/index.tsx" <<'TSX'
import { useMemo, useState } from 'react';
import { View, Text, ScrollView } from 'react-native';
import Card from '@/components/Card';
import LineChart from '@/components/LineChart';
import RangeToggle from '@/components/RangeToggle';
import { theme } from '@/theme';

type Row = { name: string; pct: number; price: number; };
const fmtEUR = (n: number) => new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(n);

const now = Date.now();
const genData = (len: number, base: number) =>
  Array.from({ length: len }, (_, i) => ({
    t: now - (len - i) * 60_000,
    v: base + Math.sin(i / 3) * base * 0.012 + (i % 5) * 0.8
  }));

const DATASETS = {
  '1D': genData(90, 12400),
  '7D': genData(90, 12520),
  '30D': genData(90, 12260),
};

const SAMPLE: Row[] = [
  { name: 'PSA 9 Charizard', pct: 2.4, price: 1820 },
  { name: 'Funko Pop #01', pct: -1.1, price: 260 },
  { name: 'Hot Wheels RLC', pct: 0.7, price: 145 },
];

export default function Portfolio() {
  const [range, setRange] = useState<'1D'|'7D'|'30D'>('7D');
  const data = DATASETS[range];
  const total = useMemo(() => Math.round(data[data.length - 1]?.v || 0), [data]);

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: theme.colors.bg }}
      contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}
    >
      {/* Title block */}
      <View style={{ gap: 4 }}>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Collection Value</Text>
        <Text style={{ color: theme.colors.navy, fontSize: 30, fontWeight: '800', letterSpacing: 0.2 }}>
          {fmtEUR(total)}
        </Text>
      </View>

      {/* Chart card */}
      <Card style={{ gap: theme.spacing.md }}>
        <RangeToggle options={['1D','7D','30D']} value={range} onChange={(v) => setRange(v as any)} />
        <LineChart data={data} />
      </Card>

      {/* Collection list */}
      <Card>
        <Text style={{ color: theme.colors.navy, fontWeight: '700', marginBottom: theme.spacing.md }}>
          Collection
        </Text>
        {SAMPLE.sort((a,b)=>b.price - a.price).map((row, idx) => (
          <View
            key={idx}
            style={{
              flexDirection: 'row',
              justifyContent: 'space-between',
              alignItems: 'center',
              paddingVertical: theme.spacing.md,
              borderTopWidth: idx ? 1 : 0,
              borderColor: theme.colors.border
            }}
          >
            <View>
              <Text style={{ color: theme.colors.navy, fontWeight: '600' }}>{row.name}</Text>
              <Text style={{ fontSize: 12, marginTop: 2, color: row.pct >= 0 ? theme.colors.up : theme.colors.down }}>
                {(row.pct >= 0 ? '+' : '') + row.pct.toFixed(2)}%
              </Text>
            </View>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{fmtEUR(row.price)}</Text>
          </View>
        ))}
      </Card>

      {/* Watchlist */}
      <Card style={{ gap: theme.spacing.sm }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Watchlist</Text>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>No items yet.</Text>
        <View style={{ alignItems: 'center', marginTop: theme.spacing.sm }}>
          <View style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>+ Add to watchlist</Text>
          </View>
        </View>
      </Card>
    </ScrollView>
  );
}
TSX

echo "→ Portfolio polish applied."
