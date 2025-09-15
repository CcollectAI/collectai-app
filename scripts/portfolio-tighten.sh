#!/usr/bin/env bash
set -euo pipefail

echo "→ Ensure dirs"
mkdir -p "app/(tabs)" app/_shelf src/components

############################################
# 1) Tabs layout — single Settings on home, no duplicates
############################################
if [ -f "app/(tabs)/_layout.tsx" ]; then cp "app/(tabs)/_layout.tsx" "app/(tabs)/_layout.tsx.bak"; fi
cat > "app/(tabs)/_layout.tsx" <<'TSX'
import { Tabs, Link } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Pressable } from 'react-native';
import { theme } from '@/theme';

function SettingsButton() {
  return (
    <Link href="/_shelf/settings" asChild>
      <Pressable style={{ paddingHorizontal: 12 }}>
        <Ionicons name="settings-outline" size={20} color={theme.colors.navy} />
      </Pressable>
    </Link>
  );
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: theme.colors.navy,
        tabBarInactiveTintColor: theme.colors.subtext,
        tabBarStyle: { backgroundColor: theme.colors.card, borderTopColor: theme.colors.border },
        headerStyle: { backgroundColor: theme.colors.bg },
        headerTitleStyle: { color: theme.colors.navy, fontWeight: '800' },
        headerTintColor: theme.colors.navy,
        sceneStyle: { backgroundColor: theme.colors.bg },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Collect AI',
          tabBarLabel: 'Collect AI',
          tabBarIcon: ({ color, size }) => <Ionicons name="stats-chart-outline" size={size} color={color} />,
          headerRight: () => <SettingsButton />,
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: 'Items',
          tabBarIcon: ({ color, size }) => <Ionicons name="albums-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="add"
        options={{
          title: 'Add',
          tabBarIcon: ({ color, size }) => <Ionicons name="add-circle-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="marketplace"
        options={{
          title: 'Marketplace',
          tabBarIcon: ({ color, size }) => <Ionicons name="cart-outline" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
TSX

############################################
# 2) RangeToggle — right-aligned (unchanged behavior)
############################################
if [ -f "src/components/RangeToggle.tsx" ]; then cp "src/components/RangeToggle.tsx" "src/components/RangeToggle.tsx.bak"; fi
cat > "src/components/RangeToggle.tsx" <<'TSX'
import { View, Pressable, Text } from 'react-native';
import { theme } from '@/theme';

type Props = { options: string[]; value: string; onChange: (v: string) => void; };
export default function RangeToggle({ options, value, onChange }: Props) {
  return (
    <View style={{ flexDirection: 'row', gap: theme.spacing.lg, justifyContent: 'flex-end' }}>
      {options.map((opt) => {
        const active = opt === value;
        return (
          <Pressable key={opt} onPress={() => onChange(opt)} style={{ paddingVertical: theme.spacing.xs }}>
            <Text style={{ fontWeight: active ? '700' : '500', color: active ? theme.colors.navy : theme.colors.subtext }}>{opt}</Text>
            <View style={{ height: 2, marginTop: 4, backgroundColor: active ? theme.colors.navy : 'transparent' }} />
          </Pressable>
        );
      })}
    </View>
  );
}
TSX

############################################
# 3) Chart — clipped, tidy, with y-tick labels; thin stroke
############################################
if [ -f "src/components/LineChart.tsx" ]; then cp "src/components/LineChart.tsx" "src/components/LineChart.tsx.bak"; fi
cat > "src/components/LineChart.tsx" <<'TSX'
import { useMemo } from 'react';
import { View, useWindowDimensions } from 'react-native';
import Svg, { Path, Line, Text as SvgText, Defs, ClipPath, Rect, G } from 'react-native-svg';
import { theme } from '@/theme';

type Point = { t: number; v: number };
type Props = { data: Point[]; height?: number; gridLines?: number; };

function smooth(vals: number[], window = 5) {
  const half = Math.floor(window / 2);
  return vals.map((_, i) => {
    let s = 0, c = 0;
    for (let k = -half; k <= half; k++) {
      const j = i + k;
      if (j >= 0 && j < vals.length) { s += vals[j]; c++; }
    }
    return s / (c || 1);
  });
}

export default function LineChart({ data, height = 180, gridLines = 4 }: Props) {
  const { width } = useWindowDimensions();
  const pad = 16;
  const innerW = Math.max(320, Math.min(width, 700)) - pad * 2;
  const w = innerW + pad * 2;
  const h = height;

  const { d, min, max, minX, maxX } = useMemo(() => {
    if (!data?.length) return { d: '', min: 0, max: 0, minX: 0, maxX: 1 };
    const xs = data.map(p => p.t);
    const ys = smooth(data.map(p => p.v), 5);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const scaleX = (t: number) => pad + ((t - minX) / (maxX - minX || 1)) * innerW;
    const scaleY = (v: number) => pad + (1 - (v - minY) / (maxY - minY || 1)) * (h - pad * 2);
    const path = xs.map((t, i) => `${i ? 'L' : 'M'} ${scaleX(t)} ${scaleY(ys[i])}`).join(' ');
    return { d: path, min: minY, max: maxY, minX, maxX };
  }, [data, innerW, h]);

  const ticks = 3;
  const gridYs = Array.from({ length: ticks }, (_, i) => pad + (i * (h - pad * 2)) / (ticks - 1 || 1));
  const tickVals = (v: number) => new Intl.NumberFormat('de-DE', { maximumFractionDigits: 0 }).format(v);
  const tickLabels = useMemo(() => {
    if (!data?.length) return [0,0,0];
    return [max, (max + min) / 2, min];
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  return (
    <View style={{ backgroundColor: theme.colors.card }}>
      <Svg width={w} height={h}>
        <Defs>
          <ClipPath id="clip">
            <Rect x={pad} y={pad} width={innerW} height={h - pad * 2} />
          </ClipPath>
        </Defs>

        {/* Grid + Y labels (left) */}
        {gridYs.map((gy, i) => (
          <Line key={i} x1={pad} x2={w - pad} y1={gy} y2={gy} stroke={theme.colors.border} strokeWidth={0.75} />
        ))}
        {tickLabels.map((val, i) => (
          <SvgText key={i} x={4} y={gridYs[i] + 4} fontSize="10" fill={theme.colors.subtext}>
            {tickVals(val)}
          </SvgText>
        ))}

        {/* Line inside clip (never bleeds) */}
        <G clipPath="url(#clip)">
          {d ? <Path d={d} fill="none" stroke={theme.colors.navy} strokeWidth={1.25} /> : null}
        </G>
      </Svg>
    </View>
  );
}
TSX

############################################
# 4) Portfolio screen — tighter summary, % Today, section header, watchlist restored
############################################
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
const base = 12400;
const genData = (len: number) =>
  Array.from({ length: len }, (_, i) => ({ t: now - (len - i) * 60_000, v: base + i * 3.5 + Math.sin(i / 7) * 8 }));

const DATASETS = { '1D': genData(90), '7D': genData(120), '30D': genData(180) };
const SAMPLE: Row[] = [
  { name: 'PSA 9 Charizard', pct: 2.4, price: 1820 },
  { name: 'Funko Pop #01', pct: -1.1, price: 260 },
  { name: 'Hot Wheels RLC', pct: 0.7, price: 145 },
  { name: 'LEGO Millennium Falcon', pct: 0.3, price: 980 },
];

export default function Portfolio() {
  const [range, setRange] = useState<'1D'|'7D'|'30D'>('7D');
  const data = DATASETS[range];
  const total = useMemo(() => Math.round(data[data.length - 1]?.v || 0), [data]);

  // % Today from 1D dataset (explicitly "Today" as requested)
  const oneDay = DATASETS['1D'];
  const pctToday = useMemo(() => {
    if (!oneDay.length) return 0;
    const first = oneDay[0].v, last = oneDay[oneDay.length - 1].v;
    return ((last - first) / (first || 1)) * 100;
  }, [oneDay]);

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: theme.colors.bg }}
      contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}
    >
      {/* Tightened summary: title bigger than number, with % Today */}
      <Card style={{ padding: theme.spacing.md, gap: 4 }}>
        <Text style={{ color: theme.colors.navy, fontSize: 20, fontWeight: '900' }}>Collection Value</Text>
        <Text style={{ color: theme.colors.navy, fontSize: 18, fontWeight: '700' }}>{fmtEUR(total)}</Text>
        <Text style={{ fontSize: 12, color: pctToday >= 0 ? theme.colors.up : theme.colors.down }}>
          {(pctToday >= 0 ? '+' : '') + pctToday.toFixed(2)}% Today
        </Text>
      </Card>

      {/* Chart with right-aligned day buttons, tighter spacing */}
      <Card style={{ padding: theme.spacing.md, gap: theme.spacing.md }}>
        <RangeToggle options={['1D','7D','30D']} value={range} onChange={(v) => setRange(v as any)} />
        <LineChart data={data} />
      </Card>

      {/* "Items" section title */}
      <Text style={{ color: theme.colors.navy, fontWeight: '800', marginLeft: theme.spacing.sm }}>Items</Text>

      {/* Organized items table */}
      <Card style={{ padding: theme.spacing.md }}>
        <View style={{ flexDirection: 'row', paddingBottom: theme.spacing.sm, borderBottomWidth: 1, borderColor: theme.colors.border }}>
          <Text style={{ flex: 1, color: theme.colors.subtext, fontWeight: '700' }}>Name</Text>
          <Text style={{ width: 70, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>%</Text>
          <Text style={{ width: 100, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>Price</Text>
        </View>
        {SAMPLE.sort((a,b)=>b.price - a.price).map((row, idx) => (
          <View key={idx} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.sm, borderBottomWidth: idx < SAMPLE.length - 1 ? 1 : 0, borderColor: theme.colors.border }}>
            <View style={{ flex: 1, paddingRight: theme.spacing.lg }}>
              <Text style={{ color: theme.colors.navy, fontWeight: '600' }}>{row.name}</Text>
              <Text style={{ fontSize: 12, marginTop: 2, color: row.pct >= 0 ? theme.colors.up : theme.colors.down }}>
                {(row.pct >= 0 ? '+' : '') + row.pct.toFixed(2)}%
              </Text>
            </View>
            <Text style={{ width: 100, textAlign: 'right', color: theme.colors.navy, fontWeight: '700' }}>
              {fmtEUR(row.price)}
            </Text>
          </View>
        ))}
      </Card>

      {/* Watchlist restored */}
      <Card style={{ padding: theme.spacing.md, gap: theme.spacing.sm }}>
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

echo "→ Portfolio tightened and restored."
