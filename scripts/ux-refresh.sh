#!/usr/bin/env bash
set -euo pipefail

echo "→ Ensure folders"
mkdir -p "app/(tabs)" app/_shelf src/components src/auth

echo "→ Install deps needed for icons & svg"
npx expo install @expo/vector-icons react-native-svg >/dev/null

############################################
# 1) Tabs layout — title “Collect AI”, icons, Settings + Share in header
############################################
if [ -f "app/(tabs)/_layout.tsx" ]; then cp "app/(tabs)/_layout.tsx" "app/(tabs)/_layout.tsx.bak"; fi
cat > "app/(tabs)/_layout.tsx" <<'TSX'
import { Tabs, Link } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Pressable, Share, View } from 'react-native';
import { theme } from '@/theme';

function HeaderActions() {
  const onShare = async () => {
    try {
      await Share.share({ message: 'Shared from Collect AI 📦' });
    } catch {}
  };
  return (
    <View style={{ flexDirection: 'row' }}>
      <Pressable onPress={onShare} style={{ paddingHorizontal: 8 }}>
        <Ionicons name="share-outline" size={20} color={theme.colors.navy} />
      </Pressable>
      <Link href="/_shelf/settings" asChild>
        <Pressable style={{ paddingRight: 12, paddingLeft: 8 }}>
          <Ionicons name="settings-outline" size={20} color={theme.colors.navy} />
        </Pressable>
      </Link>
    </View>
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
          // Replace "Portfolio" with "Collect AI"
          title: 'Collect AI',
          tabBarLabel: 'Collect AI',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="stats-chart-outline" size={size} color={color} />
          ),
          headerRight: () => <HeaderActions />,
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: 'Items',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="albums-outline" size={size} color={color} />
          ),
          // Share in the Items header too
          headerRight: () => <HeaderActions />,
        }}
      />
      <Tabs.Screen
        name="add"
        options={{
          title: 'Add',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="add-circle-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="marketplace"
        options={{
          title: 'Marketplace',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="cart-outline" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
TSX

############################################
# 2) RangeToggle — right-aligned controls
############################################
if [ -f "src/components/RangeToggle.tsx" ]; then cp "src/components/RangeToggle.tsx" "src/components/RangeToggle.tsx.bak"; fi
cat > "src/components/RangeToggle.tsx" <<'TSX'
import { View, Pressable, Text, ViewStyle } from 'react-native';
import { theme } from '@/theme';

type Props = { options: string[]; value: string; onChange: (v: string) => void; style?: ViewStyle; };
export default function RangeToggle({ options, value, onChange, style }: Props) {
  return (
    <View style={[{ flexDirection: 'row', gap: theme.spacing.lg, justifyContent: 'flex-end' }, style]}>
      {options.map((opt) => {
        const active = opt === value;
        return (
          <Pressable key={opt} onPress={() => onChange(opt)} style={{ paddingVertical: theme.spacing.xs }}>
            <Text style={{ fontWeight: active ? '700' : '500', color: active ? theme.colors.navy : theme.colors.subtext }}>
              {opt}
            </Text>
            <View style={{ height: 2, marginTop: 4, backgroundColor: active ? theme.colors.navy : 'transparent' }} />
          </Pressable>
        );
      })}
    </View>
  );
}
TSX

############################################
# 3) Card — keep white background & subtle border
############################################
if [ -f "src/components/Card.tsx" ]; then cp "src/components/Card.tsx" "src/components/Card.tsx.bak"; fi
cat > "src/components/Card.tsx" <<'TSX'
import { View, ViewProps } from 'react-native';
import { theme } from '@/theme';

export default function Card({ style, ...props }: ViewProps) {
  return (
    <View
      style={[{
        backgroundColor: theme.colors.card, // white bg so all text/numbers sit on white
        padding: theme.spacing.xl,
        borderColor: theme.colors.border,
        borderWidth: 1,
      }, style]}
      {...props}
    />
  );
}
TSX

############################################
# 4) LineChart — clipped, subtle, never bleeds; right-aligned toggles handled above
############################################
if [ -f "src/components/LineChart.tsx" ]; then cp "src/components/LineChart.tsx" "src/components/LineChart.tsx.bak"; fi
cat > "src/components/LineChart.tsx" <<'TSX'
import { useMemo } from 'react';
import { View, useWindowDimensions } from 'react-native';
import Svg, { Path, Line, Circle, Text as SvgText, Defs, ClipPath, Rect, G } from 'react-native-svg';
import { theme } from '@/theme';

type Point = { t: number; v: number };
type Props = { data: Point[]; height?: number; gridLines?: number; };

const fmtEUR = (n: number) =>
  new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n);

// Light smoothing to avoid "childish" zig-zag: moving average
function smooth(values: number[], window = 3) {
  const half = Math.floor(window / 2);
  return values.map((_, i) => {
    let s = 0, c = 0;
    for (let k = -half; k <= half; k++) {
      const j = i + k;
      if (j >= 0 && j < values.length) { s += values[j]; c++; }
    }
    return s / (c || 1);
  });
}

export default function LineChart({ data, height = 200, gridLines = 4 }: Props) {
  const { width } = useWindowDimensions();
  const pad = 16;
  const innerW = Math.max(320, Math.min(width, 700)) - pad * 2;
  const w = innerW + pad * 2;
  const h = height;

  const { d, min, max, minPt, maxPt } = useMemo(() => {
    if (!data?.length) {
      return { d: '', min: 0, max: 0, minPt: { x: pad, y: h - pad }, maxPt: { x: pad, y: pad } };
    }
    const xs = data.map(p => p.t);
    const ysRaw = data.map(p => p.v);
    const ys = smooth(ysRaw, 5); // smoothed series
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const scaleX = (t: number) => pad + ((t - minX) / (maxX - minX || 1)) * innerW;
    const scaleY = (v: number) => pad + (1 - (v - minY) / (maxY - minY || 1)) * (h - pad * 2);

    const pts = xs.map((t, i) => ({ x: scaleX(t), y: scaleY(ys[i]) }));
    const d = pts.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ');

    const minIdx = ys.indexOf(minY), maxIdx = ys.indexOf(maxY);
    return {
      d,
      min: minY, max: maxY,
      minPt: { x: pts[minIdx].x, y: pts[minIdx].y },
      maxPt: { x: pts[maxIdx].x, y: pts[maxIdx].y },
    };
  }, [data, innerW, h]);

  const gridYs = Array.from({ length: gridLines }, (_, i) => pad + (i * (h - pad * 2)) / (gridLines - 1 || 1));

  return (
    <View style={{ backgroundColor: theme.colors.card }}>
      <Svg width={w} height={h}>
        <Defs>
          <ClipPath id="clip">
            <Rect x={pad} y={pad} width={innerW} height={h - pad * 2} />
          </ClipPath>
        </Defs>

        {/* Grid */}
        {gridYs.map((gy, i) => (
          <Line key={i} x1={pad} x2={w - pad} y1={gy} y2={gy} stroke={theme.colors.border} strokeWidth={0.75} />
        ))}

        <G clipPath="url(#clip)">
          {d ? <Path d={d} fill="none" stroke={theme.colors.navy} strokeWidth={1.25} /> : null}
        </G>

        {/* High/Low subtle labels inside the clip area */}
        <G clipPath="url(#clip)">
          <Circle cx={maxPt.x} cy={maxPt.y} r={2} fill={theme.colors.up} />
          <SvgText x={maxPt.x + 6} y={Math.max(maxPt.y - 6, pad + 10)} fontSize="10" fill={theme.colors.up}>
            H {fmtEUR(max)}
          </SvgText>
          <Circle cx={minPt.x} cy={minPt.y} r={2} fill={theme.colors.down} />
          <SvgText x={minPt.x + 6} y={Math.min(minPt.y + 12, h - pad)} fontSize="10" fill={theme.colors.down}>
            L {fmtEUR(min)}
          </SvgText>
        </G>
      </Svg>
    </View>
  );
}
TSX

############################################
# 5) Portfolio screen — white summary card, right-aligned day buttons, larger organized table
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

// calmer demo data
const now = Date.now();
const base = 12400;
const genData = (len: number) =>
  Array.from({ length: len }, (_, i) => ({
    t: now - (len - i) * 60_000,
    v: base + i * 4 + Math.sin(i / 6) * 12, // gentle drift + tiny variance
  }));

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

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      {/* Title block on a white card so text is ALWAYS on white */}
      <Card style={{ gap: 6 }}>
        <Text style={{ color: theme.colors.navy, fontSize: 16, fontWeight: '800' }}>Collection Value</Text>
        <Text style={{ color: theme.colors.navy, fontSize: 30, fontWeight: '800', letterSpacing: 0.2 }}>
          {fmtEUR(total)}
        </Text>
      </Card>

      {/* Chart + right-aligned day buttons in same white card */}
      <Card style={{ gap: theme.spacing.md }}>
        <RangeToggle options={['1D','7D','30D']} value={range} onChange={(v) => setRange(v as any)} />
        <LineChart data={data} />
      </Card>

      {/* Larger, organized table: header row + aligned columns */}
      <Card>
        <View style={{ flexDirection: 'row', paddingBottom: theme.spacing.sm, borderBottomWidth: 1, borderColor: theme.colors.border }}>
          <Text style={{ flex: 1, color: theme.colors.subtext, fontWeight: '700' }}>Name</Text>
          <Text style={{ width: 70, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>%</Text>
          <Text style={{ width: 100, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>Price</Text>
        </View>
        {SAMPLE.sort((a,b)=>b.price - a.price).map((row, idx) => (
          <View key={idx} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.md, borderBottomWidth: idx < SAMPLE.length - 1 ? 1 : 0, borderColor: theme.colors.border }}>
            <View style={{ flex: 1, paddingRight: theme.spacing.lg }}>
              <Text style={{ color: theme.colors.navy, fontWeight: '600' }}>{row.name}</Text>
            </View>
            <Text style={{ width: 70, textAlign: 'right', color: row.pct >= 0 ? theme.colors.up : theme.colors.down, fontWeight: '700' }}>
              {(row.pct >= 0 ? '+' : '') + row.pct.toFixed(2)}%
            </Text>
            <Text style={{ width: 100, textAlign: 'right', color: theme.colors.navy, fontWeight: '700' }}>
              {fmtEUR(row.price)}
            </Text>
          </View>
        ))}
      </Card>
    </ScrollView>
  );
}
TSX

############################################
# 6) Items page — professional table + header share handled in Tabs
############################################
if [ -f "app/(tabs)/items.tsx" ]; then cp "app/(tabs)/items.tsx" "app/(tabs)/items.tsx.bak"; fi
cat > "app/(tabs)/items.tsx" <<'TSX'
import { View, Text, ScrollView } from 'react-native';
import Card from '@/components/Card';
import ShieldBadge, { Tier } from '@/components/ShieldBadge';
import { theme } from '@/theme';

type Item = { name: string; pct: number; price: number; tier: Tier; };
type Group = { category: string; items: Item[]; };
const fmtEUR = (n: number) => new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(n);

const GROUPS: Group[] = [
  { category: 'Pokémon', items: [
      { name: 'PSA 9 Charizard', pct: 2.4, price: 1820, tier: 'platinum' },
      { name: 'Pikachu VMAX', pct: -0.8, price: 210, tier: 'gold' },
  ]},
  { category: 'Funko', items: [
      { name: 'Freddy Funko LE', pct: 1.1, price: 320, tier: 'gold' },
  ]},
];

export default function Items() {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      {GROUPS.map((g) => {
        const total = g.items.reduce((s, it) => s + it.price, 0);
        return (
          <Card key={g.category} style={{ gap: theme.spacing.md }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>{g.category}</Text>

            {/* Header row */}
            <View style={{ flexDirection: 'row', paddingBottom: theme.spacing.sm, borderBottomWidth: 1, borderColor: theme.colors.border }}>
              <Text style={{ flex: 1, color: theme.colors.subtext, fontWeight: '700' }}>Name</Text>
              <Text style={{ width: 70, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>%</Text>
              <Text style={{ width: 90, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>Tier</Text>
              <Text style={{ width: 100, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>Price</Text>
            </View>

            {g.items.map((it, idx) => (
              <View key={idx} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.md, borderBottomWidth: idx < g.items.length - 1 ? 1 : 0, borderColor: theme.colors.border }}>
                <Text style={{ flex: 1, color: theme.colors.navy, fontWeight: '600' }}>{it.name}</Text>
                <Text style={{ width: 70, textAlign: 'right', color: it.pct >= 0 ? theme.colors.up : theme.colors.down, fontWeight: '700' }}>
                  {(it.pct >= 0 ? '+' : '') + it.pct.toFixed(2)}%
                </Text>
                <View style={{ width: 90, alignItems: 'flex-end' }}>
                  <ShieldBadge tier={it.tier} />
                </View>
                <Text style={{ width: 100, textAlign: 'right', color: theme.colors.navy, fontWeight: '700' }}>{fmtEUR(it.price)}</Text>
              </View>
            ))}

            <View style={{ alignItems: 'flex-end' }}>
              <Text style={{ color: theme.colors.subtext, fontWeight: '700' }}>Total {fmtEUR(total)}</Text>
            </View>
          </Card>
        );
      })}
    </ScrollView>
  );
}
TSX

############################################
# 7) Add page — filled out form (all white cards)
############################################
if [ -f "app/(tabs)/add.tsx" ]; then cp "app/(tabs)/add.tsx" "app/(tabs)/add.tsx.bak"; fi
cat > "app/(tabs)/add.tsx" <<'TSX'
import { View, Text, ScrollView, Pressable, TextInput } from 'react-native';
import Card from '@/components/Card';
import { theme } from '@/theme';

export default function Add() {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      {/* Basic details */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>Item details</Text>
        <TextInput placeholder="Title" placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
        <TextInput placeholder="Category (e.g., Pokémon, Funko, LEGO)" placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
        <TextInput placeholder="Brand / Series" placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
        <TextInput placeholder="Condition (e.g., New, NM, Used)" placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
      </Card>

      {/* Pricing */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>Pricing</Text>
        <TextInput placeholder="Purchase price (EUR)" placeholderTextColor={theme.colors.subtext} keyboardType="decimal-pad"
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
        <TextInput placeholder="Estimated value (EUR)" placeholderTextColor={theme.colors.subtext} keyboardType="decimal-pad"
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
      </Card>

      {/* Description */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>Description</Text>
        <TextInput placeholder="Describe your item…" placeholderTextColor={theme.colors.subtext} multiline
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, height: 120, textAlignVertical: 'top' }} />
      </Card>

      {/* Actions */}
      <Card style={{ gap: theme.spacing.md }}>
        <View style={{ flexDirection: 'row', gap: theme.colors ? 12 : 12, justifyContent: 'space-between' }}>
          <Pressable style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Detect category</Text>
          </Pressable>
          <Pressable style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Prefill (mock)</Text>
          </Pressable>
        </View>
        <View style={{ alignItems: 'center' }}>
          <Pressable style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Save</Text>
          </Pressable>
        </View>
      </Card>
    </ScrollView>
  );
}
TSX

echo "→ UX refresh complete."
