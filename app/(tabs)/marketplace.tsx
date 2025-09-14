import React, { useMemo, useRef, useState, useEffect } from 'react';
import { View, Text, ScrollView, Pressable, TextInput, KeyboardAvoidingView, Platform, Alert, FlatList } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import theme from '@/theme';

type TabKey = 'chat' | 'search' | 'sell';

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);

/* ---------- Segmented Control ---------- */
function Segmented({
  value,
  onChange,
  items,
}: {
  value: TabKey;
  onChange: (v: TabKey) => void;
  items: { key: TabKey; label: string }[];
}) {
  return (
    <View style={{
      flexDirection: 'row',
      gap: 8,
      padding: 8,
      borderWidth: 1,
      borderColor: theme.colors.border,
      backgroundColor: theme.colors.card,
    }}>
      {items.map(it => {
        const active = it.key === value;
        return (
          <Pressable
            key={it.key}
            onPress={() => onChange(it.key)}
            style={{
              flex: 1,
              paddingVertical: 10,
              alignItems: 'center',
              borderWidth: 1,
              borderColor: theme.colors.border,
              backgroundColor: active ? '#F1FAFB' : theme.colors.card,
            }}
          >
            <Text style={{ fontWeight: '700', color: active ? theme.colors.text : theme.colors.subtext }}>
              {it.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/* ---------- CHAT (mock, realtime-ready shell) ---------- */
type ChatMsg = { id: string; who: 'me' | 'them'; text: string; at: number };

function ChatPane() {
  const [msgs, setMsgs] = useState<ChatMsg[]>([
    { id: 'm1', who: 'them', text: 'Welcome to Marketplace chat!', at: Date.now() - 60_000 },
    { id: 'm2', who: 'me', text: 'Hi! Looking for PSA 10 Pikachu.', at: Date.now() - 30_000 },
  ]);
  const [draft, setDraft] = useState('');
  const listRef = useRef<FlatList<ChatMsg>>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      setMsgs(cur => [...cur, { id: String(Math.random()), who: 'them', text: 'We’ll add rooms & DMs later 🔧', at: Date.now() }]);
    }, 1500);
    return () => clearTimeout(t);
  }, []);

  const send = () => {
    const text = draft.trim();
    if (!text) return;
    setMsgs(cur => [...cur, { id: String(Math.random()), who: 'me', text, at: Date.now() }]);
    setDraft('');
    requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
  };

  const renderItem = ({ item }: { item: ChatMsg }) => {
    const mine = item.who === 'me';
    return (
      <View style={{ paddingHorizontal: 16, paddingVertical: 6 }}>
        <View style={{
          alignSelf: mine ? 'flex-end' : 'flex-start',
          maxWidth: '82%',
          backgroundColor: theme.colors.card,
          borderColor: theme.colors.border,
          borderWidth: 1,
          paddingHorizontal: 12,
          paddingVertical: 8,
        }}>
          <Text style={{ color: theme.colors.text }}>{item.text}</Text>
        </View>
      </View>
    );
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
      <FlatList
        ref={listRef}
        data={msgs}
        keyExtractor={(m) => m.id}
        renderItem={renderItem}
        contentContainerStyle={{ paddingVertical: 8 }}
        style={{ flex: 1 }}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
      />
      <View style={{
        flexDirection: 'row',
        gap: 8,
        padding: 8,
        borderTopWidth: 1,
        borderTopColor: theme.colors.border,
        backgroundColor: theme.colors.card,
      }}>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          placeholder="Message marketplace…"
          placeholderTextColor={theme.colors.subtext}
          style={{
            flex: 1,
            paddingHorizontal: 12,
            paddingVertical: 10,
            borderWidth: 1,
            borderColor: theme.colors.border,
            backgroundColor: '#FFFFFF',
          }}
        />
        <Pressable onPress={send} style={{ paddingHorizontal: 12, justifyContent: 'center' }}>
          <Ionicons name="send" size={22} color={theme.colors.text} />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

/* ---------- SEARCH (mock aggregate adapter) ---------- */
type Hit = { id: string; title: string; marketplace: string; price: number; changePct?: number };

function mockSearch(q: string): Promise<Hit[]> {
  const base: Hit[] = [
    { id: 'sx-1', title: 'Nike Dunk Low Panda (2023)', marketplace: 'StockX', price: 145, changePct: -1.1 },
    { id: 'eb-1', title: 'Charizard Holo 1999',        marketplace: 'eBay',   price: 120, changePct: +2.0 },
    { id: 'mc-1', title: 'Funko Pop Pikachu',          marketplace: 'Mercari',price: 24,  changePct:  0.0 },
    { id: 'wn-1', title: 'Retro Game Boy Color',       marketplace: 'Whatnot',price: 95,  changePct: +0.5 },
  ];
  const s = q.trim().toLowerCase();
  const out = s ? base.filter(h => h.title.toLowerCase().includes(s)) : base;
  return new Promise(res => setTimeout(() => res(out), 400));
}

function Row({ hit }: { hit: Hit }) {
  const pct = hit.changePct ?? 0;
  return (
    <View style={{
      paddingHorizontal: 12,
      paddingVertical: 12,
      borderBottomWidth: 1,
      borderBottomColor: theme.colors.border,
    }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <View>
          <Text style={{ fontWeight: '700', color: theme.colors.text }}>{hit.title}</Text>
          <Text style={{ marginTop: 4, color: pct >= 0 ? theme.colors.success : theme.colors.danger, fontSize: 12 }}>
            {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
          </Text>
        </View>
        <Text style={{ color: theme.colors.text, fontWeight: '800' }}>€{money(hit.price)}</Text>
      </View>
      <Text style={{ marginTop: 4, color: theme.colors.subtext, fontSize: 12 }}>{hit.marketplace}</Text>
    </View>
  );
}

function SearchPane() {
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(false);
  const [hits, setHits] = useState<Hit[]>([]);

  const run = async () => {
    setLoading(true);
    try {
      const r = await mockSearch(q);
      setHits(r);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <View style={{ flex: 1 }}>
      {/* search bar */}
      <View style={{ padding: 8, gap: 8, backgroundColor: theme.colors.card, borderBottomWidth: 1, borderBottomColor: theme.colors.border }}>
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder="Search across marketplaces…"
          placeholderTextColor={theme.colors.subtext}
          onSubmitEditing={run}
          returnKeyType="search"
          style={{
            paddingHorizontal: 12, paddingVertical: 10,
            borderWidth: 1, borderColor: theme.colors.border, backgroundColor: '#FFFFFF',
          }}
        />
        <Pressable onPress={run} style={{ alignSelf: 'flex-end', paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: theme.colors.border }}>
          <Text style={{ fontWeight: '700', color: theme.colors.text }}>{loading ? 'Searching…' : 'Search'}</Text>
        </Pressable>
      </View>

      {/* results list */}
      <ScrollView contentContainerStyle={{}}>
        <View style={{ margin: 16, backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border }}>
          {hits.map((h, i) => (
            <Row key={h.id} hit={h} />
          ))}
          {hits.length === 0 && !loading && (
            <View style={{ padding: 16 }}>
              <Text style={{ color: theme.colors.subtext }}>No results.</Text>
            </View>
          )}
        </View>
      </ScrollView>
    </View>
  );
}

/* ---------- SELL (simple white form + guidance) ---------- */
function SellPane() {
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('');
  const [price, setPrice] = useState('');

  const publish = () => {
    const p = Number(price);
    if (!title.trim()) return Alert.alert('Missing', 'Please enter a title.');
    if (!category.trim()) return Alert.alert('Missing', 'Please enter a category.');
    if (!Number.isFinite(p) || p <= 0) return Alert.alert('Invalid', 'Please enter a valid price.');
    Alert.alert('Published (mock)', `Title: ${title}\nCategory: ${category}\nPrice: €${money(p)}`);
  };

  const Field = ({ label, value, onChangeText, keyboardType='default' as const }:{
    label: string; value: string; onChangeText: (s:string)=>void; keyboardType?: 'default'|'numeric';
  }) => (
    <View style={{ gap: 6 }}>
      <Text style={{ color: theme.colors.text, fontWeight: '700' }}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        keyboardType={keyboardType}
        placeholderTextColor={theme.colors.subtext}
        style={{ paddingHorizontal: 12, paddingVertical: 10, borderWidth: 1, borderColor: theme.colors.border, backgroundColor: '#FFFFFF' }}
      />
    </View>
  );

  return (
    <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }}>
      <View style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border, padding: 16, gap: 12 }}>
        <Field label="Title" value={title} onChangeText={setTitle} />
        <Field label="Category" value={category} onChangeText={setCategory} />
        <Field label="Price (€)" value={price} onChangeText={setPrice} keyboardType="numeric" />

        <Pressable onPress={publish} style={{ alignSelf:'flex-start', paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: theme.colors.border }}>
          <Text style={{ fontWeight: '800', color: theme.colors.text }}>Publish (mock)</Text>
        </Pressable>
      </View>

      <View style={{ backgroundColor: theme.colors.card, borderWidth: 1, borderColor: theme.colors.border, padding: 16, gap: 8 }}>
        <Text style={{ fontWeight: '800', color: theme.colors.text }}>Tips</Text>
        <Text style={{ color: theme.colors.subtext }}>
          • Clear photos and accurate categories help your item get discovered.
        </Text>
        <Text style={{ color: theme.colors.subtext }}>
          • Pricing guidance and multi-market posting coming next.
        </Text>
      </View>
    </ScrollView>
  );
}

/* ---------- Screen wrapper ---------- */
export default function MarketplaceScreen() {
  const [tab, setTab] = useState<TabKey>('chat');

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg }}>
      {/* Header */}
      <View style={{ paddingHorizontal: 16, paddingTop: 16, paddingBottom: 8 }}>
        <Text style={{ fontSize: 24, fontWeight: '800', color: theme.colors.text }}>Marketplace</Text>
      </View>

      {/* Segments */}
      <View style={{ marginHorizontal: 16, marginBottom: 12 }}>
        <Segmented
          value={tab}
          onChange={setTab}
          items={[
            { key: 'chat',   label: 'Chat'   },
            { key: 'search', label: 'Search' },
            { key: 'sell',   label: 'Sell'   },
          ]}
        />
      </View>

      {/* Body */}
      <View style={{ flex: 1 }}>
        {tab === 'chat'   && <ChatPane />}
        {tab === 'search' && <SearchPane />}
        {tab === 'sell'   && <SellPane />}
      </View>
    </View>
  );
}
