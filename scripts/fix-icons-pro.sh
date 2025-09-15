#!/usr/bin/env bash
set -euo pipefail

echo "→ Ensure vector icon deps"
npx expo install @expo/vector-icons expo-font >/dev/null

echo "→ Root layout: load Ionicons font before rendering"
[ -f "app/_layout.tsx" ] && cp "app/_layout.tsx" "app/_layout.tsx.bak"
cat > "app/_layout.tsx" <<'TSX'
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';
import { useFonts } from 'expo-font';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

SplashScreen.preventAutoHideAsync().catch(()=>{});

export default function RootLayout() {
  const [fontsLoaded] = useFonts(Ionicons.font);
  useEffect(() => { if (fontsLoaded) SplashScreen.hideAsync().catch(()=>{}); }, [fontsLoaded]);
  if (!fontsLoaded) return null;

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: theme.colors.card }, // white header line
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

echo "→ Tabs layout: use Ionicons (no emojis), quote path safely"
[ -f "app/(tabs)/_layout.tsx" ] && cp "app/(tabs)/_layout.tsx" "app/(tabs)/_layout.tsx.bak"
cat > "app/(tabs)/_layout.tsx" <<'TSX'
import { Tabs, Link } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Pressable, Share } from 'react-native';
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
        headerStyle: { backgroundColor: theme.colors.card },
        headerTitleStyle: { color: theme.colors.navy, fontWeight: '800' },
        headerTintColor: theme.colors.navy,
        sceneStyle: { backgroundColor: theme.colors.bg },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Portfolio',
          tabBarLabel: 'Portfolio',
          tabBarIcon: ({ color, size }) => <Ionicons name="bar-chart-outline" size={size} color={color} />,
          headerRight: () => <SettingsButton />,
        }}
      />
      <Tabs.Screen
        name="items"
        options={{
          title: 'Items',
          tabBarLabel: 'Items',
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

echo "→ CompactSelect: switch to Ionicons (chevron/close/check)"
[ -f "src/components/CompactSelect.tsx" ] && cp "src/components/CompactSelect.tsx" "src/components/CompactSelect.tsx.bak"
cat > "src/components/CompactSelect.tsx" <<'TSX'
import { useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, Text, TextInput, View, Dimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

type Props = {
  title?: string;
  value?: string | null;
  options: string[];
  placeholder?: string;
  onChange: (v: string) => void;
  searchable?: boolean;
};

export default function CompactSelect({ title, value, options, placeholder = 'Select…', onChange, searchable = false }: Props) {
  const triggerRef = useRef<View>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [anch, setAnch] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  const show = () => {
    try {
      // @ts-ignore – RN runtime
      triggerRef.current?.measureInWindow?.((x: number, y: number, w: number, h: number) => {
        setAnch({ x, y, w, h });
        setOpen(true);
      });
    } catch {
      setAnch(null);
      setOpen(true);
    }
  };
  const hide = () => setOpen(false);

  const filtered = query ? options.filter((o) => o.toLowerCase().includes(query.toLowerCase())) : options;

  const { width: SW, height: SH } = Dimensions.get('window');
  const POPOVER_W = 260;
  const left = Math.max(8, Math.min((anch?.x ?? 16), SW - POPOVER_W - 8));
  const topBase = (anch ? anch.y + anch.h + 6 : 120);
  const maxH = Math.max(160, Math.min(320, SH - topBase - 16));
  const top = Math.min(topBase, SH - maxH - 8);

  return (
    <>
      <Pressable ref={triggerRef} onPress={show} style={{ alignSelf: 'flex-start' }}>
        <View style={{
          backgroundColor: theme.colors.card,
          borderWidth: 1,
          borderColor: theme.colors.border,
          paddingVertical: theme.spacing.xs,
          paddingHorizontal: theme.spacing.sm,
          flexDirection: 'row',
          alignItems: 'center',
          gap: theme.spacing.xs,
        }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{value || placeholder}</Text>
          <Ionicons name="chevron-down" size={14} color={theme.colors.subtext} />
        </View>
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={hide}>
        <Pressable onPress={hide} style={{ flex: 1, backgroundColor: 'rgba(11,61,145,0.05)' }}>
          <Pressable
            onPress={() => {}}
            style={{
              position: 'absolute',
              top,
              left,
              width: POPOVER_W,
              backgroundColor: theme.colors.card,
              borderWidth: 1,
              borderColor: theme.colors.border,
              padding: theme.spacing.md,
              maxHeight: maxH,
            }}
          >
            {title ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: theme.spacing.sm }}>
                <Text style={{ color: theme.colors.navy, fontWeight: '800' }}>{title}</Text>
                <Ionicons name="close" size={16} color={theme.colors.subtext} />
              </View>
            ) : null}

            {searchable ? (
              <TextInput
                value={query}
                onChangeText={setQuery}
                placeholder="Search…"
                placeholderTextColor={theme.colors.subtext}
                style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff', marginBottom: theme.spacing.sm }}
              />
            ) : null}

            <ScrollView keyboardShouldPersistTaps="handled">
              {filtered.map((opt, idx) => {
                const selected = value === opt;
                return (
                  <Pressable key={opt} onPress={() => { onChange(opt); hide(); }}>
                    <View style={{
                      paddingVertical: theme.spacing.md,
                      flexDirection: 'row',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      borderTopWidth: idx === 0 ? 0 : 1,
                      borderColor: theme.colors.border,
                    }}>
                      <Text style={{ color: theme.colors.navy, fontWeight: selected ? '800' : '600' }}>{opt}</Text>
                      {selected ? <Ionicons name="checkmark" size={16} color={theme.colors.navy} /> : null}
                    </View>
                  </Pressable>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}
TSX

echo "→ SearchRow: use Ionicons for image placeholder"
[ -f "src/components/SearchRow.tsx" ] && cp "src/components/SearchRow.tsx" "src/components/SearchRow.tsx.bak"
cat > "src/components/SearchRow.tsx" <<'TSX'
import { View, Text, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

export default function SearchRow({ title, subtitle, price, badge, thumbUri }: {
  title: string; subtitle: string; price: string; badge?: string; thumbUri?: string | null;
}) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.md, borderBottomWidth: 1, borderColor: theme.colors.border }}>
      <View style={{ width: 56, height: 56, borderWidth: 1, borderColor: theme.colors.border, justifyContent: 'center', alignItems: 'center', marginRight: theme.spacing.md }}>
        {thumbUri ? <Image source={{ uri: thumbUri }} style={{ width: 54, height: 54 }} /> : <Ionicons name="image-outline" size={18} color={theme.colors.subtext} />}
      </View>
      <View style={{ flex: 1, paddingRight: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '600' }} numberOfLines={1}>{title}</Text>
        <Text style={{ color: theme.colors.subtext, fontSize: 12 }} numberOfLines={1}>{subtitle}</Text>
        {badge ? <Text style={{ color: theme.colors.subtext, fontSize: 10, marginTop: 2 }}>{badge}</Text> : null}
      </View>
      <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{price}</Text>
    </View>
  );
}
TSX

echo "→ ShieldBadge: clean Ionicons shield + tier label"
[ -f "src/components/ShieldBadge.tsx" ] && cp "src/components/ShieldBadge.tsx" "src/components/ShieldBadge.tsx.bak"
cat > "src/components/ShieldBadge.tsx" <<'TSX'
import { View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

export type Tier = 'silver' | 'gold' | 'platinum';

const COLORS: Record<Tier, string> = {
  silver: '#C0C0C0',
  gold: '#D4AF37',
  platinum: '#B0BEC5',
};

export default function ShieldBadge({ tier }: { tier: Tier }) {
  return (
    <View style={{
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: '#fff',
      borderWidth: 1,
      borderColor: COLORS[tier],
      paddingVertical: 2,
      paddingHorizontal: 6,
    }}>
      <Ionicons name="shield-outline" size={14} color={theme.colors.navy} />
      <Text style={{ color: theme.colors.navy, fontWeight: '700', fontSize: 12, marginLeft: 4 }}>
        {tier[0].toUpperCase() + tier.slice(1)}
      </Text>
    </View>
  );
}
TSX

echo "→ Items screen: replace any emoji share with Ionicons"
[ -f "app/(tabs)/items.tsx" ] && cp "app/(tabs)/items.tsx" "app/(tabs)/items.tsx.bak"
cat > "app/(tabs)/items.tsx" <<'TSX'
import { View, Text, ScrollView, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Card from '@/components/Card';
import ShieldBadge, { Tier } from '@/components/ShieldBadge';
import { theme } from '@/theme';
import { useItems, groupByCategory } from '@/store/items';

type Item = { name: string; pct?: number; price: number };
type Group = { category: string; tier: Tier; items: Item[] };

const fmtEUR0_US = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

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

  const onDownload = () => {};

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.lg, gap: theme.spacing.lg }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16, backgroundColor: theme.colors.card, paddingHorizontal: 8, paddingVertical: 4 }}>
          Items
        </Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing.xs }}>
          <Ionicons name="share-outline" size={18} color={theme.colors.navy} />
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Share</Text>
        </View>
      </View>

      {merged.map((g) => {
        const total = g.items.reduce((s, it) => s + it.price, 0);
        return (
          <View key={g.category} style={{ gap: theme.spacing.xs }}>
            <Card style={{ gap: theme.spacing.sm, padding: theme.spacing.md }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingBottom: theme.spacing.xs, borderBottomWidth: 1, borderColor: theme.colors.border }}>
                <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>{g.category}</Text>
                <ShieldBadge tier={g.tier} />
              </View>

              <View style={{ flexDirection: 'row', paddingVertical: theme.spacing.xs, borderBottomWidth: 1, borderColor: theme.colors.border, alignItems: 'center' }}>
                <Text style={{ flex: 1, color: theme.colors.subtext, fontWeight: '700' }}>Name</Text>
                <Text style={{ width: 100, textAlign: 'right', color: theme.colors.subtext, fontWeight: '700' }}>Price</Text>
              </View>

              {g.items.map((it, idx) => (
                <View key={idx} style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.sm, borderBottomWidth: idx < g.items.length - 1 ? 1 : 0, borderColor: theme.colors.border }}>
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

            <View style={{ alignItems: 'flex-end' }}>
              <Text style={{ color: theme.colors.subtext, fontWeight: '700' }}>
                Total {fmtEUR0_US(total)}
              </Text>
            </View>
          </View>
        );
      })}

      <View style={{ alignItems: 'center', marginTop: theme.spacing.sm, marginBottom: theme.spacing.xl }}>
        <Pressable onPress={onDownload} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Download overview</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
TSX

echo "→ Marketplace screen: remove EmojiIcon, use Ionicons (search icon only)"
[ -f "app/(tabs)/marketplace.tsx" ] && cp "app/(tabs)/marketplace.tsx" "app/(tabs)/marketplace.tsx.bak"
# Recreate marketplace.tsx from last good version with Ionicons
cat > "app/(tabs)/marketplace.tsx" <<'TSX'
import { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, ScrollView, TextInput, Pressable, KeyboardAvoidingView, Platform } from 'react-native';
import Segmented from '@/components/Segmented';
import Card from '@/components/Card';
import Chip from '@/components/Chip';
import SearchRow from '@/components/SearchRow';
import Skeleton from '@/components/Skeleton';
import CompactSelect from '@/components/CompactSelect';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

type Result = {
  id: string;
  title: string;
  source: string;
  category: string;
  condition: string;
  price: number;
  thumb?: string | null;
  verified?: boolean;
};

const CATEGORIES = ['Pokémon', 'Funko', 'LEGO', 'Diecast', 'Sports Cards', 'Comics', 'Other'];
const ALL_CATEGORIES = ['All', ...CATEGORIES] as const;
const TYPES = ['Listings', 'Auctions', 'Sold'] as const;
const SORTS = ['Relevance', 'Price ↑', 'Price ↓', 'Recent'] as const;

const fmtEUR0 = (n: number) =>
  new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(n);

export default function Marketplace() {
  const [seg, setSeg] = useState<'Chat'|'Search'|'Sell'>('Search');

  return (
    <KeyboardAvoidingView behavior={Platform.select({ ios: 'padding', android: undefined })} style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
        <Segmented segments={['Chat','Search','Sell']} value={seg} onChange={(v) => setSeg(v as any)} />
        {seg === 'Chat' && <ChatPane />}
        {seg === 'Search' && <SearchPane />}
        {seg === 'Sell' && <SellPane />}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function ChatPane() {
  type Msg = { id: string; from: 'me'|'bot'; text: string; ts: number };
  const [msgs, setMsgs] = useState<Msg[]>([
    { id: '1', from: 'bot', text: 'Hi! Looking for Charizard or LEGO today?', ts: Date.now() - 60_000 },
    { id: '2', from: 'me', text: 'Show me Charizard under €2k', ts: Date.now() - 40_000 },
  ]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const listRef = useRef<ScrollView>(null);

  useEffect(() => { listRef.current?.scrollToEnd({ animated: true }); }, [msgs.length]);

  const send = () => {
    if (!input.trim()) return;
    const now = Date.now();
    setMsgs((m) => [...m, { id: String(now), from: 'me', text: input.trim(), ts: now }]);
    setInput('');
    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      const reply = 'Here are a few picks from verified sellers.';
      setMsgs((m) => [...m, { id: String(Date.now()), from: 'bot', text: reply, ts: Date.now() }]);
    }, 700);
  };

  const labelFor = (from: 'me'|'bot') => (from === 'me' ? 'You' : 'MarketBot');

  return (
    <Card style={{ gap: theme.spacing.md }}>
      <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Chat</Text>
      <ScrollView ref={listRef} style={{ maxHeight: 320, borderWidth: 1, borderColor: theme.colors.border }}>
        <View style={{ padding: theme.spacing.md, gap: theme.spacing.sm }}>
          {msgs.map((m) => (
            <View key={m.id} style={{ alignItems: m.from === 'me' ? 'flex-end' : 'flex-start' }}>
              <Text style={{ color: theme.colors.subtext, fontSize: 10, marginBottom: 2 }}>
                {labelFor(m.from)}
              </Text>
              <View style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, maxWidth: '85%' }}>
                <Text style={{ color: theme.colors.navy }}>{m.text}</Text>
              </View>
              <Text style={{ color: theme.colors.subtext, fontSize: 10, marginTop: 2 }}>
                {new Date(m.ts).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
              </Text>
            </View>
          ))}
          {typing && (
            <View style={{ alignItems: 'flex-start' }}>
              <Text style={{ color: theme.colors.subtext, fontSize: 10, marginBottom: 2 }}>MarketBot</Text>
              <View style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, maxWidth: '70%' }}>
                <Text style={{ color: theme.colors.subtext }}>Assistant is typing…</Text>
              </View>
            </View>
          )}
        </View>
      </ScrollView>

      <View style={{ flexDirection: 'row', gap: theme.spacing.sm }}>
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Message…"
          placeholderTextColor={theme.colors.subtext}
          style={{ flex: 1, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
        />
        <Pressable onPress={send} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingHorizontal: theme.spacing.lg, justifyContent: 'center' }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Send</Text>
        </Pressable>
      </View>
    </Card>
  );
}

function SearchPane() {
  const [q, setQ] = useState('');
  const [cat, setCat] = useState<(typeof ALL_CATEGORIES)[number]>('All');
  const [type, setType] = useState<(typeof TYPES)[number]>('Listings');
  const [sort, setSort] = useState<(typeof SORTS)[number]>('Relevance');
  const [min, setMin] = useState('');
  const [max, setMax] = useState('');
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);

  const results = useMemo<Result[]>(() => {
    const base: Result[] = Array.from({ length: 8 }, (_, i) => ({
      id: `r${page}-${i}`,
      title: `Charizard PSA 9 #${i + 1}`,
      source: i % 2 ? 'eBay' : 'TCGplayer',
      category: 'Pokémon',
      condition: i % 3 ? 'Near Mint' : 'Used',
      price: 800 + i * 75,
      verified: i % 3 === 0,
      thumb: null,
    }));
    return base
      .filter(r => (cat === 'All' || r.category === cat))
      .filter(r => (type === 'Sold' ? r.price : true))
      .filter(r => (q ? r.title.toLowerCase().includes(q.toLowerCase()) : true))
      .filter(r => (min ? r.price >= Number(min) : true))
      .filter(r => (max ? r.price <= Number(max) : true))
      .sort((a, b) => {
        if (sort === 'Price ↑') return a.price - b.price;
        if (sort === 'Price ↓') return b.price - a.price;
        if (sort === 'Recent') return b.id.localeCompare(a.id);
        return 0;
      });
  }, [q, cat, type, sort, min, max, page]);

  const search = () => { setLoading(true); setTimeout(() => setLoading(false), 450); };
  const loadMore = () => setPage((p) => p + 1);

  return (
    <View style={{ gap: theme.spacing.xl }}>
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Search Listings</Text>

        <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm }}>
          <Ionicons name="search-outline" size={18} color={theme.colors.subtext} />
          <TextInput
            value={q}
            onChangeText={setQ}
            placeholder="Search listings…"
            placeholderTextColor={theme.colors.subtext}
            style={{ flex: 1, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
          />
          <Pressable onPress={search} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingHorizontal: theme.spacing.lg, paddingVertical: theme.spacing.xs }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Go</Text>
          </Pressable>
        </View>

        <View style={{ gap: theme.spacing.sm }}>
          <View style={{ flexDirection: 'row', gap: theme.spacing.md, flexWrap: 'wrap', alignItems: 'center' }}>
            <CompactSelect title="Category" options={ALL_CATEGORIES as unknown as string[]} value={cat} onChange={(v) => setCat(v as any)} searchable />
            <CompactSelect title="Type" options={TYPES as unknown as string[]} value={type} onChange={(v) => setType(v as any)} />
            <CompactSelect title="Sort" options={SORTS as unknown as string[]} value={sort} onChange={(v) => setSort(v as any)} />
          </View>

          <View style={{ flexDirection: 'row', gap: theme.spacing.sm }}>
            <TextInput
              value={min}
              onChangeText={setMin}
              keyboardType="numeric"
              placeholder="Min €"
              placeholderTextColor={theme.colors.subtext}
              style={{ flex: 1, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
            />
            <TextInput
              value={max}
              onChangeText={setMax}
              keyboardType="numeric"
              placeholder="Max €"
              placeholderTextColor={theme.colors.subtext}
              style={{ flex: 1, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
            />
          </View>
        </View>
      </Card>

      <ResultsCard loading={loading} results={results} onLoadMore={loadMore} />
    </View>
  );
}

function ResultsCard({ loading, results, onLoadMore }: { loading: boolean; results: Result[]; onLoadMore: () => void }) {
  return (
    <Card style={{ padding: 0 }}>
      <View style={{ padding: theme.spacing.md, paddingBottom: theme.spacing.sm, borderBottomWidth: 1, borderColor: theme.colors.border }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Results</Text>
      </View>

      {loading ? (
        <View style={{ padding: theme.spacing.md, gap: theme.spacing.md }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing.md }}>
              <Skeleton style={{ width: 56, height: 56 }} />
              <View style={{ flex: 1, gap: theme.spacing.xs }}>
                <Skeleton style={{ height: 12 }} />
                <Skeleton style={{ height: 10, width: '60%' }} />
              </View>
              <Skeleton style={{ width: 60, height: 14 }} />
            </View>
          ))}
        </View>
      ) : (
        <View style={{ paddingHorizontal: theme.spacing.md }}>
          {results.map((r) => (
            <SearchRow
              key={r.id}
              title={r.title}
              subtitle={`${r.source} • ${r.category} • ${r.condition}`}
              price={fmtEUR0(r.price)}
              badge={r.verified ? 'Verified seller' : undefined}
              thumbUri={r.thumb ?? null}
            />
          ))}
        </View>
      )}

      {!loading && (
        <View style={{ padding: theme.spacing.md, alignItems: 'center' }}>
          <Pressable onPress={onLoadMore} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingHorizontal: theme.spacing.xl, paddingVertical: theme.spacing.sm }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Load more</Text>
          </Pressable>
        </View>
      )}
    </Card>
  );
}

function SellPane() {
  const YEARS = useMemo(() => Array.from({ length: 60 }, (_, i) => String(new Date().getFullYear() - i)), []);
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [condition, setCondition] = useState('Near Mint');
  const [year, setYear] = useState(YEARS[0]);
  const [brand, setBrand] = useState('');
  const [series, setSeries] = useState('');
  const [edition, setEdition] = useState('Base');
  const [quantity, setQuantity] = useState('1');
  const [shipping, setShipping] = useState('Tracked');
  const [location, setLocation] = useState('');
  const [acceptOffers, setAcceptOffers] = useState('Yes');
  const [price, setPrice] = useState('');
  const [desc, setDesc] = useState('');

  const recPrice = useMemo(() => {
    const base = category === 'Pokémon' ? 800 : category === 'LEGO' ? 350 : category === 'Diecast' ? 180 : 250;
    return base + (title.length % 7) * 45;
  }, [category, title]);

  return (
    <Card style={{ gap: theme.spacing.md }}>
      <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Create listing</Text>

      <View style={{ gap: theme.spacing.md }}>
        <TextInput
          value={title}
          onChangeText={setTitle}
          placeholder="Title"
          placeholderTextColor={theme.colors.subtext}
          style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
        />

        <View style={{ flexDirection: 'row', gap: theme.spacing.sm, flexWrap: 'wrap', alignItems: 'center' }}>
          <CompactSelect title="Category" options={CATEGORIES} value={category} onChange={setCategory} searchable />
          <CompactSelect title="Condition" options={['New','Near Mint','Used','Damaged']} value={condition} onChange={setCondition} />
        </View>

        <View style={{ flexDirection: 'row', gap: theme.spacing.sm, flexWrap: 'wrap', alignItems: 'center' }}>
          <CompactSelect title="Year" options={YEARS} value={year} onChange={setYear} />
          <CompactSelect title="Edition" options={['Base','First Edition','Limited','Promo','Special']} value={edition} onChange={setEdition} />
        </View>

        <TextInput
          value={brand}
          onChangeText={setBrand}
          placeholder="Brand (e.g., PSA, Topps, LEGO)"
          placeholderTextColor={theme.colors.subtext}
          style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
        />

        <TextInput
          value={series}
          onChangeText={setSeries}
          placeholder="Set / Series (e.g., Base Set, UCS)"
          placeholderTextColor={theme.colors.subtext}
          style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
        />

        <View style={{ flexDirection: 'row', gap: theme.spacing.sm }}>
          <TextInput
            value={quantity}
            onChangeText={setQuantity}
            keyboardType="numeric"
            placeholder="Quantity"
            placeholderTextColor={theme.colors.subtext}
            style={{ flex: 1, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
          />
          <TextInput
            value={price}
            onChangeText={setPrice}
            keyboardType="decimal-pad"
            placeholder="Price (EUR)"
            placeholderTextColor={theme.colors.subtext}
            style={{ flex: 1, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
          />
        </View>

        <View style={{ flexDirection: 'row', gap: theme.spacing.sm, flexWrap: 'wrap', alignItems: 'center' }}>
          <CompactSelect title="Shipping" options={['Local Pickup','Tracked','Untracked']} value={shipping} onChange={setShipping} />
          <CompactSelect title="Accept offers" options={['Yes','No']} value={acceptOffers} onChange={setAcceptOffers} />
        </View>

        <TextInput
          value={location}
          onChangeText={setLocation}
          placeholder="Location"
          placeholderTextColor={theme.colors.subtext}
          style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
        />

        <TextInput
          value={desc}
          onChangeText={setDesc}
          placeholder="Description"
          placeholderTextColor={theme.colors.subtext}
          multiline
          style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, height: 120, textAlignVertical: 'top', backgroundColor: '#fff' }}
        />
      </View>

      <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm }}>
        <View style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }}>
          <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Recommended</Text>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{fmtEUR0(recPrice)}</Text>
        </View>

        <View style={{ flex: 1, alignItems: 'flex-end' }}>
          <Pressable style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
            <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Publish (mock)</Text>
          </Pressable>
        </View>
      </View>
    </Card>
  );
}
TSX

echo "→ Optional: keep (unused) EmojiIcon file to avoid import errors in stray files"
# If a stray file still imports EmojiIcon, create a minimal no-op fallback so the build won't fail.
mkdir -p "src/components"
cat > "src/components/EmojiIcon.tsx" <<'TSX'
import { Text } from 'react-native';
export default function EmojiIcon({ size = 16 }: { size?: number }) { return <Text style={{ fontSize: size }} />; }
TSX

echo "→ Done. Icons unified to Ionicons, imports fixed, shell-safe paths."
