#!/usr/bin/env bash
set -euo pipefail
ts="$(date -u +%Y%m%d-%H%M%S)"

echo "→ Update ShieldBadge to use tier colors on the shield icon"
mkdir -p src/components
[ -f "src/components/ShieldBadge.tsx" ] && cp "src/components/ShieldBadge.tsx" "src/components/ShieldBadge.tsx.bak.$ts"
cat > "src/components/ShieldBadge.tsx" <<'TSX'
import { View, Text } from 'react-native';
import Icon from '@/components/Icon';
import { theme } from '@/theme';

export type Tier = 'silver' | 'gold' | 'platinum';
const COLORS: Record<Tier, string> = {
  silver: '#C0C0C0',
  gold: '#D4AF37',
  platinum: '#B0BEC5',
};

export default function ShieldBadge({ tier }: { tier: Tier }) {
  const color = COLORS[tier];
  return (
    <View style={{
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: '#fff',
      borderWidth: 1,
      borderColor: color,
      paddingVertical: 2,
      paddingHorizontal: 6,
    }}>
      <Icon name="shield-outline" color={color} />
      <Text style={{ color: theme.colors.navy, fontWeight: '700', fontSize: 12, marginLeft: 4 }}>
        {tier[0].toUpperCase() + tier.slice(1)}
      </Text>
    </View>
  );
}
TSX

echo "→ Refresh Items screen (tighter spacing, colored badge, share button in-page)"
[ -f "app/(tabs)/items.tsx" ] && cp "app/(tabs)/items.tsx" "app/(tabs)/items.tsx.bak.$ts"
cat > "app/(tabs)/items.tsx" <<'TSX'
import { View, Text, ScrollView, Pressable, Share } from 'react-native';
import Icon from '@/components/Icon';
import ShieldBadge, { Tier } from '@/components/ShieldBadge';
import Card from '@/components/Card';
import { theme } from '@/theme';

type Item = { name: string; pct?: number; price: number };
type Group = { category: string; tier: Tier; items: Item[] };

const fmtEUR0_US = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

// NOTE: Replace with your real data hookup when ready
const DATA: Group[] = [
  { category: 'Pokémon', tier: 'platinum', items: [
    { name: 'PSA 9 Charizard', pct: 2.4, price: 1820 },
    { name: 'Pikachu VMAX', pct: -0.8, price: 210 },
  ]},
  { category: 'Funko', tier: 'gold', items: [
    { name: 'Freddy Funko LE', pct: 1.1, price: 320 },
  ]},
];

export default function Items() {
  const onShare = async () => { try { await Share.share({ message: 'Items overview from Collect AI' }); } catch {} };

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

      {DATA.map((g) => {
        const total = g.items.reduce((s, it) => s + it.price, 0);
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
              {g.items.map((it, idx) => (
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
        <Pressable style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Download overview</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
TSX

echo "→ Rebuild Marketplace with a proper Sell tab (vertical, tidy form)"
[ -f "app/(tabs)/marketplace.tsx" ] && cp "app/(tabs)/marketplace.tsx" "app/(tabs)/marketplace.tsx.bak.$ts"
cat > "app/(tabs)/marketplace.tsx" <<'TSX'
import { useState } from 'react';
import { View, Text, ScrollView, TextInput, Pressable, KeyboardAvoidingView, Platform, Alert } from 'react-native';
import Card from '@/components/Card';
import CompactSelect from '@/components/CompactSelect';
import Icon from '@/components/Icon';
import { theme } from '@/theme';

const CATEGORIES = ['Pokémon','Funko','LEGO','Diecast','Sports Cards','Comics','Other'];
const CONDITIONS = ['New','Near Mint','Good','Used','Damaged'];
const YEARS = Array.from({ length: 35 }, (_, i) => String(2025 - i)); // 2025..1991
const METHODS = ['Fixed Price','Auction'] as const;

function Segmented({ segments, value, onChange }:{segments:string[]; value:string; onChange:(v:string)=>void}) {
  return (
    <View style={{ flexDirection: 'row', borderWidth: 1, borderColor: theme.colors.border }}>
      {segments.map(s => {
        const active = s === value;
        return (
          <Pressable key={s} onPress={() => onChange(s)} style={{ flex: 1, paddingVertical: 8, backgroundColor: active ? theme.colors.card : theme.colors.bg }}>
            <Text style={{ textAlign: 'center', color: active ? theme.colors.navy : theme.colors.subtext, fontWeight: active ? '800' : '600' }}>{s}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export default function Marketplace() {
  const [seg, setSeg] = useState<'Chat'|'Search'|'Sell'>('Sell');
  return (
    <KeyboardAvoidingView behavior={Platform.select({ ios: 'padding', android: undefined })} style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
        <Segmented segments={['Chat','Search','Sell']} value={seg} onChange={(v)=>setSeg(v as any)} />
        {seg === 'Sell' ? <SellPane /> : (
          <Card><Text style={{ color: theme.colors.subtext }}>This tab is focused on Sell for now.</Text></Card>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function SellPane() {
  const [cat, setCat] = useState<string>('Pokémon');
  const [method, setMethod] = useState<typeof METHODS[number]>('Fixed Price');
  const [title, setTitle] = useState('');
  const [year, setYear] = useState<string>('2024');
  const [condition, setCondition] = useState('Near Mint');
  const [price, setPrice] = useState('');
  const [notes, setNotes] = useState('');

  const publish = () => {
    const payload = { cat, method, title, year, condition, price, notes };
    Alert.alert('Publish (mock)', JSON.stringify(payload, null, 2));
  };

  return (
    <Card style={{ gap: theme.spacing.md }}>
      <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Sell an item</Text>

      {/* Inputs in vertical, tidy layout */}
      <View style={{ gap: theme.spacing.sm }}>
        <View style={{ flexDirection: 'row', gap: theme.spacing.md, flexWrap: 'wrap' }}>
          <CompactSelect title="Category" options={CATEGORIES} value={cat} onChange={setCat} searchable />
          <CompactSelect title="Method" options={[...METHODS] as unknown as string[]} value={method} onChange={(v)=>setMethod(v as typeof method)} />
          <CompactSelect title="Year" options={YEARS} value={year} onChange={setYear} />
          <CompactSelect title="Condition" options={CONDITIONS} value={condition} onChange={setCondition} />
        </View>

        <View style={{ gap: theme.spacing.sm }}>
          <LabeledInput label="Title" value={title} onChangeText={setTitle} placeholder="e.g., PSA 9 Charizard" />
          <LabeledInput label="Price (€)" value={price} onChangeText={setPrice} keyboardType="numeric" placeholder="e.g., 1200" />
          <LabeledInput label="Notes" value={notes} onChangeText={setNotes} placeholder="Optional notes…" multiline />
        </View>
      </View>

      <View style={{ alignItems: 'flex-start', gap: theme.spacing.sm }}>
        <Pressable onPress={publish} style={{ flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: 8, paddingHorizontal: 16 }}>
          <Icon name="share-outline" />
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Publish (mock)</Text>
        </Pressable>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>
          Guidance: Keep titles short; include grade/edition. Photos upload coming next.
        </Text>
      </View>
    </Card>
  );
}

function LabeledInput(props: { label: string } & React.ComponentProps<typeof TextInput>) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{props.label}</Text>
      <TextInput
        {...props}
        placeholderTextColor={theme.colors.subtext}
        style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
      />
    </View>
  );
}
TSX

echo "→ Done. Rebuild to see changes."
