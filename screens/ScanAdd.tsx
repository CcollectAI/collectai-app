import React, { useEffect, useState } from 'react';
import { View, Text, Button, Alert } from 'react-native';
import { BarCodeScanner } from 'expo-barcode-scanner';
import { supabase } from '../lib/supabase';

export default function ScanAdd({ navigation }: any) {
  const [perm, setPerm] = useState<'granted'|'denied'|'undetermined'>('undetermined');
  const [scanned, setScanned] = useState(false);

  useEffect(() => {
    (async () => {
      const { status } = await BarCodeScanner.requestPermissionsAsync();
      setPerm(status === 'granted' ? 'granted' : 'denied');
    })();
  }, []);

  async function onScan({ data }: { data: string }) {
    if (scanned) return;
    setScanned(true);
    try {
      const title = `Barcode ${data}`;
      const { data: ins, error } = await supabase.from('items').insert([{ title, category: 'funko', attributes: { barcode: data } }]).select('id').single();
      if (error) throw error;
      navigation.replace('ItemDetail', { id: ins?.id });
    } catch (e:any) {
      Alert.alert('Error', e.message ?? String(e));
      setScanned(false);
    }
  }

  if (perm !== 'granted') return <View style={{ flex:1, justifyContent:'center', alignItems:'center' }}><Text>Camera permission {perm}</Text></View>;
  return (
    <View style={{ flex:1 }}>
      <BarCodeScanner onBarCodeScanned={onScan as any} style={{ flex:1 }} />
      <View style={{ position:'absolute', bottom:20, left:0, right:0, alignItems:'center' }}>
        <Button title="Cancel" onPress={()=>navigation.goBack()} />
      </View>
    </View>
  );
}
