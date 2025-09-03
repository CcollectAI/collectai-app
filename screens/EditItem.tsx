import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, Alert } from 'react-native';
import { supabase } from '../lib/supabase';

export default function EditItem({ route, navigation }: any) {
  const { id } = route.params as { id: string };
  const [title, setTitle] = useState('');
  const [acq, setAcq] = useState<string>('');

  useEffect(() => {
    (async () => {
      const { data, error } = await supabase.from('items').select('title,acquisition_price').eq('id', id).single();
      if (!error && data) {
        setTitle(data.title ?? '');
        setAcq(data.acquisition_price != null ? String(data.acquisition_price) : '');
      }
    })();
  }, [id]);

  async function save() {
    try {
      const { error } = await supabase.from('items')
        .update({ title, acquisition_price: acq ? Number(acq) : null })
        .eq('id', id);
      if (error) throw error;
      Alert.alert('Saved','Item updated.');
      navigation.goBack();
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
  }

  async function del() {
    try {
      const { error } = await supabase.from('items').delete().eq('id', id);
      if (error) throw error;
      Alert.alert('Deleted','Item removed.');
      navigation.navigate('Items');
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
  }

  return (
    <View style={{ padding:16, gap:12 }}>
      <Text style={{ fontWeight:'700', fontSize:18 }}>Edit Item</Text>
      <Text>Title</Text>
      <TextInput value={title} onChangeText={setTitle} style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }} />
      <Text>Acquisition Price (EUR)</Text>
      <TextInput value={acq} onChangeText={setAcq} keyboardType="decimal-pad" style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }} />
      <Button title="Save" onPress={save} />
      <View style={{ height: 8 }} />
      <Button title="Delete Item" color="#b00020" onPress={del} />
    </View>
  );
}

