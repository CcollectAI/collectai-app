import React, { useState } from 'react';
import { View, Text, Button, Alert } from 'react-native';
import { supabase } from '../lib/supabase';
import { exportCsv } from '../lib/export';

export default function ExportAll() {
  const [busy, setBusy] = useState(false);

  async function run() {
    try {
      setBusy(true);
      // Pull from optimized view
      const { data, error } = await supabase.from('items_card')
        .select('id,title,category,acquisition_price,latest_price,created_at,tag_names')
        .order('created_at', { ascending: false });
      if (error) throw error;
      await exportCsv(data ?? [], 'collection-all.csv');
    } catch (e:any) { Alert.alert('Export', e.message ?? String(e)); }
    finally { setBusy(false); }
  }

  return (
    <View style={{ padding:16, gap:12 }}>
      <Text style={{ fontWeight:'700', fontSize:18 }}>Export Entire Collection</Text>
      <Text style={{ color:'#666' }}>Exports id, title, category, acquisition_price, latest_price, created_at, tags</Text>
      <Button title={busy ? 'Exporting…' : 'Export CSV'} onPress={run} disabled={busy} />
    </View>
  );
}
