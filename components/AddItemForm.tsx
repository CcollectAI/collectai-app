import React, { useMemo, useState } from 'react';
import { View, TextInput, Text, Switch, Button, Alert, ScrollView } from 'react-native';
import { z } from 'zod';
import { supabase } from '../lib/supabase';
import { Category, CategoryList, AttrSchemas, CategoryLabels } from '../types/category';

type Props = { onCreated?: (itemId: string) => void };

export default function AddItemForm({ onCreated }: Props) {
  const [category, setCategory] = useState<Category>('pokemon');
  const [title, setTitle] = useState('');
  const [acqPrice, setAcqPrice] = useState<string>('');
  const [attributes, setAttributes] = useState<Record<string, any>>({});
  const schema = useMemo(() => AttrSchemas[category], [category]);
  const shape = (schema._def.shape() as Record<string, z.ZodTypeAny>);

  function Field({ k, s }: { k: string; s: z.ZodTypeAny }) {
    if (s instanceof z.ZodBoolean) {
      return (
        <View key={k} style={{ paddingVertical: 8 }}>
          <Text>{k}</Text>
          <Switch value={!!attributes[k]} onValueChange={(v)=>setAttributes(a=>({...a,[k]:v}))}/>
        </View>
      );
    }
    return (
      <View key={k} style={{ paddingVertical: 8 }}>
        <Text>{k}</Text>
        <TextInput
          placeholder={k}
          value={attributes[k] ?? ''}
          onChangeText={(t)=>setAttributes(a=>({...a,[k]:t}))}
          style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }}
        />
      </View>
    );
  }

  async function submit() {
    try {
      const u = (await supabase.auth.getUser()).data.user;
      if (!u?.id) { Alert.alert('Auth', 'No user session.'); return; }
      const parsed = schema.safeParse(attributes);
      if (!parsed.success) { Alert.alert('Invalid', parsed.error.errors.map(e=>e.message).join('\n')); return; }
      const { data, error } = await supabase.from('items').insert([{
        owner: u.id,
        category,
        title,
        acquisition_price: acqPrice ? Number(acqPrice) : null,
        attributes: parsed.data,
      }]).select('id').single();
      if (error) throw error;
      onCreated?.(data.id);
      setTitle(''); setAcqPrice(''); setAttributes({});
      Alert.alert('Saved','Item created.');
    } catch (e:any) { Alert.alert('Error', e.message ?? String(e)); }
  }

  return (
    <ScrollView contentContainerStyle={{ gap: 8, padding: 12 }}>
      <Text style={{ fontWeight:'600' }}>Category</Text>
      <TextInput
        value={category}
        onChangeText={(t)=>{ if ((CategoryList as readonly string[]).includes(t)) { setCategory(t as Category); setAttributes({}); } }}
        placeholder={`One of: ${CategoryList.join(', ')}`}
        style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }}
      />
      <Text style={{ color:'#666' }}>{CategoryLabels[category]}</Text>

      <Text style={{ fontWeight:'600' }}>Title</Text>
      <TextInput value={title} onChangeText={setTitle} placeholder="e.g., Bearbrick 400% / Charizard" style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }} />

      <Text style={{ fontWeight:'600' }}>Acquisition Price (EUR)</Text>
      <TextInput keyboardType="decimal-pad" value={acqPrice} onChangeText={setAcqPrice} placeholder="49.99" style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }} />

      <View style={{ marginTop: 8 }}>
        <Text style={{ fontWeight:'700', marginBottom:6 }}>Attributes</Text>
        {Object.keys(shape).map((k)=> <Field key={k} k={k} s={shape[k]} />)}
      </View>

      <View style={{ marginTop: 12 }}>
        <Button title="Add Item" onPress={submit} />
      </View>
    </ScrollView>
  );
}
