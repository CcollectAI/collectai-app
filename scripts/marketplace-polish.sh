#!/usr/bin/env bash
set -euo pipefail

echo "→ ensure folders"
mkdir -p "app/(tabs)" src/components

echo "→ components: Chip (square), Skeleton (pulse), SearchRow (normalized)"
# Chip
cat > "src/components/Chip.tsx" <<'TSX'
import { Pressable, Text } from 'react-native';
import { theme } from '@/theme';

export default function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={{
        borderWidth: 1,
        borderColor: selected ? theme.colors.navy : theme.colors.border,
        backgroundColor: selected ? '#FFFFFF' : theme.colors.card,
        paddingVertical: theme.spacing.xs,
        paddingHorizontal: theme.spacing.md,
      }}
    >
      <Text style={{ color: selected ? theme.colors.navy : theme.colors.subtext, fontWeight: selected ? '700' : '500' }}>
        {label}
      </Text>
    </Pressable>
  );
}
TSX

# Skeleton
cat > "src/components/Skeleton.tsx" <<'TSX'
import { useEffect, useRef } from 'react';
import { Animated, ViewStyle } from 'react-native';
import { theme } from '@/theme';

export default function Skeleton({ style }: { style?: ViewStyle }) {
  const opacity = useRef(new Animated.Value(0.4)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 800, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.4, duration: 800, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);
  return (
    <Animated.View
      style={[
        { backgroundColor: theme.colors.border, opacity },
        style,
      ]}
    />
  );
}
TSX

# SearchRow
cat > "src/components/SearchRow.tsx" <<'TSX'
import { View, Text, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '@/theme';

export default function SearchRow({
  title,
  subtitle,
  price,
  badge,
  thumbUri,
}: {
  title: string;
  subtitle: string;
  price: string;
  badge?: string;
  thumbUri?: string | null;
}) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: theme.spacing.md, borderBottomWidth: 1, borderColor: theme.colors.border }}>
      <View style={{ width: 56, height: 56, borderWidth: 1, borderColor: theme.colors.border, justifyContent: 'center', alignItems: 'center', marginRight: theme.spacing.md }}>
        {thumbUri ? (
          <Image source={{ uri: thumbUri }} style={{ width: 54, height: 54 }} />
        ) : (
          <Ionicons name="image-outline" size={20} color={theme.colors.subtext} />
        )}
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

echo "→ marketplace screen (complex polish)"
[ -f "app/(tabs)/marketplace.tsx" ] && cp "app/(tabs)/marketplace.tsx" "app/(tabs)/marketplace.tsx.bak"
cat > "app/(tabs)/marketplace.tsx" <<'TSX'
import { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, ScrollView, TextInput, Pressable, KeyboardAvoidingView, Platform } from 'react-native';
import Segmented from '@/components/Segmented';
import Card from '@/components/Card';
import Chip from '@/components/Chip';
import SearchRow from '@/components/SearchRow';
import Skeleton from '@/components/Skeleton';
import { theme } from '@/theme';
import { Ionicons } from '@expo/vector-icons';

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

const CATEGORIES = ['All', 'Pokémon', 'Funko', 'LEGO', 'Diecast'];
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

  useEffect(() => {
    listRef.current?.scrollToEnd({ animated: true });
  }, [msgs.length]);

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

  return (
    <Card style={{ gap: theme.spacing.md }}>
      <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Chat</Text>
      <ScrollView ref={listRef} style={{ maxHeight: 280, borderWidth: 1, borderColor: theme.colors.border }}>
        <View style={{ padding: theme.spacing.md, gap: theme.spacing.sm }}>
          {msgs.map((m) => (
            <View key={m.id} style={{ alignItems: m.from === 'me' ? 'flex-end' : 'flex-start' }}>
              <View style={{
                backgroundColor: theme.colors.card,
                borderWidth: 1,
                borderColor: theme.colors.border,
                padding: theme.spacing.sm,
                maxWidth: '85%',
              }}>
                <Text style={{ color: theme.colors.navy }}>{m.text}</Text>
              </View>
              <Text style={{ color: theme.colors.subtext, fontSize: 10, marginTop: 2 }}>
                {new Date(m.ts).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
              </Text>
            </View>
          ))}
          {typing && (
            <View style={{ alignItems: 'flex-start' }}>
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
  const [cat, setCat] = useState('All');
  const [type, setType] = useState<'Listings'|'Auctions'|'Sold'>('Listings');
  const [sort, setSort] = useState<typeof SORTS[number]>('Relevance');
  const [min, setMin] = useState('');
  const [max, setMax] = useState('');
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);

  const results = useMemo<Result[]>(() => {
    // mock normalized hits
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
      .filter(r => (type === 'Sold' ? r.price : true)) // placeholder
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

  const search = () => {
    setLoading(true);
    setTimeout(() => setLoading(false), 450);
  };

  const loadMore = () => setPage((p) => p + 1);

  return (
    <View style={{ gap: theme.spacing.xl }}>
      {/* Query */}
      <Card style={{ gap: theme.spacing.md }}>
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

        {/* Filters */}
        <View style={{ gap: theme.spacing.md }}>
          <View style={{ flexDirection: 'row', gap: theme.spacing.sm, flexWrap: 'wrap' }}>
            {CATEGORIES.map((c) => (
              <Chip key={c} label={c} selected={cat === c} onPress={() => setCat(c)} />
            ))}
          </View>

          <View style={{ flexDirection: 'row', gap: theme.spacing.sm }}>
            {(['Listings','Auctions','Sold'] as const).map(t => (
              <Chip key={t} label={t} selected={type === t} onPress={() => setType(t)} />
            ))}
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
            <Pressable onPress={() => setSort(sort === 'Price ↑' ? 'Price ↓' : 'Price ↑')} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingHorizontal: theme.spacing.md, justifyContent: 'center' }}>
              <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{sort}</Text>
            </Pressable>
          </View>
        </View>
      </Card>

      {/* Results */}
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
            {results.map((r, idx) => (
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

        {/* Load more */}
        {!loading && (
          <View style={{ padding: theme.spacing.md, alignItems: 'center' }}>
            <Pressable onPress={loadMore} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingHorizontal: theme.spacing.xl, paddingVertical: theme.spacing.sm }}>
              <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Load more</Text>
            </Pressable>
          </View>
        )}
      </Card>
    </View>
  );
}

function SellPane() {
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('Pokémon');
  const [condition, setCondition] = useState('Near Mint');
  const [price, setPrice] = useState('');
  const [desc, setDesc] = useState('');

  const recPrice = useMemo(() => {
    // mock heuristic
    const base = category === 'Pokémon' ? 800 : category === 'LEGO' ? 350 : category === 'Diecast' ? 180 : 250;
    return base + (title.length % 7) * 45;
  }, [category, title]);

  return (
    <Card style={{ gap: theme.spacing.md }}>
      <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Create listing</Text>

      <TextInput
        value={title}
        onChangeText={setTitle}
        placeholder="Title"
        placeholderTextColor={theme.colors.subtext}
        style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
      />

      <View style={{ flexDirection: 'row', gap: theme.spacing.sm }}>
        <TextInput
          value={category}
          onChangeText={setCategory}
          placeholder="Category"
          placeholderTextColor={theme.colors.subtext}
          style={{ flex: 1, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
        />
        <TextInput
          value={condition}
          onChangeText={setCondition}
          placeholder="Condition"
          placeholderTextColor={theme.colors.subtext}
          style={{ flex: 1, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
        />
      </View>

      <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm }}>
        <TextInput
          value={price}
          onChangeText={setPrice}
          keyboardType="decimal-pad"
          placeholder="Price (EUR)"
          placeholderTextColor={theme.colors.subtext}
          style={{ flex: 1, borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, backgroundColor: '#fff' }}
        />
        <View style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }}>
          <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Recommended</Text>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>{fmtEUR0(recPrice)}</Text>
        </View>
      </View>

      <TextInput
        value={desc}
        onChangeText={setDesc}
        placeholder="Description"
        placeholderTextColor={theme.colors.subtext}
        multiline
        style={{ borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm, height: 120, textAlignVertical: 'top', backgroundColor: '#fff' }}
      />

      <View style={{ flexDirection: 'row', gap: theme.spacing.sm, flexWrap: 'wrap' }}>
        {['Clear photos', 'Correct category', 'Accurate price', 'Ship tracked'].map((t) => (
          <Chip key={t} label={t} />
        ))}
      </View>

      <View style={{ alignItems: 'center' }}>
        <Pressable style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl }}>
          <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Publish (mock)</Text>
        </Pressable>
      </View>
    </Card>
  );
}
TSX

echo "→ marketplace polish complete"
