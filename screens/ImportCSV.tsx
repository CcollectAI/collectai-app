import React, { useState } from 'react';
import { View, Text, Button, Alert } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import Papa from 'papaparse';
import { supabase } from '../lib/supabase';

export default function ImportCSV() {
  const [count, setCount] = useState(0);

  async function pick() {
    const res = await DocumentPicker.getDocumentAsync({ type: 'text/csv' });
    if (res.canceled || !res.assets?.length) return;
    const asset = res.assets[0];
    const file = await fetch(asset.uri).then(r=>r.text());
    const parsed = Papa.parse(file, { header: true });
    const rows = parsed.data as any[];
    let ok = 0;
    for (const r of rows) {
      if (!r.title || !r.category) continue;
      const { error } = await supabase.from('items').insert([{
        title: r.title,
        category: r.category,
        acquisition_price: r.acquisition_price ? Number(r.acquisition_price) : null,
        attributes: r.attributes ? JSON.parse(r.attributes) : {}
      }]);
      if (!error) ok++;
    }
    setCount(ok);
    Alert.alert('Import', `Imported ${ok} items`);
  }

  return (
    <View style={{ padding:16, gap:12 }}>
      <Text style={{ fontWeight:'700', fontSize:18 }}>Import CSV</Text>
      <Text>CSV columns: title, category, acquisition_price, attributes (JSON)</Text>
      <Button title="Pick CSV" onPress={pick} />
      <Text>Imported: {count}</Text>
    </View>
  );
}
