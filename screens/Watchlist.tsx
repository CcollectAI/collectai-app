import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, Alert, FlatList } from 'react-native';
import { supabase } from '../lib/supabase';
import { Category, CategoryList } from '../types/category';
import { CategoryMarketplaces } from '../lib/marketplaces';
import * as WebBrowser from 'expo-web-browser';

type Row = { id: number; category: string | null; query: string; marketplace_key: string | null };

export default function Watchlist() {
  const [rows, setRows] = useState<Row[]>([]);
  const [category, setCategory] = useState<Category | 'all'>('all');
  const [marketplace_key, setMarketplaceKey] = useState<string>('ebay');
  const [query, setQuery] = useState('');

  async function load() {
    const { data, error } = await supabase.from('watchlist').select('*').order('created_at', { ascending: false });
    if (error) Alert.alert('Error', error.message);
    else setRows((data ?? []) as Row[]);
  }

  async function addRow() {
    try {
      const { error } = await supabase.from('watchlist').insert([{
        category: category === 'all' ? null : category,
        marketplace_key,
        query
      }]);
      if (error) throw error;
      setQuery('');
      load();
    } catch(e:any) { Alert.alert('Error', e.message ?? String(e)); }
  }

  async function removeRow(id: number) {
    const { error } = await supabase.from('watchlist').delete().eq('id', id);
    if (error) Alert.alert('Error', error.message); else load();
  }

  useEffect(()=>{ load(); }, []);

  const presets = category === 'all' ? [] : [
    `${category} sealed`,
    `${category} rare`,
    `${category} grail`,
 ];

  return (
    <View style={{ padding: 16, gap: 12 }}>
      <Text style={{ fontWeight:'700' }}>Add Watch</Text>
      <TextInput
        value={category}
        onChangeText={(t)=>{ if (t==='all' || (CategoryList as readonly string[]).includes(t)) setCategory(t as any); }}
        placeholder={`Category (all or one of: ${CategoryList.join(', ')})`}
        style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }}
      />
      <Text>Suggested marketplaces: {suggested.join(', ')}</Text>
      <Text>Query presets: {presets.join(' · ')}</Text>
      <TextInput
        value={marketplace_key}
        onChangeText={setMarketplaceKey}
        placeholder="marketplace key (e.g., ebay)"
        style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }}
      />
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="search keywords"
        style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }}
      />
      <Button title="Add to Watchlist" onPress={addRow} />

      <Text style={{ fontWeight:'700', marginTop: 16 }}>Watchlist</Text>
      <FlatList
        data={rows}
        keyExtractor={(x)=>String(x.id)}
        renderItem={({item})=>(
      <View style={{ marginTop:6, flexDirection:'row', gap:8 }}>
        <Button title="Delete" onPress={()=>removeRow(item.id)} />
          {item.marketplace_key && item.query ? (
        <Button title="Open" onPress={()=>{
          const q = encodeURIComponent(item.query);
          const url =
            item.marketplace_key === 'ebay' ? `https://www.ebay.com/sch/i.html?_nkw=${q}` :
            item.marketplace_key === 'mercari' ? `https://www.mercari.com/search/?keyword=${q}` :
            item.marketplace_key === 'poshmark' ? `https://poshmark.com/search?query=${q}` :
            item.marketplace_key === 'etsy' ? `https://www.etsy.com/search?q=${q}` :
         `https://www.google.com/search?q=${q}`;
       WebBrowser.openBrowserAsync(url);
    }} />
  ) : null}
</View>
  );
}
