#!/usr/bin/env bash
set -euo pipefail

echo "→ Ensuring folders…"
mkdir -p "app/(tabs)" app/_shelf components src src/auth

echo "→ Install deps…"
npx expo install react-native-svg @expo/vector-icons

echo "→ Theme + session stubs (safe)…"
if [ -f "src/theme.ts" ]; then cp "src/theme.ts" "src/theme.ts.bak"; fi
cat > "src/theme.ts" <<'TS'
export const theme = {
  colors: {
    brand: { base: "#1ABC9C" },
    navy: "#0B3D91",
    bg: "#E6F7F8",
    card: "#FFFFFF",
    text: "#0B3D91",
    subtext: "#64748B",
    up: "#10B981",
    down: "#EF4444",
    border: "#E5E7EB",
  },
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
};
TS

if [ -f "src/auth/session.ts" ]; then cp "src/auth/session.ts" "src/auth/session.ts.bak"; fi
cat > "src/auth/session.ts" <<'TS'
export type SessionState = { ready: boolean; signedIn: boolean };
export function useSession(): SessionState {
  return { ready: true, signedIn: true };
}
TS

echo "→ Root layout…"
if [ -f "app/_layout.tsx" ]; then cp "app/_layout.tsx" "app/_layout.tsx.bak"; fi
cat > "app/_layout.tsx" <<'TSX'
import { Stack } from 'expo-router';
import { theme } from '@/theme';

export default function RootLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.bg },
        headerTintColor: theme.colors.navy,
        headerTitleStyle: { fontWeight: '700' },
        contentStyle: { backgroundColor: theme.colors.bg },
      }}
    >
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="_shelf/settings" options={{ title: 'Settings' }} />
    </Stack>
  );
}
TSX

echo "→ Tabs layout (quoted path)…"
if [ -f "app/(tabs)/_layout.tsx" ]; then cp "app/(tabs)/_layout.tsx" "app/(tabs)/_layout.tsx.bak"; fi
cat > "app/(tabs)/_layout.tsx" <<'TSX'
import { Tabs, Link } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Pressable } from 'react-native';
import { theme } from '@/theme';

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: theme.colors.navy,
        tabBarInactiveTintColor: theme.colors.subtext,
        tabBarStyle: { backgroundColor: theme.colors.card, borderTopColor: theme.colors.border },
        headerStyle: { backgroundColor: theme.colors.bg },
        headerTitleStyle: { color: theme.colors.navy, fontWeight: '700' },
        headerTintColor: theme.colors.navy,
        sceneStyle: { backgroundColor: theme.colors.bg },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Portfolio',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="stats-chart-outline" size={size} color={color} />
          ),
          headerRight: () => (
            <Link href="/_shelf/settings" asChild>
              <Pressable style={{ paddingHorizontal: 12 }}>
                <Ionicons name="settings-outline" size={22} color={theme.colors.navy} />
              </Pressable>
            </Link>
          ),
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: 'Items',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="albums-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="add"
        options={{
          title: 'Add',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="add-circle-outline" size={size + 6} color={color} />
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

echo "→ Card component…"
if [ -f "components/Card.tsx" ]; then cp "components/Card.tsx" "components/Card.tsx.bak"; fi
cat > "components/Card.tsx" <<'TSX'
import { View, ViewProps } from 'react-native';
import { theme } from '@/theme';

export default function Card({ style, ...props }: ViewProps) {
  return (
    <View
      style={[{
        backgroundColor: theme.colors.card,
        padding: theme.spacing.lg,
        borderColor: theme.colors.border,
        borderWidth: 1,
      }, style]}
      {...props}
    />
  );
}
TSX

echo "→ Segmented control…"
if [ -f "components/Segmented.tsx" ]; then cp "components/Segmented.tsx" "components/Segmented.tsx.bak"; fi
cat > "components/Segmented.tsx" <<'TSX'
import { View, Pressable, Text } from 'react-native';
import { theme } from '@/theme';

type Props = { segments: string[]; value: string; onChange: (v: string) => void; };
export default function Segmented({ segments, value, onChange }: Props) {
  return (
    <View style={{ flexDirection: 'row', borderWidth: 1, borderColor: theme.colors.border }}>
      {segments.map((s) => {
        const active = s === value;
        return (
          <Pressable
            key={s}
            onPress={() => onChange(s)}
            style={{
              flex: 1,
              paddingVertical: theme.spacing.sm,
              alignItems: 'center',
              backgroundColor: active ? theme.colors.card : 'transparent',
            }}
          >
            <Text style={{ color: active ? theme.colors.navy : theme.colors.subtext, fontWeight: active ? '700' : '500' }}>
              {s}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
TSX

echo "→ Shield badge…"
if [ -f "components/ShieldBadge.tsx" ]; then cp "components/ShieldBadge.tsx" "components/ShieldBadge.tsx.bak"; fi
cat > "components/ShieldBadge.tsx" <<'TSX'
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

export type Tier = 'silver' | 'gold' | 'platinum';
export default function ShieldBadge({ tier }: { tier: Tier }) {
  const label = tier.charAt(0).toUpperCase() + tier.slice(1);
  const tint = tier === 'gold' ? '#EAB308' : tier === 'platinum' ? '#A3A3A3' : '#9CA3AF';
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing.xs }}>
      <Ionicons name="shield-outline" size={16} color={tint} />
      <Text style={{ color: theme.colors.subtext, fontWeight: '600' }}>{label}</Text>
    </View>
  );
}
TSX

echo "→ LineChart (SVG)…"
if [ -f "components/LineChart.tsx" ]; then cp "components/LineChart.tsx" "components/LineChart.tsx.bak"; fi
cat > "components/LineChart.tsx" <<'TSX'
import { useMemo } from 'react';
import { View } from 'react-native';
import Svg, { Path, Line, Circle, Text as SvgText } from 'react-native-svg';
import { theme } from '@/theme';

type Point = { t: number; v: number };
type Props = { data: Point[]; height?: number; gridLines?: number; };

export default function LineChart({ data, height = 180, gridLines = 4 }: Props) {
  const pad = 16;
  const w = 360;
  const h = height;

  const { path, min, max, minPt, maxPt } = useMemo(() => {
    if (!data.length) {
      return { path: '', min: 0, max: 0, minPt: { x: 0, y: 0 }, maxPt: { x: 0, y: 0 } };
    }
    const xs = data.map(d => d.t);
    const ys = data.map(d => d.v);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const scaleX = (t: number) => pad + ((t - minX) / (maxX - minX || 1)) * (w - pad * 2);
    const scaleY = (v: number) => pad + (1 - (v - minY) / (maxY - minY || 1)) * (h - pad * 2);

    const d = data.map((p, i) => `${i ? 'L' : 'M'} ${scaleX(p.t)} ${scaleY(p.v)}`).join(' ');
    const minIdx = ys.indexOf(minY), maxIdx = ys.indexOf(maxY);
    return {
      path: d, min: minY, max: maxY,
      minPt: { x: scaleX(data[minIdx].t), y: scaleY(minY) },
      maxPt: { x: scaleX(data[maxIdx].t), y: scaleY(maxY) },
    };
  }, [data, w, h]);

  const gridYs = Array.from({ length: gridLines }, (_, i) => pad + (i * (h - pad * 2)) / (gridLines - 1 || 1));

  return (
    <View style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border }}>
      <Svg width={w} height={h}>
        {gridYs.map((gy, i) => (
          <Line key={i} x1={pad} x2={w - pad} y1={gy} y2={gy} stroke={theme.colors.border} strokeWidth={1} />
        ))}
        {path ? <Path d={path} fill="none" stroke={theme.colors.navy} strokeWidth={2} /> : null}
        <Circle cx={maxPt.x} cy={maxPt.y} r={3} fill={theme.colors.up} />
        <SvgText x={maxPt.x + 6} y={maxPt.y - 6} fontSize="10" fill={theme.colors.up}>H €{max.toFixed(2)}</SvgText>
        <Circle cx={minPt.x} cy={minPt.y} r={3} fill={theme.colors.down} />
        <SvgText x={minPt.x + 6} y={minPt.y + 14} fontSize="10" fill={theme.colors.down}>L €{min.toFixed(2)}</SvgText>
      </Svg>
    </View>
  );
}
TSX

echo "→ Portfolio screen…"
if [ -f "app/(tabs)/index.tsx" ]; then cp "app/(tabs)/index.tsx" "app/(tabs)/index.tsx.bak"; fi
cat > "app/(tabs)/index.tsx" <<'TSX'
import { useMemo, useState } from 'react';
import { View, Text, ScrollView, Pressable } from 'react-native';
import Card from '@/components/Card';
import LineChart from '@/components/LineChart';
import { theme } from '@/theme';

type Row = { name: string; pct: number; price: number; };
const fmtEUR = (n: number) => new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(n);
const now = Date.now();
const genData = (len: number, base: number) =>
  Array.from({ length: len }, (_, i) => ({ t: now - (len - i) * 60_000, v: base + Math.sin(i / 3) * base * 0.02 + (i % 5) * 1.5 }));

const DATASETS = { '1D': genData(60, 12340), '7D': genData(60, 12480), '30D': genData(60, 12110) };
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
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      <View>
        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginBottom: 4 }}>Collection Value</Text>
        <Text style={{ color: theme.colors.navy, fontSize: 28, fontWeight: '800' }}>{fmtEUR(total)}</Text>
      </View>

      <Card>
        <View style={{ flexDirection: 'row', justifyContent: 'flex-end', gap: theme.spacing.sm, marginBottom: theme.spacing.md }}>
          {(['1D','7D','30D'] as const).map(k => (
            <Pressable key={k} onPress={() => setRange(k)} style={{
              paddingHorizontal: theme.spacing.md, paddingVertical: theme.spacing.xs,
              borderWidth: 1, borderColor: range === k ? theme.colors.navy : theme.colors.border,
              backgroundColor: range === k ? '#FFFFFF' : 'transparent',
            }}>
              <Text style={{ color: range === k ? theme.colors.navy : theme.colors.subtext, fontWeight: '700' }}>{k}</Text>
            </Pressable>
          ))}
        </View>
        <LineChart data={data} />
      </Card>

      <Card>
        <Text style={{ color: theme.colors.navy, fontWeight: '700', marginBottom: theme.spacing.md }}>Collection</Text>
        {SAMPLE.sort((a,b)=>b.price - a.price).map((row, idx) => (
          <View key={idx} style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: theme.spacing.sm, borderTopWidth: idx ? 1 : 0, borderColor: theme.colors.border }}>
            <View>
              <Text style={{ color: theme.colors.navy, fontWeight: '600' }}>{row.name}</Text>
              <Text style={{ fontSize: 12, color: row.pct >= 0 ? theme.colors.up : theme.colors.down }}>
                {(row.pct >= 0 ? '+' : '') + row.pct.toFixed(2)}%
              </Text>
            </View>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{fmtEUR(row.price)}</Text>
          </View>
        ))}
      </Card>

      <Card>
        <Text style={{ color: theme.colors.navy, fontWeight: '700', marginBottom: theme.spacing.md }}>Watchlist</Text>
        <View style={{ alignItems: 'center' }}>
          <Pressable style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>+ Add to watchlist</Text>
          </Pressable>
        </View>
      </Card>
    </ScrollView>
  );
}
TSX

echo "→ Items screen…"
if [ -f "app/(tabs)/items.tsx" ]; then cp "app/(tabs)/items.tsx" "app/(tabs)/items.tsx.bak"; fi
cat > "app/(tabs)/items.tsx" <<'TSX'
import { View, Text, ScrollView, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
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
      <View style={{ alignItems: 'flex-end' }}>
        <Pressable onPress={() => {}} style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing.xs }}>
          <Ionicons name="share-outline" size={18} color={theme.colors.navy} />
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Share</Text>
        </Pressable>
      </View>

      {GROUPS.map((g) => {
        const total = g.items.reduce((s, it) => s + it.price, 0);
        return (
          <Card key={g.category} style={{ gap: theme.spacing.sm }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>{g.category}</Text>
            {g.items.map((it, idx) => (
              <View key={idx} style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: theme.spacing.sm, borderTopWidth: idx ? 1 : 0, borderColor: theme.colors.border }}>
                <View>
                  <Text style={{ color: theme.colors.navy, fontWeight: '600' }}>{it.name}</Text>
                  <Text style={{ fontSize: 12, color: it.pct >= 0 ? theme.colors.up : theme.colors.down }}>
                    {(it.pct >= 0 ? '+' : '') + it.pct.toFixed(2)}%
                  </Text>
                </View>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing.lg }}>
                  <ShieldBadge tier={it.tier} />
                  <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{fmtEUR(it.price)}</Text>
                </View>
              </View>
            ))}
            <View style={{ alignItems: 'flex-end', marginTop: theme.spacing.sm }}>
              <Text style={{ color: theme.colors.subtext, fontWeight: '700' }}>Total {fmtEUR(total)}</Text>
            </View>
          </Card>
        );
      })}

      <View style={{ alignItems: 'center', marginTop: theme.spacing.md, marginBottom: theme.spacing.xl }}>
        <Pressable onPress={() => {}} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Download overview</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
TSX

echo "→ Add screen…"
if [ -f "app/(tabs)/add.tsx" ]; then cp "app/(tabs)/add.tsx" "app/(tabs)/add.tsx.bak"; fi
cat > "app/(tabs)/add.tsx" <<'TSX'
import { View, Text, ScrollView, Pressable, Image } from 'react-native';
import Card from '@/components/Card';
import { theme } from '@/theme';
import { useState } from 'react';

export default function Add() {
  const [photoUri, setPhotoUri] = useState<string | null>(null);

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      <Card style={{ alignItems: 'center', justifyContent: 'center' }}>
        <Pressable onPress={() => { /* TODO: ImagePicker */ }} style={{ padding: theme.spacing.lg, borderWidth: 1, borderColor: theme.colors.border }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{photoUri ? 'Change photo' : 'Tap to add photo'}</Text>
        </Pressable>
        {photoUri ? <Image source={{ uri: photoUri }} style={{ width: '100%', height: 200, marginTop: theme.spacing.md }} /> : null}
        <View style={{ marginTop: theme.spacing.md }}>
          <Pressable onPress={() => { /* TODO: detect category */ }} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Detect category</Text>
          </Pressable>
        </View>
      </Card>

      <Card style={{ gap: theme.spacing.sm }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800' }}>Details</Text>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>
          Fields adapt by category (e.g., Pokémon vs Funko vs LEGO). All values are overridable.
        </Text>
      </Card>
    </ScrollView>
  );
}
TSX

echo "→ Marketplace screen…"
if [ -f "app/(tabs)/marketplace.tsx" ]; then cp "app/(tabs)/marketplace.tsx" "app/(tabs)/marketplace.tsx.bak"; fi
cat > "app/(tabs)/marketplace.tsx" <<'TSX'
import { useState } from 'react';
import { View, Text, ScrollView, TextInput, Pressable } from 'react-native';
import Segmented from '@/components/Segmented';
import Card from '@/components/Card';
import { theme } from '@/theme';

export default function Marketplace() {
  const [seg, setSeg] = useState<'Chat'|'Search'|'Sell'>('Chat');

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      <Segmented segments={['Chat','Search','Sell']} value={seg} onChange={(v) => setSeg(v as any)} />

      {seg === 'Chat' && (
        <Card style={{ gap: theme.spacing.md }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Chat (mock)</Text>
          <View style={{ height: 180, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: '#fff' }} />
          <View style={{ flexDirection: 'row', gap: theme.spacing.sm }}>
            <TextInput placeholder="Message..." placeholderTextColor={theme.colors.subtext}
              style={{ flex: 1, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
            <Pressable style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingHorizontal: theme.spacing.lg, justifyContent: 'center' }}>
              <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Send</Text>
            </Pressable>
          </View>
        </Card>
      )}

      {seg === 'Search' && (
        <Card style={{ gap: theme.spacing.md }}>
          <TextInput placeholder="Search listings…" placeholderTextColor={theme.colors.subtext}
            style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
          <View style={{ borderTopWidth: 1, borderColor: theme.colors.border, paddingTop: theme.spacing.md }}>
            <Text style={{ color: theme.colors.subtext }}>Normalized results appear here.</Text>
          </View>
        </Card>
      )}

      {seg === 'Sell' && (
        <Card style={{ gap: theme.spacing.md }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Create listing</Text>
          <TextInput placeholder="Title" placeholderTextColor={theme.colors.subtext}
            style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
          <TextInput placeholder="Price (EUR)" placeholderTextColor={theme.colors.subtext} keyboardType="decimal-pad"
            style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
          <TextInput placeholder="Description" placeholderTextColor={theme.colors.subtext} multiline
            style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, height: 100, textAlignVertical: 'top' }} />
          <Pressable style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, alignItems: 'center' }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Publish (mock)</Text>
          </Pressable>
          <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>
            Guidance: add clear photos, verify category, confirm estimated price.
          </Text>
        </Card>
      )}
    </ScrollView>
  );
}
TSX

echo "→ Settings screen…"
if [ -f "app/_shelf/settings.tsx" ]; then cp "app/_shelf/settings.tsx" "app/_shelf/settings.tsx.bak"; fi
cat > "app/_shelf/settings.tsx" <<'TSX'
import { ScrollView, Text } from 'react-native';
import Card from '@/components/Card';
import { theme } from '@/theme';

export default function Settings() {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      <Card>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>Settings</Text>
        <Text style={{ color: theme.colors.subtext, marginTop: 8 }}>Coming soon.</Text>
      </Card>
    </ScrollView>
  );
}
TSX

echo "→ Done."
