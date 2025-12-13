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
