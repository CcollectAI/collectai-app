#!/usr/bin/env bash
set -euo pipefail
ts="$(date -u +%Y%m%d-%H%M%S)"

echo "→ Install light runtime deps (Expo-managed, small footprint)"
npx expo install react-native-svg @react-native-async-storage/async-storage expo-file-system expo-sharing expo-image-picker >/dev/null

echo "→ Storage helpers (AsyncStorage JSON get/set)"
mkdir -p src/lib
cat > src/lib/storage.ts <<'TS'
import AsyncStorage from '@react-native-async-storage/async-storage';

export async function getJSON<T>(key: string, fallback: T): Promise<T> {
  try {
    const s = await AsyncStorage.getItem(key);
    return s ? (JSON.parse(s) as T) : fallback;
  } catch { return fallback; }
}
export async function setJSON<T>(key: string, value: T): Promise<void> {
  try { await AsyncStorage.setItem(key, JSON.stringify(value)); } catch {}
}
TS

echo "→ Items store (minimal, no external libs)"
mkdir -p src/store
cat > src/store/items.ts <<'TS'
import { useEffect, useMemo, useState } from 'react';
import { getJSON, setJSON } from '@/lib/storage';

export type Item = {
  id: string;
  category: string;
  name: string;
  price: number;
  pct?: number;
  tier?: 'silver'|'gold'|'platinum';
};

const KEY = 'items.v1';

export async function addItem(it: Omit<Item,'id'>): Promise<Item[]> {
  const curr = await getJSON<Item[]>(KEY, []);
  const next: Item[] = [...curr, { ...it, id: String(Date.now()) }];
  await setJSON(KEY, next);
  return next;
}
export async function listItems(): Promise<Item[]> {
  return getJSON<Item[]>(KEY, []);
}

export function useItems(): Item[] {
  const [items, setItems] = useState<Item[]>([]);
  useEffect(() => { listItems().then(setItems); }, []);
  return items;
}

export function useItemsWithSeed(seed: Item[]): Item[] {
  const user = useItems();
  return useMemo(() => {
    // merge by simple concat; real app would de-dupe by id
    return [...seed, ...user];
  }, [user, seed]);
}

export function groupByCategory(items: Item[]) {
  const map = new Map<string, Item[]>();
  for (const it of items) {
    map.set(it.category, [...(map.get(it.category)||[]), it]);
  }
  return Array.from(map.entries()).map(([category, items]) => {
    const tier: Item['tier'] = (items.some(i => i.price > 1500) ? 'platinum'
                         : items.some(i => i.price > 400) ? 'gold'
                         : 'silver');
    return { category, items, tier };
  });
}
TS

echo "→ CSV export helper + save/share"
mkdir -p src/export
cat > src/export/csv.ts <<'TS'
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';

type Row = { category: string; name: string; priceEUR: number; pct?: number };

const fmt = (v: unknown) => {
  if (v == null) return '';
  const s = String(v);
  return /[,"\n]/.test(s) ? `"${s.replace(/"/g,'""')}"` : s;
};

export function rowsToCSV(rows: Row[]): string {
  const head = ['Category','Name','Price (EUR)','Change %'];
  const lines = [head.join(',')];
  for (const r of rows) {
    lines.push([fmt(r.category), fmt(r.name), fmt(r.priceEUR), fmt(typeof r.pct==='number'? r.pct.toFixed(2) : '')].join(','));
  }
  return lines.join('\n');
}

export async function saveCSVAndShare(filename: string, csv: string): Promise<string> {
  const path = FileSystem.cacheDirectory! + filename;
  await FileSystem.writeAsStringAsync(path, csv, { encoding: FileSystem.EncodingType.UTF8 });
  try {
    const can = await Sharing.isAvailableAsync();
    if (can) await Sharing.shareAsync(path, { mimeType: 'text/csv', dialogTitle: filename });
  } catch {}
  return path;
}
TS

echo "→ Prediction stub (used by Add after image capture)"
cat > src/lib/predict.ts <<'TS'
export type Prediction = { category: string; title?: string; priceHint?: number; confidence: number };
const CATS = ['Pokémon','Funko','LEGO','Diecast','Sports Cards','Comics','Other'];

export async function predictFromImage(_uri: string): Promise<Prediction> {
  // mock: pick a category deterministically from uri hash
  let h = 0; for (let i=0;i<_uri.length;i++) h = (h*31 + _uri.charCodeAt(i))>>>0;
  const category = CATS[h % CATS.length];
  const priceHint = 100 + (h % 20) * 50;
  const confidence = 0.72;
  const title = category === 'Pokémon' ? 'PSA 9 Charizard' :
                category === 'LEGO' ? 'LEGO Starfighter 75218' :
                'Collector Item';
  await new Promise(r=>setTimeout(r, 450));
  return { category, title, priceHint, confidence };
}
TS

echo "→ SVG LineChart (gridlines, clamp, hi/low badges, touch tooltip)"
mkdir -p src/components
cat > src/components/LineChart.tsx <<'TSX'
import React, { useMemo, useRef, useState } from 'react';
import { View, Text, PanResponder, LayoutChangeEvent } from 'react-native';
import Svg, { Path, Rect, Defs, ClipPath, G, Line, Circle } from 'react-native-svg';
import { theme } from '@/theme';

export type Point = { t: number; y: number };
export default function LineChart({
  data,
  height = 160,
  padding = 16,
  gridY = 4,
  gridX = 6,
  currency = 'EUR',
}: { data: Point[]; height?: number; padding?: number; gridY?: number; gridX?: number; currency?: string; }) {
  const [w, setW] = useState(0);
  const [cursor, setCursor] = useState<{x:number; y:number; i:number} | null>(null);
  const onLayout = (e: LayoutChangeEvent) => setW(e.nativeEvent.layout.width);

  const { path, minY, maxY, scaleX, scaleY, hi, lo } = useMemo(() => {
    const xs = data.map(d=>d.t); const ys = data.map(d=>d.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY0 = Math.min(...ys), maxY0 = Math.max(...ys);
    const padY = (maxY0 - minY0) * 0.08 || 1; // avoid zero
    const minY = minY0 - padY, maxY = maxY0 + padY;

    const scaleX = (x:number) => {
      if (w<=0) return padding;
      return padding + (x - minX) / (maxX - minX || 1) * (w - padding*2);
    };
    const scaleY = (y:number) => {
      const h = height - padding*2;
      const v = (1 - (y - minY) / (maxY - minY || 1)) * h;
      return padding + Math.max(0, Math.min(h, v));
    };

    let d = '';
    data.forEach((p, i) => {
      const X = scaleX(p.t), Y = scaleY(p.y);
      d += (i===0 ? `M ${X} ${Y}` : ` L ${X} ${Y}`);
    });

    // hi/low
    let hiI = 0, loI = 0;
    for (let i=1;i<data.length;i++){
      if (data[i].y > data[hiI].y) hiI = i;
      if (data[i].y < data[loI].y) loI = i;
    }

    return { path: d, minY, maxY, scaleX, scaleY, hi: hiI, lo: loI };
  }, [data, w, height, padding]);

  const pan = useRef(PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onPanResponderGrant: e => { const x = e.nativeEvent.locationX; moveCursor(x); },
    onPanResponderMove: e => { const x = e.nativeEvent.locationX; moveCursor(x); },
    onPanResponderRelease: () => setCursor(null),
  })).current;

  const moveCursor = (x:number) => {
    if (w<=0) return;
    // find nearest point
    let nearest = 0, best = Infinity;
    data.forEach((p,i)=>{
      const px = w > 0 ? padding + (p.t - data[0].t) / ((data[data.length-1].t - data[0].t) || 1) * (w - padding*2) : 0;
      const dist = Math.abs(px - x);
      if (dist < best) { best = dist; nearest = i; }
    });
    const p = data[nearest];
    setCursor({ x: scaleX(p.t), y: scaleY(p.y), i: nearest });
  };

  const fmtEUR0_US = (n:number) =>
    new Intl.NumberFormat('en-US', { style:'currency', currency: 'EUR', minimumFractionDigits:0, maximumFractionDigits:0 }).format(n);

  return (
    <View onLayout={onLayout} style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border }}>
      <Svg height={height} width="100%" {...pan.panHandlers}>
        <Defs>
          <ClipPath id="clip">
            <Rect x={padding} y={padding} width={Math.max(0, w - padding*2)} height={height - padding*2} />
          </ClipPath>
        </Defs>

        {/* Grid */}
        <G>
          {Array.from({length: gridY+1}).map((_,i)=>{
            const y = padding + i*(height - padding*2)/gridY;
            return <Line key={'gy'+i} x1={padding} x2={Math.max(padding, w - padding)} y1={y} y2={y} stroke={theme.colors.border} strokeWidth={1} />;
          })}
          {Array.from({length: gridX+1}).map((_,i)=>{
            const x = padding + i*(Math.max(0, w - padding*2))/gridX;
            return <Line key={'gx'+i} y1={padding} y2={height - padding} x1={x} x2={x} stroke={theme.colors.border} strokeWidth={1} />;
          })}
        </G>

        {/* Line (clipped so it never exceeds chart) */}
        <G clipPath="url(#clip)">
          <Path d={path} stroke={theme.colors.navy} strokeWidth={2} fill="none" />
        </G>

        {/* Hi/Low badges */}
        {data.length>0 && (
          <>
            {/* High */}
            <G>
              <Circle cx={scaleX(data[hi].t)} cy={Math.max(padding, Math.min(height - padding, (()=>{
                // ensure inside
                return (height - padding*2) - (height - padding*2) * ((data[hi].y - minY) / ( (maxY - minY) || 1)) + padding;
              })()))} r={3} fill={theme.colors.up} />
              <TextBadge x={scaleX(data[hi].t)} y={Math.max(padding+10, (()=>{
                const h = height - padding*2;
                const v = padding + (1 - (data[hi].y - minY)/( (maxY - minY)||1))*h;
                return v - 18;
              })())} text={'H '+fmtEUR0_US(data[hi].y)} />
            </G>

            {/* Low */}
            <G>
              <Circle cx={scaleX(data[lo].t)} cy={Math.max(padding, Math.min(height - padding, (()=>{
                return (height - padding*2) - (height - padding*2) * ((data[lo].y - minY) / ( (maxY - minY) || 1)) + padding;
              })()))} r={3} fill={theme.colors.down} />
              <TextBadge x={scaleX(data[lo].t)} y={Math.min(height - padding - 10, (()=>{
                const h = height - padding*2;
                const v = padding + (1 - (data[lo].y - minY)/( (maxY - minY)||1))*h;
                return v + 6;
              })())} text={'L '+fmtEUR0_US(data[lo].y)} />
            </G>
          </>
        )}

        {/* Cursor */}
        {cursor && (
          <G pointerEvents="none">
            <Line x1={cursor.x} x2={cursor.x} y1={padding} y2={height - padding} stroke={theme.colors.navy} strokeDasharray="3 3" />
            <Circle cx={cursor.x} cy={cursor.y} r={4} fill="#fff" stroke={theme.colors.navy} />
          </G>
        )}
      </Svg>

      {/* Tooltip */}
      {cursor && (
        <View style={{ position:'absolute', left: Math.max(padding, Math.min((cursor.x - 48), (w - 96))), top: 6, backgroundColor:'#fff', borderWidth:1, borderColor: theme.colors.border, paddingHorizontal:8, paddingVertical:4 }}>
          <Text style={{ color: theme.colors.navy, fontWeight:'700' }}>{fmtEUR0_US(data[cursor.i].y)}</Text>
        </View>
      )}
    </View>
  );
}

function TextBadge({ x, y, text }:{x:number; y:number; text:string}) {
  // Render as absolutely-positioned RN view over the SVG (crisp text)
  return (
    <View style={{ position:'absolute', left: x - 32, top: y - 10, backgroundColor:'#fff', borderWidth:1, borderColor: theme.colors.border, paddingHorizontal:6, paddingVertical:2 }}>
      <Text style={{ color: theme.colors.navy, fontSize: 10, fontWeight: '700' }}>{text}</Text>
    </View>
  );
}
TSX

echo "→ Portfolio screen uses LineChart + right-aligned ranges + watchlist"
mkdir -p app/(tabs)
[ -f "app/(tabs)/index.tsx" ] && cp "app/(tabs)/index.tsx" "app/(tabs)/index.tsx.bak.$ts"
cat > app/(tabs)/index.tsx <<'TSX'
import { useMemo, useState } from 'react';
import { View, Text, ScrollView, Pressable } from 'react-native';
import LineChart, { Point } from '@/components/LineChart';
import Card from '@/components/Card';
import Icon from '@/components/Icon';
import { theme } from '@/theme';

const now = Date.now();
const mk = (n:number, step:number, jitter=0) => Array.from({length:n}, (_,i)=>({ t: now - (n-1-i)*step, y: 1500 + Math.sin(i/3)*60 + Math.cos(i/5)*30 + (jitter? (i%7)*2 : 0)}));
const DATA_1D: Point[] = mk(24, 60*60*1000);
const DATA_7D: Point[] = mk(7, 24*60*60*1000);
const DATA_30D: Point[] = mk(30, 24*60*60*1000, 1);

const fmtEUR0_US = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

export default function Portfolio() {
  const [range, setRange] = useState<'1D'|'7D'|'30D'>('7D');
  const data = range==='1D'?DATA_1D:range==='7D'?DATA_7D:DATA_30D;

  const total = useMemo(()=> data[data.length-1].y * 1.0, [data]); // mock value
  const pct = useMemo(()=> ((data[data.length-1].y - data[0].y)/data[0].y)*100, [data]);

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}>

      {/* Title block */}
      <View style={{ flexDirection:'row', alignItems:'flex-start', justifyContent:'space-between' }}>
        <View>
          <Text style={{ color: theme.colors.navy, fontWeight:'800', fontSize: 16, backgroundColor: theme.colors.card, paddingHorizontal:8, paddingVertical:4 }}>
            Collection Value
          </Text>
          <Text style={{ color: theme.colors.navy, fontWeight:'700', fontSize: 20, marginTop: 6 }}>
            {fmtEUR0_US(total)}
          </Text>
          <Text style={{ marginTop: 2, color: pct>=0? theme.colors.up : theme.colors.down, fontWeight:'700' }}>
            {(pct>=0?'+':'') + pct.toFixed(2)}% today
          </Text>
        </View>

        {/* Range toggle (right-aligned) */}
        <View style={{ flexDirection:'row', gap: 8 }}>
          {(['1D','7D','30D'] as const).map(r=>{
            const active = r===range;
            return (
              <Pressable key={r} onPress={()=>setRange(r)} style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: active? theme.colors.navy : theme.colors.border, paddingVertical: 4, paddingHorizontal: 10 }}>
                <Text style={{ color: active? theme.colors.navy : theme.colors.subtext, fontWeight: active? '800':'600' }}>{r}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      {/* Chart */}
      <LineChart data={data} height={170} />

      {/* Items title (white box) */}
      <Text style={{ color: theme.colors.navy, fontWeight:'800', backgroundColor:'#fff', alignSelf:'flex-start', paddingHorizontal:8, paddingVertical:4 }}>
        Items
      </Text>

      {/* Collection list (simple, tidy) */}
      <Card style={{ padding: theme.spacing.md }}>
        <View style={{ flexDirection:'row', alignItems:'center', paddingBottom: 8, borderBottomWidth:1, borderColor: theme.colors.border }}>
          <Text style={{ flex:1, color: theme.colors.subtext, fontWeight:'700' }}>Name</Text>
          <Text style={{ width:100, textAlign:'right', color: theme.colors.subtext, fontWeight:'700' }}>Price</Text>
        </View>
        {[
          { name:'PSA 9 Charizard', pct:+2.4, price:1820 },
          { name:'Pikachu VMAX', pct:-0.8, price:210 },
          { name:'Freddy Funko LE', pct:+1.1, price:320 },
        ].map((r,i)=>(
          <View key={i} style={{ flexDirection:'row', alignItems:'center', paddingVertical:10, borderBottomWidth: i<2?1:0, borderColor: theme.colors.border }}>
            <View style={{ flex:1, paddingRight:12 }}>
              <Text style={{ color: theme.colors.navy, fontWeight:'600' }}>{r.name}</Text>
              <Text style={{ fontSize:12, color: r.pct>=0? theme.colors.up: theme.colors.down, marginTop:2 }}>
                {(r.pct>=0?'+':'') + r.pct.toFixed(2)}%
              </Text>
            </View>
            <Text style={{ width:100, textAlign:'right', color: theme.colors.navy, fontWeight:'700' }}>{fmtEUR0_US(r.price)}</Text>
          </View>
        ))}
      </Card>

      {/* Watchlist */}
      <Card style={{ gap: 8 }}>
        <Text style={{ color: theme.colors.navy, fontWeight:'700' }}>Watchlist</Text>
        {[
          { title:'Charizard alt art PSA 10', price: 2400 },
          { title:'LEGO UCS Falcon', price: 650 },
        ].map((w,i)=>(
          <View key={i} style={{ flexDirection:'row', alignItems:'center', justifyContent:'space-between' }}>
            <Text style={{ color: theme.colors.navy }}>{w.title}</Text>
            <Text style={{ color: theme.colors.subtext }}>{fmtEUR0_US(w.price)}</Text>
          </View>
        ))}
        <Pressable style={{ alignSelf:'center', borderWidth:1, borderColor: theme.colors.navy, paddingHorizontal:16, paddingVertical:6, marginTop: 4 }}>
          <View style={{ flexDirection:'row', gap:6, alignItems:'center' }}>
            <Icon name="add-circle-outline" />
            <Text style={{ color: theme.colors.navy, fontWeight:'700' }}>Add to watchlist</Text>
          </View>
        </Pressable>
      </Card>
    </ScrollView>
  );
}
TSX

echo "→ Items screen: wire CSV export & share, merge with stored items"
[ -f "app/(tabs)/items.tsx" ] && cp "app/(tabs)/items.tsx" "app/(tabs)/items.tsx.bak.$ts"
cat > app/(tabs)/items.tsx <<'TSX'
import { View, Text, ScrollView, Pressable, Share } from 'react-native';
import Icon from '@/components/Icon';
import ShieldBadge, { Tier } from '@/components/ShieldBadge';
import Card from '@/components/Card';
import { theme } from '@/theme';
import { useItemsWithSeed, groupByCategory } from '@/store/items';
import { rowsToCSV, saveCSVAndShare } from '@/export/csv';

type SeedItem = { category: string; name: string; pct?: number; price: number; tier: Tier };
const SEED: SeedItem[] = [
  { category:'Pokémon', name:'PSA 9 Charizard', pct: 2.4, price: 1820, tier: 'platinum' },
  { category:'Pokémon', name:'Pikachu VMAX', pct:-0.8, price: 210, tier: 'platinum' },
  { category:'Funko',   name:'Freddy Funko LE', pct: 1.1, price: 320, tier: 'gold' },
];

const fmtEUR0_US = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

export default function Items() {
  const userPlusSeed = useItemsWithSeed(SEED.map(s => ({
    id: 'seed-'+s.name,
    category: s.category,
    name: s.name,
    price: s.price,
    pct: s.pct,
    tier: s.tier
  } as any)));

  const groups = groupByCategory(userPlusSeed as any);

  const onShare = async () => { try { await Share.share({ message: 'Items overview from Collect AI' }); } catch {} };
  const onDownload = async () => {
    const rows = (groups as any[]).flatMap(g =>
      (g.items as any[]).map(it => ({ category: g.category, name: it.name, priceEUR: it.price, pct: it.pct }))
    );
    const csv = rowsToCSV(rows);
    await saveCSVAndShare('collectai-items.csv', csv);
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }}
      contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}>
      
      {/* Title row with in-page Share */}
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <Text style={{
          color: theme.colors.navy, fontWeight: '800', fontSize: 16,
          backgroundColor: theme.colors.card, paddingHorizontal: 8, paddingVertical: 4
        }}>
          Items
        </Text>
        <Pressable onPress={onShare} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <Icon name="share-outline" />
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Share</Text>
        </Pressable>
      </View>

      {groups.map((g:any) => {
        const total = g.items.reduce((s:number, it:any) => s + it.price, 0);
        return (
          <View key={g.category} style={{ gap: theme.spacing.xs }}>
            <Card style={{ padding: theme.spacing.md, gap: theme.spacing.sm }}>
              {/* Category header with right-aligned tier badge */}
              <View style={{
                flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
                paddingBottom: theme.spacing.xs, borderBottomWidth: 1, borderColor: theme.colors.border
              }}>
                <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>{g.category}</Text>
                <ShieldBadge tier={g.tier} />
              </View>

              {/* Table header */}
              <View style={{
                flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.xs,
                borderBottomWidth: 1, borderColor: theme.colors.border
              }}>
                <Text style={{ flex: 1, color: theme.colors.subtext, fontWeight: '700' }}>Name</Text>
                <Text style={{ width: 100, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>Price</Text>
              </View>

              {/* Rows */}
              {g.items.map((it:any, idx:number) => (
                <View key={idx} style={{
                  flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.sm,
                  borderBottomWidth: idx < g.items.length - 1 ? 1 : 0, borderColor: theme.colors.border
                }}>
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

            {/* Category total beneath the card (not inside) */}
            <View style={{ alignItems: 'flex-end' }}>
              <Text style={{ color: theme.colors.subtext, fontWeight: '700' }}>
                Total {fmtEUR0_US(total)}
              </Text>
            </View>
          </View>
        );
      })}

      {/* Download overview button centered at bottom */}
      <View style={{ alignItems: 'center', marginTop: theme.spacing.sm, marginBottom: theme.spacing.xl }}>
        <Pressable onPress={onDownload} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Download overview</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
TSX

echo "→ Add screen: camera first, prediction prefill, manual fields + notes; save→Items"
[ -f "app/(tabs)/add.tsx" ] && cp "app/(tabs)/add.tsx" "app/(tabs)/add.tsx.bak.$ts"
cat > app/(tabs)/add.tsx <<'TSX'
import { useState } from 'react';
import { View, Text, ScrollView, Pressable, TextInput, Alert, Image } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import CompactSelect from '@/components/CompactSelect';
import Card from '@/components/Card';
import Icon from '@/components/Icon';
import { theme } from '@/theme';
import { predictFromImage } from '@/lib/predict';
import { addItem } from '@/store/items';
import { router } from 'expo-router';

const CATEGORIES = ['Pokémon','Funko','LEGO','Diecast','Sports Cards','Comics','Other'];
const CONDITIONS = ['New','Near Mint','Good','Used','Damaged'];
const YEARS = Array.from({ length: 35 }, (_, i) => String(2025 - i)); // 2025..1991

export default function Add() {
  const [imageUri, setImageUri] = useState<string|undefined>();
  const [cat, setCat] = useState<string>('Pokémon');
  const [title, setTitle] = useState('');
  const [year, setYear] = useState<string>('2024');
  const [condition, setCondition] = useState('Near Mint');
  const [price, setPrice] = useState('');
  const [notes, setNotes] = useState('');

  const pickImage = async () => {
    const { granted } = await ImagePicker.requestCameraPermissionsAsync();
    if (!granted) {
      Alert.alert('Permission', 'Camera permission is required. You can still choose from gallery.');
    }
    const res = await ImagePicker.launchImageLibraryAsync({ quality: 0.7, allowsEditing: false });
    if (!res.canceled && res.assets?.[0]?.uri) {
      const uri = res.assets[0].uri;
      setImageUri(uri);
      // Predict and prefill
      const pred = await predictFromImage(uri);
      setCat(pred.category);
      if (pred.title && !title) setTitle(pred.title);
      if (pred.priceHint && !price) setPrice(String(Math.round(pred.priceHint)));
    }
  };

  const capture = async () => {
    const { granted } = await ImagePicker.requestCameraPermissionsAsync();
    if (!granted) {
      Alert.alert('Permission', 'Camera permission denied.');
      return;
    }
    const res = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (!res.canceled && res.assets?.[0]?.uri) {
      const uri = res.assets[0].uri;
      setImageUri(uri);
      const pred = await predictFromImage(uri);
      setCat(pred.category);
      if (pred.title && !title) setTitle(pred.title);
      if (pred.priceHint && !price) setPrice(String(Math.round(pred.priceHint)));
    }
  };

  const save = async () => {
    const p = Number(price || 0);
    if (!title || !cat || !p) {
      Alert.alert('Missing', 'Please add at least title, category and price.');
      return;
    }
    await addItem({ category: cat, name: title, price: p, pct: 0 });
    Alert.alert('Saved', 'Item added to your Items.', [{text:'OK', onPress:()=> router.push('/(tabs)/items') }]);
  };

  return (
    <ScrollView style={{ flex:1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      {/* Camera-first card */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Use AI Prediction & Take a picture</Text>
        <View style={{ flexDirection:'row', gap: theme.colors ? 12 : 12, flexWrap:'wrap' }}>
          <Pressable onPress={capture} style={{ borderWidth:1, borderColor: theme.colors.navy, paddingVertical: 8, paddingHorizontal: 16, flexDirection:'row', alignItems:'center', gap: 8 }}>
            <Icon name="add-circle-outline" />
            <Text style={{ color: theme.colors.navy, fontWeight:'700' }}>Capture</Text>
          </Pressable>
          <Pressable onPress={pickImage} style={{ borderWidth:1, borderColor: theme.colors.navy, paddingVertical: 8, paddingHorizontal: 16, flexDirection:'row', alignItems:'center', gap: 8 }}>
            <Icon name="image-outline" />
            <Text style={{ color: theme.colors.navy, fontWeight:'700' }}>Choose from Gallery</Text>
          </Pressable>
        </View>
        {imageUri ? <Image source={{ uri: imageUri }} style={{ width: '100%', height: 220, borderWidth:1, borderColor: theme.colors.border }} /> : null}
      </Card>

      {/* Manual inputs */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight:'700' }}>Manual details</Text>

        <View style={{ flexDirection:'row', gap: theme.spacing.md, flexWrap:'wrap' }}>
          <CompactSelect title="Category" options={CATEGORIES} value={cat} onChange={setCat} searchable />
          <CompactSelect title="Year" options={YEARS} value={year} onChange={setYear} />
          <CompactSelect title="Condition" options={CONDITIONS} value={condition} onChange={setCondition} />
        </View>

        <LabeledInput label="Title" value={title} onChangeText={setTitle} placeholder="e.g., PSA 9 Charizard" />
        <LabeledInput label="Price (€)" value={price} onChangeText={setPrice} keyboardType="numeric" placeholder="e.g., 1200" />
        <LabeledInput label="Notes" value={notes} onChangeText={setNotes} placeholder="Optional notes…" multiline />

        <View style={{ flexDirection:'row', gap: 12 }}>
          <Pressable onPress={save} style={{ borderWidth:1, borderColor: theme.colors.navy, paddingVertical: 10, paddingHorizontal: 16 }}>
            <Text style={{ color: theme.colors.navy, fontWeight:'700' }}>Save</Text>
          </Pressable>
        </View>
      </Card>
    </ScrollView>
  );
}

function LabeledInput(props: { label: string } & React.ComponentProps<typeof TextInput>) {
  const { label, ...rest } = props;
  return (
    <View style={{ gap: 6 }}>
      <Text style={{ color: theme.colors.navy, fontWeight:'700' }}>{label}</Text>
      <TextInput
        {...rest}
        placeholderTextColor={theme.colors.subtext}
        style={{ borderWidth:1, borderColor: theme.colors.border, padding: 10, backgroundColor: '#fff' }}
      />
    </View>
  );
}
TSX

echo "→ Commit & tag progress snapshot"
git add -A || true
git commit -m "[sprint1-next $ts] Chart polish, CSV export, Add camera+predict stub" || true
git tag -f "sprint1-next-$ts" || true

echo "✅ Done. Now restart Expo with a clean cache:"
echo "   npx expo start --tunnel --clear"
