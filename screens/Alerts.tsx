import React, { useEffect, useState } from 'react';
import { View, Text, Button, Alert, FlatList } from 'react-native';
import { listAlerts, checkAlertsNow } from '../lib/alerts';
import { supabase } from '../lib/supabase';

export default function Alerts() {
  const [rows, setRows] = useState<any[]>([]);
  const [results, setResults] = useState<any[]>([]);

  async function load() {
    try {
      const a = await listAlerts();
      setRows(a);
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
  }

  useEffect(()=>{ load(); }, []);

  async function check() {
    try {
      const trig = await checkAlertsNow();
      setResults(trig);
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
  }

  return (
    <View style={{ padding:16, gap:12 }}>
      <Button title="Check Alerts Now" onPress={check} />
      {results.length ? (
        <View style={{ borderWidth:1,borderColor:'#0a0', padding:8, borderRadius:8 }}>
          <Text style={{ fontWeight:'700' }}>Triggered: {results.length}</Text>
        </View>
      ) : null}
    import { flushPriceQueue } from '../lib/price';
     ...
    <Button title="Flush Offline Prices" onPress={async()=>{
      const n = await flushPriceQueue();
      Alert.alert('Offline', `Flushed ${n} queued price entries`);  
  }} />
      <Text style={{ fontWeight:'700', marginTop:8 }}>My Alerts</Text>
      <FlatList
        data={rows}
        keyExtractor={(x)=>String(x.id)}
        renderItem={({item})=>(
          <View style={{ borderWidth:1,borderColor:'#eee', padding:8, borderRadius:8, marginBottom:8 }}>
            <Text>item: {item.item_id}</Text>
            <Text>{item.direction} €{Number(item.target_price).toFixed(2)}</Text>
            <Text style={{ color:'#666' }}>last: {item.last_triggered_at ?? '-'}</Text>
          </View>
        )}
      />
    </View>
  );
}
