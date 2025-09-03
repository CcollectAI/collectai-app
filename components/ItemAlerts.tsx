import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, Alert, FlatList } from 'react-native';
import { supabase } from '../lib/supabase';
import { createAlert, deleteAlert } from '../lib/alerts';

export default function ItemAlerts({ itemId }: { itemId: string }) {
  const [rows, setRows] = useState<any[]>([]);
  const [dir, setDir] = useState<'at_or_above'|'at_or_below'>('at_or_above');
  const [target, setTarget] = useState('');

  async function load() {
    const { data, error } = await supabase.from('price_alerts')
      .select('*').eq('item_id', itemId).order('created_at',{ascending:false});
    if (!error) setRows(data||[]);
  }

  useEffect(()=>{ load(); }, [itemId]);

  async function add() {
    try {
      await createAlert(itemId, dir, Number(target || 0));
      setTarget(''); load();
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e));}
  }

  return (
    <View style={{ marginTop:12 }}>
      <Text style={{ fontWeight:'700', marginBottom:6 }}>Price Alerts</Text>
      <TextInput
        value={dir}
        onChangeText={(t)=>{ if (t==='at_or_above'||t==='at_or_below') setDir(t as any); }}
        placeholder="at_or_above | at_or_below"
        style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8, marginBottom:6 }}
      />
      <TextInput
        value={target}
        onChangeText={setTarget}
        keyboardType="decimal-pad"
        placeholder="Target price, e.g., 100"
        style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8, marginBottom:6 }}
      />
      <Button title="Add Alert" onPress={add} />
      <FlatList
        style={{ marginTop:10 }}
        data={rows}
        keyExtractor={(x)=>String(x.id)}
        renderItem={({item})=>(
          <View style={{ borderWidth:1,borderColor:'#eee',borderRadius:8,padding:8, marginBottom:8 }}>
            <Text>{item.direction} €{Number(item.target_price).toFixed(2)}</Text>
            <Text style={{ color:'#666' }}>Last: {item.last_triggered_at ?? '-'}</Text>
            <View style={{ marginTop:6 }}>
              <Button title="Delete" onPress={()=>deleteAlert(item.id).then(load)} />
            </View>
          </View>
        )}
      />
    </View>
  );
}
