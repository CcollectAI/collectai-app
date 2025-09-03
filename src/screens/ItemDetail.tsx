import { useState } from 'react';
import { View, Text, Image, ScrollView, Alert } from 'react-native';
import { fonts, colors, spacing } from '../theme/tokens';
import useValuations from '../hooks/useValuations';
import Button from '../components/Button';
import { supabase } from '../lib/supabase';
import { format } from 'date-fns';
import { useLayoutEffect } from 'react';
import { Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export default function ItemDetail({ route }: any){
  const { item } = route.params;
useLayoutEffect(()=>{
  navigation.setOptions({
    headerRight: ()=>(
      <View style={{ flexDirection:'row' }}>
        <Pressable onPress={()=>navigation.navigate('EditItem', { item })} style={{ paddingHorizontal:12 }}>
          <Ionicons name="create-outline" size={22} />
        </Pressable>
        <Pressable onPress={()=>navigation.navigate('NewListing', { item })} style={{ paddingRight:12 }}>
          <Ionicons name="pricetag-outline" size={22} />
        </Pressable>
      </View>
    )
  });
},[navigation, item]);
  const { rows, loading, refresh } = useValuations(item.id);
  const [adding, setAdding] = useState(false);

  const addValuation = async ()=>{
    try{
      setAdding(true);
      const { data:{ session } } = await supabase.auth.getSession();
      const uid = session?.user?.id; if(!uid) throw new Error('Not signed in');
      const val = Math.max(5, Math.round(((item.purchase_price??50) * 1.1 + Math.random()*10) * 100)/100);
      const { error } = await supabase.from('valuations').insert({
        item_id: item.id, user_id: uid, estimated_value: val, confidence: 70
      });
      if (error) throw error;
      await refresh();
      Alert.alert('Added valuation', `$${val}`);
    }catch(e:any){ Alert.alert('Valuation error', e.message||String(e)); }
    finally{ setAdding(false); }
  };

  const latest = rows[0]?.estimated_value ?? item.purchase_price ?? null;

return (
  <ScrollView style={{ flex:1, backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing(2), gap: spacing(2) }}>
    <Text style={fonts.h2}>{item.title}</Text>
    {item.image_url ? <Image source={{ uri: item.image_url }} style={{ width: '100%', height: 260, borderRadius: 16 }} /> : null}

    <View style={{ gap:8 }}>
      <Text style={fonts.title}>Details</Text>
      <Text style={fonts.body}>Category: {item.category}</Text>
      {item.condition && <Text style={fonts.body}>Condition: {item.condition}</Text>}
      {item.year && <Text style={fonts.body}>Year: {item.year}</Text>}
      {item.series && <Text style={fonts.body}>Series: {item.series}</Text>}
      {item.brand && <Text style={fonts.body}>Brand: {item.brand}</Text>}
      {item.sku && <Text style={fonts.body}>SKU: {item.sku}</Text>}
      {item.tags?.length ? <Text style={fonts.body}>Tags: {item.tags.join(', ')}</Text> : null}
      {item.description && <Text style={fonts.body}>Description: {item.description}</Text>}
      {item.purchase_price!=null && <Text style={fonts.body}>Purchase price: ${item.purchase_price}</Text>}
    </View>

    <View style={{ height:1, backgroundColor:'#E5E7EB', marginVertical:12 }} />

    <View style={{ gap:8 }}>
      <Text style={fonts.title}>Valuation history</Text>
      {loading ? <Text style={fonts.small}>Loading…</Text> :
        (rows.length ? rows.map(r=>(
          <View key={r.id} style={{ flexDirection:'row', justifyContent:'space-between' }}>
            <Text style={fonts.body}>${r.estimated_value} ({r.confidence}%)</Text>
            <Text style={fonts.small}>{format(new Date(r.as_of), 'yyyy-MM-dd HH:mm')}</Text>
          </View>
        )) : <Text style={fonts.small}>No valuations yet.</Text>)
      }
    </View>
    <Button title="Add quick valuation" onPress={addValuation} loading={adding}/>
  </ScrollView>
 );
}
