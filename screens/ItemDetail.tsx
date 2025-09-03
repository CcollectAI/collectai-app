import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, Alert, ScrollView, Image } from 'react-native';
import { Button as RNButton } from 'react-native';
import { supabase } from '../lib/supabase';
import { addManualPrice } from '../lib/price';
import { uploadItemImage, getSignedUrl } from '../lib/storage';
import AttributeEditor from '../components/AttributeEditor';
import TagManager from '../components/TagManager';
import ItemAlerts from '../components/ItemAlerts';
import SuggestedMarketplaces from './SuggestedMarketplaces';
import ItemGallery from '../components/ItemGallery';
import PriceChart from '../components/PriceChart';
import { duplicateItem } from '../lib/items';
import { shareItem } from '../lib/share';

type Item = {
  id: string;
  title: string;
  category: string;
  attributes: Record<string, any>;
  image_path?: string | null;   // storage path (not URL)
  archived?: boolean;
};

export default function ItemDetail({ route, navigation }: any) {
  const { id } = route.params as { id: string };
  const [item, setItem] = useState<Item | null>(null);
  const [price, setPrice] = useState('');
  const [imgUrl, setImgUrl] = useState<string | null>(null);

  async function load() {
    const { data, error } = await supabase
      .from('items')
      .select('id,title,category,attributes,image_path,archived')
      .eq('id', id)
      .single();
    if (error) { Alert.alert('Error', error.message); return; }
    setItem(data as Item);

    const p = (data as any)?.image_path as string | null;
    if (p) {
      try { const url = await getSignedUrl(p); setImgUrl(url); } catch { setImgUrl(null); }
    } else {
      setImgUrl(null);
    }
  }

  async function attachImage() {
    try {
      const picker = await import('../lib/storage');
      const uri = await picker.pickImage();
      if (!uri) return;
      const path = await uploadItemImage(id, uri);
      const { error } = await supabase.from('items').update({ image_path: path }).eq('id', id);
      if (error) throw error;
      const signed = await getSignedUrl(path);
      setImgUrl(signed);
    } catch (e:any) { Alert.alert('Image', e.message ?? String(e)); }
  }

  async function setArchived(flag: boolean) {
    try {
      const { error } = await supabase.from('items').update({ archived: flag }).eq('id', id);
      if (error) throw error;
      setItem(prev => prev ? { ...prev, archived: flag } : prev);
      Alert.alert(flag ? 'Archived' : 'Restored');
    } catch (e:any) { Alert.alert('Error', e.message ?? String(e)); }
  }

  useEffect(() => { load(); }, []);

  if (!item) return <View style={{ padding:16 }}><Text>Loading…</Text></View>;
  const entries = Object.entries(item.attributes || {});

  return (
    <ScrollView contentContainerStyle={{ padding:16, gap:12 }}>
      <Text style={{ fontWeight:'700', fontSize:18 }}>{item.title}</Text>
      <Text style={{ color:'#666' }}>Category: {item.category}</Text>

      {/* Action row: Edit / Duplicate / Share / Archive/Restore */}
      <View style={{ flexDirection:'row', flexWrap:'wrap', gap:8, marginTop:6 }}>
        <RNButton title="Edit Item" onPress={()=>navigation.navigate('EditItem', { id: item.id })} />
        <RNButton title="Duplicate" onPress={async ()=>{
          try { const nid = await duplicateItem(item.id); navigation.navigate('ItemDetail', { id: nid }); }
          catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
        }} />
        <RNButton title="Share" onPress={()=>shareItem(item.id, item.title)} />
        {item.archived
          ? <RNButton title="Restore" onPress={()=>setArchived(false)} />
          : <RNButton title="Archive" onPress={()=>setArchived(true)} />
        }
      </View>

      {imgUrl ? <Image source={{ uri: imgUrl }} style={{ width:'100%', height:220, borderRadius:12 }} /> : null}
      <Button title={imgUrl ? 'Replace Image' : 'Add Image'} onPress={attachImage} />

      {/* Multi-image gallery */}
      <ItemGallery itemId={item.id} />

      {/* Attributes (read) */}
      <View style={{ marginTop:8 }}>
        <Text style={{ fontWeight:'700', marginBottom:6 }}>Attributes</Text>
        {entries.length === 0
          ? <Text style={{ color:'#666' }}>None</Text>
          : entries.map(([k,v]) => <Text key={k}>{k}: {String(v)}</Text>)
        }
      </View>

      {/* Attribute editor (write) */}
      <AttributeEditor itemId={item.id} category={item.category} initial={item.attributes || {}} />

      {/* Tags */}
      <TagManager itemId={item.id} />

      {/* Price input */}
      <View style={{ marginTop:12 }}>
        <Text style={{ fontWeight:'700' }}>Add Price (EUR)</Text>
        <TextInput
          keyboardType="decimal-pad"
          value={price}
          onChangeText={setPrice}
          placeholder="49.99"
          style={{ borderWidth:1, borderColor:'#ddd', padding:8, borderRadius:8 }}
        />
        <Button
          title="Save Price"
          onPress={async ()=>{
            try {
              const n = Number(price);
              if (Number.isNaN(n)) { Alert.alert('Invalid','Enter a number'); return; }
              await addManualPrice(item.id, n);
              setPrice('');
              Alert.alert('Saved','Price added.');
            } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
          }}
        />
      </View>

      {/* Price chart */}
      <PriceChart itemId={item.id} />

      {/* Marketplaces */}
      <SuggestedMarketplaces category={item.category as any} />
      <Button title="Manage Marketplace Links"
        onPress={() => navigation.navigate('Marketplaces', { itemId: item.id, itemCategory: item.category })}
      />
    </ScrollView>
  );
}
