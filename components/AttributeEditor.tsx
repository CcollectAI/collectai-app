import React, { useMemo, useState } from 'react';
import { View, Text, TextInput, Switch, Button, Alert } from 'react-native';
import { z } from 'zod';
import { AttrSchemas } from '../types/category';
import { supabase } from '../lib/supabase';

export default function AttributeEditor({ itemId, category, initial }: { itemId: string; category: any; initial: Record<string,any> }) {
  const schema = useMemo(()=>AttrSchemas[category], [category]) as any;
  const shape = (schema._def.shape() as Record<string, z.ZodTypeAny>);
  const [attrs, setAttrs] = useState<Record<string,any>>(initial||{});
  const [saving, setSaving] = useState(false);

  function Field({ k, s }: { k: string; s: z.ZodTypeAny }) {
    if (s instanceof z.ZodBoolean) {
      return (
        <View key={k} style={{ paddingVertical: 6 }}>
          <Text>{k}</Text>
          <Switch value={!!attrs[k]} onValueChange={(v)=>setAttrs(a=>({...a,[k]:v}))}/>
        </View>
      );
    }
    return (
      <View key={k} style={{ paddingVertical: 6 }}>
        <Text>{k}</Text>
        <TextInput value={attrs[k] ?? ''} onChangeText={(t)=>setAttrs(a=>({...a,[k]:t}))}
          style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }} placeholder={k} />
      </View>
    );
  }

  async function save() {
    try {
      const parsed = schema.safeParse(attrs);
      if (!parsed.success) { Alert.alert('Invalid', parsed.error.errors.map(e=>e.message).join('\n')); return; }
      setSaving(true);
      const { error } = await supabase.from('items').update({ attributes: parsed.data }).eq('id', itemId);
      if (error) throw error;
      Alert.alert('Saved','Attributes updated.');
    } catch(e:any) { Alert.alert('Error', e.message ?? String(e)); }
    finally { setSaving(false); }
  }

  return (
    <View style={{ marginTop: 12 }}>
      <Text style={{ fontWeight:'700', marginBottom:6 }}>Edit Attributes</Text>
      {Object.keys(shape).map((k)=> <Field key={k} k={k} s={shape[k]} />)}
      <View style={{ marginTop: 10 }}>
        <Button title={saving ? 'Saving…' : 'Save Attributes'} onPress={save} disabled={saving}/>
      </View>
    </View>
  );
}
