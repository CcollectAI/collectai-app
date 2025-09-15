#!/usr/bin/env bash
set -euo pipefail

echo "→ Update Add screen (AI heading, better alignment, extra collector fields)"
[ -f "app/(tabs)/add.tsx" ] && cp "app/(tabs)/add.tsx" "app/(tabs)/add.tsx.bak"
cat > "app/(tabs)/add.tsx" <<'TSX'
import { useState, useMemo } from 'react';
import { View, Text, ScrollView, Pressable, TextInput, Image, Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import Card from '@/components/Card';
import { theme } from '@/theme';
import { addItem } from '@/store/items';
import { predictFromImage } from '@/lib/predict';
import { router } from 'expo-router';
import CompactSelect from '@/components/CompactSelect';

const CATEGORIES = ['Pokémon', 'Funko', 'LEGO', 'Diecast', 'Sports Cards', 'Comics', 'Other'];
const CONDITIONS = ['New', 'Near Mint', 'Used', 'Damaged'];
const EDITIONS = ['Base', 'First Edition', 'Limited', 'Promo', 'Special'];
const GRADES = ['Raw', 'PSA 10', 'PSA 9', 'BGS 9.5', 'BGS 9', 'SGC 10', 'CGC 9.5'];

export default function Add() {
  const YEARS = useMemo(() => Array.from({ length: 60 }, (_, i) => String(new Date().getFullYear() - i)), []);
  const [photo, setPhoto] = useState<string | null>(null);
  const [predCat, setPredCat] = useState<string | null>(null);
  const [predVal, setPredVal] = useState<number | null>(null);
  const [predicting, setPredicting] = useState(false);

  // Manual fields
  const [category, setCategory] = useState<string>('Pokémon');
  const [title, setTitle] = useState<string>('');
  const [condition, setCondition] = useState<string>('New');
  const [year, setYear] = useState<string>(YEARS[0]);
  const [brand, setBrand] = useState<string>('');
  const [series, setSeries] = useState<string>(''); // Set/Series
  const [edition, setEdition] = useState<string>(EDITIONS[0]);
  const [grade, setGrade] = useState<string>(GRADES[0]);
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

    // Persist minimal item (name/price/%/notes). Extra metadata can be appended into notes.
    const meta = [`Category: ${category}`, year && `Year: ${year}`, brand && `Brand: ${brand}`, series && `Set/Series: ${series}`, edition && `Edition: ${edition}`, grade && `Grade: ${grade}`].filter(Boolean).join(' • ');
    const mergedNotes = [notes.trim(), meta].filter(Boolean).join('\n');

    addItem({
      category,
      name: title.trim(),
      price: isNaN(price) ? 0 : Math.round(price),
      pct: typeof pct === 'number' && isFinite(pct) ? pct : undefined,
      notes: mergedNotes || undefined,
    });

    Alert.alert('Saved', 'Item added to your collection.', [
      { text: 'View Items', onPress: () => router.navigate('/(tabs)/items') },
      { text: 'OK' },
    ]);
  };

  return (
    <ScrollView style={{ flex: 1, backgroundColor: theme.colors.bg }} contentContainerStyle={{ padding: theme.spacing.xl, gap: theme.spacing.xl }}>
      {/* AI photo valuation — headline feature (alignment improved) */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>
          Use AI Prediction & Take a picture
        </Text>

        {/* Capture actions: wrap on small widths, aligned left */}
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.spacing.md }}>
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
              <Pressable onPress={applyPrediction} disabled={!predCat && predVal==null} style={{ borderWidth: 1, borderColor: theme.colors.navy, paddingVertical: theme.spacing.sm, paddingHorizontal: theme.spacing.xl, alignSelf: 'flex-start', opacity: (!predCat && predVal==null) ? 0.5 : 1 }}>
                <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Apply suggestion</Text>
              </Pressable>
            </View>
          </View>
        ) : null}
      </Card>

      {/* Manual entry — compact dropdowns + vertical fields */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '800', fontSize: 16 }}>Manual entry</Text>

        <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Category</Text>
        <CompactSelect title="Select Category" options={CATEGORIES} value={category} onChange={setCategory} searchable />

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Item title</Text>
        <TextInput value={title} onChangeText={setTitle} placeholder="e.g., PSA 9 Charizard" placeholderTextColor={theme.colors.subtext}
          style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />

        {/* Collector details */}
        <View style={{ gap: theme.spacing.md }}>
          <View>
            <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Year</Text>
            <CompactSelect title="Year" options={YEARS} value={year} onChange={setYear} />
          </View>

          <View>
            <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Brand</Text>
            <TextInput value={brand} onChangeText={setBrand} placeholder="e.g., PSA, Topps, LEGO" placeholderTextColor={theme.colors.subtext}
              style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
          </View>

          <View>
            <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Set / Series</Text>
            <TextInput value={series} onChangeText={setSeries} placeholder="e.g., Base Set, UCS" placeholderTextColor={theme.colors.subtext}
              style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: theme.colors.border, padding: theme.spacing.sm }} />
          </View>

          <View>
            <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Edition</Text>
            <CompactSelect title="Edition" options={EDITIONS} value={edition} onChange={setEdition} />
          </View>

          <View>
            <Text style={{ color: theme.colors.subtext, fontSize: 12 }}>Grading</Text>
            <CompactSelect title="Grading" options={GRADES} value={grade} onChange={setGrade} />
          </View>
        </View>

        <Text style={{ color: theme.colors.subtext, fontSize: 12, marginTop: 4 }}>Condition</Text>
        <CompactSelect title="Select Condition" options={CONDITIONS} value={condition} onChange={setCondition} />

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

echo "→ Update Marketplace screen (usernames in chat, vertical search with dropdowns, richer sell form)"
[ -f "app/(tabs)/marketplace.tsx" ] && cp "app/(tabs)/marketplace.tsx" "app/(tabs)/marketplace.tsx.bak"
cat > "app/(tabs)/marketplace.tsx" <<'TSX'
import { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, ScrollView, TextInput, Pressable, KeyboardAvoidingView, Platform } from 'react-native';
import Segmented from '@/components/Segmented';
import Card from '@/components/Card';
import Chip from '@/components/Chip';
import SearchRow from '@/components/SearchRow';
import Skeleton from '@/components/Skeleton';
import CompactSelect from '@/components/CompactSelect';
import EmojiIcon from '@/components/EmojiIcon';
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

  const labelFor = (from: 'me'|'bot') => (from === 'me' ? 'You' : 'MarketBot');

  return (
    <Card style={{ gap: theme.spacing.md }}>
      <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Chat</Text>
      <ScrollView ref={listRef} style={{ maxHeight: 320, borderWidth: 1, borderColor: theme.colors.border }}>
        <View style={{ padding: theme.spacing.md, gap: theme.spacing.sm }}>
          {msgs.map((m) => (
            <View key={m.id} style={{ alignItems: m.from === 'me' ? 'flex-end' : 'flex-start' }}>
              {/* Username above bubble */}
              <Text style={{ color: theme.colors.subtext, fontSize: 10, marginBottom: 2 }}>
                {labelFor(m.from)}
              </Text>
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
      {/* Search Listings (vertical, intuitive layout) */}
      <Card style={{ gap: theme.spacing.md }}>
        <Text style={{ color: theme.colors.navy, fontWeight: '700' }}>Search Listings</Text>

        {/* Query */}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm }}>
          <EmojiIcon name="search" size={18} />
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

        {/* Dropdown filters (vertical-friendly) */}
        <View style={{ gap: theme.spacing.sm }}>
          <View style={{ flexDirection: 'row', gap: theme.spacing.md, flexWrap: 'wrap', alignItems: 'center' }}>
            <CompactSelect title="Category" options={ALL_CATEGORIES as unknown as string[]} value={cat} onChange={(v) => setCat(v as any)} searchable />
            <CompactSelect title="Type" options={TYPES as unknown as string[]} value={type} onChange={(v) => setType(v as any)} />
            <CompactSelect title="Sort" options={SORTS as unknown as string[]} value={sort} onChange={(v) => setSort(v as any)} />
          </View>

          {/* Price range (on its own row) */}
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

      {/* Results (unchanged list, vertically aligned) */}
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

      {/* Vertically aligned form fields */}
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

      {/* Price recommendation stays visible, vertically aligned */}
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

echo "→ Done (Add + Marketplace updated)."
