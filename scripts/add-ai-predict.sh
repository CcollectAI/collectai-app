#!/usr/bin/env bash
set -euo pipefail

echo "→ Installing lightweight deps for camera & dropdowns"
npx expo install expo-image-picker @react-native-picker/picker >/dev/null

echo "→ Create store for items (shared between Add & Items)"
mkdir -p src/store
cat > src/store/items.ts <<'TS'
import { useSyncExternalStore } from 'react';

export type NewItem = {
  category: string;
  name: string;
  price: number;      // estimated value shown in Items
  pct?: number;       // optional % vs purchase price
  notes?: string;
};
export type Item = NewItem & { id: string };

const state: { items: Item[] } = { items: [] };
const subs = new Set<() => void>();
const emit = () => subs.forEach((f) => f());

function subscribe(cb: () => void) { subs.add(cb); return () => subs.delete(cb); }
function getSnapshot() { return state.items; }

export function useItems() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
export function addItem(input: NewItem) {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2,8)}`;
  state.items.push({ id, ...input });
  emit();
}

// compute a simple tier by category total (no extra deps)
export type Tier = 'silver' | 'gold' | 'platinum';
export function tierFromTotal(total: number): Tier {
  if (total >= 1500) return 'platinum';
  if (total >= 500) return 'gold';
  return 'silver';
}

export function groupByCategory(items: Item[]) {
  const map = new Map<string, Item[]>();
  for (const it of items) {
    const arr = map.get(it.category) || [];
    arr.push(it);
    map.set(it.category, arr);
  }
  return Array.from(map.entries()).map(([category, items]) => {
    const total = items.reduce((s, it) => s + (it.price || 0), 0);
    return { category, items, total, tier: tierFromTotal(total) as Tier };
  });
}
TS

echo "→ Create mock predictor (stub) used after photo capture"
mkdir -p src/lib
cat > src/lib/predict.ts <<'TS'
export type Prediction = { category: string; estValue: number; confidence: number };
const CATS = ['Pokémon', 'Funko', 'LEGO', 'Diecast'];

export async function predictFromImage(_uri: string): Promise<Prediction> {
  // Mock: tiny delay + deterministic pseudo-score
  await new Promise(r => setTimeout(r, 300));
  const pick = CATS[Math.floor(Math.random() * CATS.length)];
  const est = pick === 'Pokémon' ? 850 + Math.floor(Math.random() * 1400)
           : pick === 'LEGO'     ? 300 + Math.floor(Math.random() * 1200)
           : pick === 'Diecast'  ? 120 + Math.floor(Math.random() * 400)
           :                        200 + Math.floor(Math.random() * 600);
  return { category: pick, estValue: est, confidence: 0.78 };
}
TS

echo "→ Update Items page to read from store and include newly added items"
if [ -f "app/(tabs)/items.tsx" ]; then cp "app/(tabs)/items.tsx" "app/(tabs)/items.tsx.bak"; fi
cat > "app/(tabs)/items.tsx" <<'TSX'
import { View, Text, ScrollView, Pressable, Share } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Card from '@/components/Card';
import ShieldBadge from '@/components/ShieldBadge';
import { theme } from '@/theme';
import { useItems, groupByCategory } from '@/store/items';

type Tier = 'silver' | 'gold' | 'platinum';
type Item = { name: string; pct?: number; price: number };
type Group = { category: string; tier: Tier; items: Item[] };

// Static seed (kept), will be merged with user-added
const SEED: Group[] = [
  { category: 'Pokémon', tier: 'platinum', items: [
    { name: 'PSA 9 Charizard', pct: 2.4, price: 1820 },
    { name: 'Pikachu VMAX', pct: -0.8, price: 210 },
  ]},
  { category: 'Funko', tier: 'gold', items: [
    { name: 'Freddy Funko LE', pct: 1.1, price: 320 },
  ]},
];

const fmtEUR0 = (n: number) =>
  new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

export default function Items() {
  const userItems = useItems();
  const userGroups = groupByCategory(userItems).map(g => ({
    category: g.category,
    tier: g.tier,
    items: g.items.map(i => ({ name: i.name, pct: i.pct, price: i.price })),
  }));

  // merge by category
  const merged: Group[] = (() => {
    const byCat = new Map<string, Group>();
    for (const g of SEED) byCat.set(g.category, { ...g, items: [...g.items] });
    for (const g of userGroups) {
      const existing = byCat.get(g.category);
      if (existing) {
        existing.items.push(...g.items);
      } else {
        byCat.set(g.category, g);
      }
    }
    return Array.from(byCat.values());
  })();

  const onShare = async () => {
    try { await Share.share({ message: 'My collection snapshot from Collect AI' }); } catch {}
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      {/* Top-right Share */}
      <View style={{ alignItems: 'flex-end' }}>
        <Pressable onPress={onShare} style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing.xs }}>
          <Ionicons name="share-outline" size={18} color={theme.colors.navy} />
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Share</Text>
        </Pressable>
      </View>

      {merged.map((g) => {
        const total = g.items.reduce((s, it) => s + it.price, 0);
        return (
          <Card key={g.category} style={{ gap: theme.spacing.md, padding: theme.spacing.md }}>
            {/* Category row: name left, single shield right */}
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingBottom: theme.spacing.sm, borderBottomWidth: 1, borderColor: theme.colors.border }}>
              <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>{g.category}</Text>
              <ShieldBadge tier={g.tier} />
            </View>

            {/* Table header + extra lines for tidy look */}
            <View style={{ flexDirection: 'row', paddingVertical: theme.spacing.sm, borderBottomWidth: 1, borderColor: theme.colors.border, alignItems: 'center' }}>
              <Text style={{ flex: 1, color: theme.colors.subtext, fontWeight: '700' }}>Name</Text>
              <View style={{ width: 1, alignSelf: 'stretch', backgroundColor: theme.colors.border, marginHorizontal: theme.spacing.md }} />
              <Text style={{ width: 100, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>Price</Text>
            </View>

            {g.items.map((it, idx) => (
              <View key={idx} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.md, borderBottomWidth: idx < g.items.length - 1 ? 1 : 0, borderColor: theme.colors.border }}>
                {/* Name (longest) with % under it */}
                <View style={{ flex: 1, paddingRight: theme.spacing.md }}>
                  <Text style={{ color: theme.colors.navy, fontWeight: '600' }}>{it.name}</Text>
                  {typeof it.pct === 'number' && (
                    <Text style={{ fontSize: 12, marginTop: 2, color: it.pct >= 0 ? theme.colors.up : theme.colors.down }}>
                      {(it.pct >= 0 ? '+' : '') + it.pct.toFixed(2)}%
                    </Text>
                  )}
                </View>

                <View style={{ width: 1, alignSelf: 'stretch', backgroundColor: theme.colors.border, marginHorizontal: theme.spacing.md }} />

                {/* Price (no decimals) */}
                <Text style={{ width: 100, textAlign: 'right', color: theme.colors.navy, fontWeight: '700' }}>
                  {fmtEUR0(it.price)}
                </Text>
              </View>
            ))}

            {/* Category total */}
            <View style={{ alignItems: 'flex-end', marginTop: theme.spacing.sm }}>
              <Text style={{ color: theme.colors.subtext, fontWeight: '700' }}>Total {fmtEUR0(total)}</Text>
            </View>
          </Card>
        );
      })}

      {/* Download overview (centered) */}
      <View style={{ alignItems: 'center', marginBottom: theme.spacing.xl }}>
        <Pressable onPress={() => {}} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Download overview</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
TSX

echo "→ Replace Add page with AI-first capture + manual fallback + notes + save-to-items"
if [ -f "app/(tabs)/add.tsx" ]; then cp "app/(tabs)/add.tsx" "app/(tabs)/add.tsx.bak"; fi
cat > "app/(tabs)/add.tsx" <<'TSX'
import { useState } from 'react';
import { View, Text, ScrollView, Pressable, TextInput, Image, Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Picker } from '@react-native-picker/picker';
import Card from '@/components/Card';
import { theme } from '@/theme';
import { addItem } from '@/store/items';
import { predictFromImage } from '@/lib/predict';
import { router } from 'expo-router';

const CATEGORIES = ['Pokémon', 'Funko', 'LEGO', 'Diecast'];
const CONDITIONS = ['New', 'Near Mint', 'Used', 'Damaged'];

export default function Add() {
  const [photo, setPhoto] = useState<string | null>(null);
  const [predCat, setPredCat] = useState<string | null>(null);
  const [predVal, setPredVal] = useState<number | null>(null);
  const [predicting, setPredicting] = useState(false);

  // Manual fields
  const [category, setCategory] = useState<string>('Pokémon');
  const [title, setTitle] = useState<string>('');
  const [condition, setCondition] = useState<string>('New');
  const [purchase, setPurchase] = useState<string>('');   // string for TextInput
  const [estValue, setEstValue] = useState<string>('');   // overridable
  const [notes, setNotes] = useState<string>('');

  const fmtEUR0 = (n: number) => new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0, minimumFractionDigits: 0 }).format(n);

  const handlePick = async (mode: 'camera' | 'library') => {
    try {
      if (mode === 'camera') {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') return Alert.alert('Permission needed', 'Camera access is required.');
        const res = await ImagePicker.launchCameraAsync({ quality: 0.6 });
        if (res.canceled) return;
        const uri = res.assets[0].uri;
        setPhoto(uri);
        await runPredict(uri);
      } else {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') return Alert.alert('Permission needed', 'Library access is required.');
        const res = await ImagePicker.launchImageLibraryAsync({ quality: 0.6 });
        if (res.canceled) return;
        const uri = res.assets[0].uri;
        setPhoto(uri);
        await runPredict(uri);
      }
    } catch (e) {
      Alert.alert('Error', 'Could not open camera or library.');
    }
  };

  const runPredict = async (uri: string) => {
    setPredicting(true);
    try {
      const p = await predictFromImage(uri);
      setPredCat(p.category);
      setPredVal(p.estValue);
    } finally {
      setPredicting(false);
    }
  };

  const applyPrediction = () => {
    if (predCat) setCategory(predCat);
    if (predVal !== null) setEstValue(String(predVal));
  };

  const onSave = () => {
    if (!title.trim()) return Alert.alert('Missing title', 'Please enter an item title.');
    const price = Number(estValue || 0);
    const buy = Number(purchase || 0);
    const pct = buy > 0 ? ((price - buy) / buy) * 100 : undefined;

    addItem({
      category,
      name: title.trim(),
      price: isNaN(price) ? 0 : Math.round(price),
      pct: typeof pct === 'number' && isFinite(pct) ? pct : undefined,
      notes: notes.trim() || undefined,
    });

    Alert.alert('Saved', 'Item added to your collection.', [
      { text: 'View Items', onPress: () => router.navigate('/(tabs)/items') },
      { text: 'OK' },
    ]);
    // Optionally reset form
    // setTitle(''); setPurchase(''); setEstValue(''); setNotes('');
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      {/* AI photo valuation — headline feature */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>
          Snap a photo — AI predicts category & value
        </Text>

        {/* Capture actions */}
        <View style={{ flexDirection: 'row', gap: theme.spacing.md }}>
          <Pressable onPress={() => handlePick('camera')} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Take photo</Text>
          </Pressable>
          <Pressable onPress={() => handlePick('library')} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Choose from library</Text>
          </Pressable>
        </View>

        {/* Preview + prediction */}
        {photo ? (
          <View style={{ gap: theme.spacing.sm }}>
            <Image source={{ uri: photo }} style={{ width: '100%', height: 200, borderWidth: 1, borderColor: theme.colors.border }} />
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <Text style={{ color: theme.colors.subtext }}>{predicting ? 'Predicting…' : predCat ? `Predicted: ${predCat}` : 'No prediction yet'}</Text>
              <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>
                {predVal != null ? fmtEUR0(predVal) : ''}
              </Text>
            </View>
            <View>
              <Pressable onPress={applyPrediction} disabled={!predCat && predVal==null} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl, opacity: (!predCat && predVal==null) ? 0.5 : 1 }}>
                <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Apply suggestion</Text>
              </Pressable>
            </View>
          </View>
        ) : null}
      </Card>

      {/* Manual entry — dropdowns first, then fields */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>Manual entry</Text>

        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Category</Text>
        <View style={{ borderWidth: 1, borderColor: theme.colors.border }}>
          <Picker selectedValue={category} onValueChange={(v) => setCategory(String(v))}>
            {CATEGORIES.map((c) => <Picker.Item key={c} label={c} value={c} />)}
          </Picker>
        </View>

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Item title</Text>
        <TextInput value={title} onChangeText={setTitle} placeholder="e.g., PSA 9 Charizard" placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Condition</Text>
        <View style={{ borderWidth: 1, borderColor: theme.colors.border }}>
          <Picker selectedValue={condition} onValueChange={(v) => setCondition(String(v))}>
            {CONDITIONS.map((c) => <Picker.Item key={c} label={c} value={c} />)}
          </Picker>
        </View>

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Purchase price (EUR)</Text>
        <TextInput value={purchase} onChangeText={setPurchase} keyboardType="decimal-pad" placeholder="e.g., 300" placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Estimated value (EUR)</Text>
        <TextInput value={estValue} onChangeText={setEstValue} keyboardType="decimal-pad" placeholder="e.g., 950" placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Notes</Text>
        <TextInput value={notes} onChangeText={setNotes} multiline placeholder="Any extra details..." placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, height: 100, textAlignVertical: 'top' }} />
      </Card>

      {/* Save */}
      <View style={{ alignItems: 'center' }}>
        <Pressable onPress={onSave} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Add to Items</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
TSX

echo "→ Done."
