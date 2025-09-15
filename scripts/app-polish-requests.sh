#!/usr/bin/env bash
set -euo pipefail

echo "→ Ensure deps for icons"
npx expo install @expo/vector-icons expo-font >/dev/null

############################################
# Root layout: load Ionicons + white header bar globally
############################################
[ -f app/_layout.tsx ] && cp app/_layout.tsx app/_layout.tsx.bak
cat > app/_layout.tsx <<'TSX'
import { Stack } from 'expo-router';
import { useEffect } from 'react';
import * as SplashScreen from 'expo-splash-screen';
import { useFonts } from 'expo-font';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

SplashScreen.preventAutoHideAsync().catch(()=>{});

export default function RootLayout() {
  // Load Ionicons so icons don't show as '?'
  const [fontsLoaded] = useFonts(Ionicons.font);

  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync().catch(()=>{});
  }, [fontsLoaded]);

  if (!fontsLoaded) return null;

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.card }, // white header bar
        headerTintColor: theme.colors.navy,
        headerTitleStyle: { fontWeight: '800' },
        contentStyle: { backgroundColor: theme.colors.bg },
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="_shelf/settings" options={{ title: 'Settings' }} />
    </Stack>
  );
}
TSX

############################################
# Tabs: safe Ionicons, header titles, white header bar
############################################
mkdir -p "app/(tabs)"
[ -f "app/(tabs)/_layout.tsx" ] && cp "app/(tabs)/_layout.tsx" "app/(tabs)/_layout.tsx.bak"
cat > "app/(tabs)/_layout.tsx" <<'TSX'
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Pressable, Share } from 'react-native';
import { theme } from '@/theme';
import { Link } from 'expo-router';

function SettingsButton() {
  return (
    <Link href="/_shelf/settings" asChild>
      <Pressable style={{ paddingHorizontal: 12 }}>
        <Ionicons name="settings-outline" size={20} color={theme.colors.navy} />
      </Pressable>
    </Link>
  );
}
function ShareButton() {
  const onShare = async () => { try { await Share.share({ message: 'Shared from Collect AI' }); } catch {} };
  return (
    <Pressable onPress={onShare} style={{ paddingHorizontal: 12 }}>
      <Ionicons name="share-outline" size={20} color={theme.colors.navy} />
    </Pressable>
  );
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: theme.colors.navy,
        tabBarInactiveTintColor: theme.colors.subtext,
        tabBarStyle: { backgroundColor: theme.colors.card, borderTopColor: theme.colors.border },
        headerStyle: { backgroundColor: theme.colors.card }, // white header bar, everywhere
        headerTitleStyle: { color: theme.colors.navy, fontWeight: '800' },
        headerTintColor: theme.colors.navy,
        sceneStyle: { backgroundColor: theme.colors.bg },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          // per request: replace "Collect AI" with "Portfolio"
          title: 'Portfolio',
          tabBarLabel: 'Portfolio',
          tabBarIcon: ({ color, size }) => <Ionicons name="bar-chart-outline" size={size} color={color} />,
          headerRight: () => <SettingsButton />,
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          // per request: Items page title becomes "Collect AI"
          title: 'Collect AI',
          tabBarIcon: ({ color, size }) => <Ionicons name="albums-outline" size={size} color={color} />,
          headerRight: () => <ShareButton />,
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
# LineChart: clip correctly + High/Low markers; tidy stroke
############################################
[ -f src/components/LineChart.tsx ] && cp src/components/LineChart.tsx src/components/LineChart.tsx.bak
cat > src/components/LineChart.tsx <<'TSX'
import { useMemo } from 'react';
import { View, useWindowDimensions } from 'react-native';
import Svg, { Path, Line, Circle, Text as SvgText, Defs, ClipPath, Rect, G } from 'react-native-svg';
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
const fmtEUR_US = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n);

export default function LineChart({ data, height = 180, gridLines = 4 }: Props) {
  const { width } = useWindowDimensions();
  const pad = 16;
  const innerW = Math.max(320, Math.min(width, 700)) - pad * 2;
  const w = innerW + pad * 2;
  const h = height;

  const { path, min, max, minPt, maxPt, gridYs } = useMemo(() => {
    if (!data?.length) {
      return {
        path: '', min: 0, max: 0,
        minPt: { x: pad, y: h - pad }, maxPt: { x: pad, y: pad },
        gridYs: Array.from({ length: gridLines }, (_, i) => pad + (i * (h - pad * 2)) / (gridLines - 1 || 1)),
      };
    }
    const xs = data.map(p => p.t);
    const ys = smooth(data.map(p => p.v), 5);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const scaleX = (t: number) => pad + ((t - minX) / (maxX - minX || 1)) * innerW;
    const scaleY = (v: number) => pad + (1 - (v - minY) / (maxY - minY || 1)) * (h - pad * 2);
    const pts = xs.map((t, i) => ({ x: scaleX(t), y: scaleY(ys[i]) }));
    const path = pts.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ');
    const minIdx = ys.indexOf(minY), maxIdx = ys.indexOf(maxY);
    return {
      path,
      min: minY, max: maxY,
      minPt: pts[minIdx], maxPt: pts[maxIdx],
      gridYs: Array.from({ length: gridLines }, (_, i) => pad + (i * (h - pad * 2)) / (gridLines - 1 || 1)),
    };
  }, [data, innerW, h, gridLines]);

  return (
    <View style={{ backgroundColor: theme.colors.card }}>
      <Svg width={w} height={h}>
        <Defs>
          <ClipPath id="clip">
            {/* strict clip so the line never bleeds */}
            <Rect x={pad} y={pad} width={innerW} height={h - pad * 2} />
          </ClipPath>
        </Defs>

        {/* Grid */}
        {gridYs.map((gy, i) => (
          <Line key={i} x1={pad} x2={w - pad} y1={gy} y2={gy} stroke={theme.colors.border} strokeWidth={0.75} />
        ))}

        {/* Line inside clip */}
        <G clipPath="url(#clip)">
          {path ? <Path d={path} fill="none" stroke={theme.colors.navy} strokeWidth={1.25} /> : null}
        </G>

        {/* High / Low markers (kept inside clip visually) */}
        <G clipPath="url(#clip)">
          <Circle cx={maxPt.x} cy={maxPt.y} r={2} fill={theme.colors.up} />
          <SvgText x={Math.min(maxPt.x + 6, w - pad - 60)} y={Math.max(maxPt.y - 6, pad + 10)} fontSize="10" fill={theme.colors.up}>
            H {fmtEUR_US(max)}
          </SvgText>
          <Circle cx={minPt.x} cy={minPt.y} r={2} fill={theme.colors.down} />
          <SvgText x={Math.min(minPt.x + 6, w - pad - 60)} y={Math.min(minPt.y + 12, h - pad)} fontSize="10" fill={theme.colors.down}>
            L {fmtEUR_US(min)}
          </SvgText>
        </G>
      </Svg>
    </View>
  );
}
TSX

############################################
# Portfolio screen: US numerics, remove '%' header column
############################################
[ -f "app/(tabs)/index.tsx" ] && cp "app/(tabs)/index.tsx" "app/(tabs)/index.tsx.bak"
cat > "app/(tabs)/index.tsx" <<'TSX'
import { useMemo, useState } from 'react';
import { View, Text, ScrollView } from 'react-native';
import Card from '@/components/Card';
import LineChart from '@/components/LineChart';
import RangeToggle from '@/components/RangeToggle';
import { theme } from '@/theme';

type Row = { name: string; pct: number; price: number; };
const fmtEUR_US = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'EUR' }).format(n);

// calm demo data
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

  // % Today (from 1D)
  const oneDay = DATASETS['1D'];
  const pctToday = useMemo(() => {
    if (!oneDay.length) return 0;
    const first = oneDay[0].v, last = oneDay[oneDay.length - 1].v;
    return ((last - first) / (first || 1)) * 100;
  }, [oneDay]);

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}>
      {/* Summary: title larger than number; US numerics for EUR */}
      <Card style={{ padding: theme.spacing.md, gap: 4 }}>
        <Text style={{ color: theme.colors.navy, fontSize: 20, fontWeight: '900' }}>Collection Value</Text>
        <Text style={{ color: theme.colors.navy, fontSize: 18, fontWeight: '700' }}>{fmtEUR_US(total)}</Text>
        <Text style={{ fontSize: 12, color: pctToday >= 0 ? theme.colors.up : theme.colors.down }}>
          {(pctToday >= 0 ? '+' : '') + pctToday.toFixed(2)}% Today
        </Text>
      </Card>

      {/* Chart card - tidy, clipped; range buttons right-aligned */}
      <Card style={{ padding: theme.spacing.md, gap: theme.spacing.md }}>
        <RangeToggle options={['1D','7D','30D']} value={range} onChange={(v) => setRange(v as any)} />
        <LineChart data={data} />
      </Card>

      {/* Items title */}
      <Text style={{ color: theme.colors.navy, fontWeight: '800', marginLeft: theme.spacing.sm }}>Items</Text>

      {/* Organized table: remove '%' column (keep % under name) */}
      <Card style={{ padding: theme.spacing.md }}>
        <View style={{ flexDirection: 'row', paddingBottom: theme.spacing.sm, borderBottomWidth: 1, borderColor: theme.colors.border }}>
          <Text style={{ flex: 1, color: theme.colors.subtext, fontWeight: '700' }}>Name</Text>
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
              {fmtEUR_US(row.price)}
            </Text>
          </View>
        ))}
      </Card>
    </ScrollView>
  );
}
TSX

############################################
# Items screen: header title Collect AI (white), share in header, total under card
############################################
[ -f "app/(tabs)/items.tsx" ] && cp "app/(tabs)/items.tsx" "app/(tabs)/items.tsx.bak"
cat > "app/(tabs)/items.tsx" <<'TSX'
import { View, Text, ScrollView } from 'react-native';
import Card from '@/components/Card';
import ShieldBadge, { Tier } from '@/components/ShieldBadge';
import { theme } from '@/theme';
import { useItems, groupByCategory } from '@/store/items';

type Item = { name: string; pct?: number; price: number };
type Group = { category: string; tier: Tier; items: Item[] };

const fmtEUR0_US = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

// seed merged with user items
const SEED: Group[] = [
  { category: 'Pokémon', tier: 'platinum', items: [
    { name: 'PSA 9 Charizard', pct: 2.4, price: 1820 },
    { name: 'Pikachu VMAX', pct: -0.8, price: 210 },
  ]},
  { category: 'Funko', tier: 'gold', items: [
    { name: 'Freddy Funko LE', pct: 1.1, price: 320 },
  ]},
];

export default function Items() {
  const userItems = useItems();
  const userGroups = groupByCategory(userItems).map(g => ({
    category: g.category,
    tier: g.tier,
    items: g.items.map(i => ({ name: i.name, pct: i.pct, price: i.price })),
  }));

  const merged: Group[] = (() => {
    const byCat = new Map<string, Group>();
    for (const g of SEED) byCat.set(g.category, { ...g, items: [...g.items] });
    for (const g of userGroups) {
      const existing = byCat.get(g.category);
      if (existing) existing.items.push(...g.items);
      else byCat.set(g.category, g);
    }
    return Array.from(byCat.values());
  })();

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      {/* Inline title row aligned with (header) share button; also white bg via global header */}
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16, backgroundColor: theme.colors.card, paddingHorizontal: 8, paddingVertical: 4 }}>
          Collect AI
        </Text>
        {/* header already has Share button; this inline keeps the layout balanced visually */}
      </View>

      {merged.map((g) => {
        const total = g.items.reduce((s, it) => s + it.price, 0);
        return (
          <View key={g.category} style={{ gap: theme.spacing.sm }}>
            <Card style={{ gap: theme.spacing.md, padding: theme.spacing.md }}>
              {/* Category header: name left, shield right */}
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingBottom: theme.spacing.sm, borderBottomWidth: 1, borderColor: theme.colors.border }}>
                <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>{g.category}</Text>
                <ShieldBadge tier={g.tier} />
              </View>

              {/* Table header (no % column; % lives under name) */}
              <View style={{ flexDirection: 'row', paddingVertical: theme.spacing.sm, borderBottomWidth: 1, borderColor: theme.colors.border, alignItems: 'center' }}>
                <Text style={{ flex: 1, color: theme.colors.subtext, fontWeight: '700' }}>Name</Text>
                <Text style={{ width: 100, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>Price</Text>
              </View>

              {g.items.map((it, idx) => (
                <View key={idx} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.md, borderBottomWidth: idx < g.items.length - 1 ? 1 : 0, borderColor: theme.colors.border }}>
                  <View style={{ flex: 1, paddingRight: theme.spacing.md }}>
                    <Text style={{ color: theme.colors.navy, fontWeight: '600' }}>{it.name}</Text>
                    {typeof it.pct === 'number' && (
                      <Text style={{ fontSize: 12, marginTop: 2, color: it.pct >= 0 ? theme.colors.up : theme.colors.down }}>
                        {(it.pct >= 0 ? '+' : '') + it.pct.toFixed(2)}%
                      </Text>
                    )}
                  </View>
                  <Text style={{ width: 100, textAlign: 'right', color: theme.colors.navy, fontWeight: '700' }}>
                    {fmtEUR0_US(it.price)}
                  </Text>
                </View>
              ))}
            </Card>

            {/* Total placed UNDER the category card (not part of the box) */}
            <View style={{ alignItems: 'flex-end' }}>
              <Text style={{ color: theme.colors.subtext, fontWeight: '700' }}>
                Total {fmtEUR0_US(total)}
              </Text>
            </View>
          </View>
        );
      })}
    </ScrollView>
  );
}
TSX

echo "→ Done. Headers are white, icons fixed, chart clipped with High/Low, US numerics applied, and Items layout updated."
