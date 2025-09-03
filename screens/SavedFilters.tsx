import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, Alert, FlatList } from 'react-native';
import { supabase } from '../lib/supabase';
import type { Category } from '../types/category';
import { CategoryList } from '../types/category';

export default function SavedFilters({ navigation, route }: any) {
  const [rows, setRows] = useState<any[]>([]);
  const [name, setName] = useState('');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<Category | 'all'>('all');

  async function load() {
    const { data, error } = await supabase.from('saved_filters').select('*').order('created_at', { ascending: false });
    if (error) Alert.alert('Error', error.message); else setRows(data ?? []);
  }

  async function saveFilter() {
    try {
      const u = (await supabase.auth.getUser()).data.user;
      if (!u?.id) { Alert.alert('Auth','No user'); return; }
      const { error } = await supabase.from('saved_filters').insert([{
        owner: u.id, name, search: search || null, category: category === 'all' ? null : category
      }]);
      if (error) throw error;
      setName(''); load();
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
  }

  async function removeFilter(id:number) {
    const { error } = await supabase.from('saved_filters').delete().eq('id', id);
    if (error) Alert.alert('Error', error.message); else load();
  }

  useEffect(()=>{ load(); }, []);

  return (
    <View style={{ padding:16, gap:12 }}>
      <Text style={{ fontWeight:'700' }}>Save current filter</Text>
      <TextInput placeholder="Name" value={name} onChangeText={setName} style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }} />
      <TextInput placeholder="Search" value={search} onChangeText={setSearch} style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }} />
      <TextInput placeholder={`Category (all or: ${CategoryList.join(', ')})`} value={category} onChangeText={(t)=>{ if (t==='all' || (CategoryList as readonly string[]).includes(t)) setCategory(t as any); }} style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }} />
      <Button title="Save Filter" onPress={saveFilter} />

      <Text style={{ fontWeight:'700', marginTop:16 }}>My Filters</Text>
      <FlatList
        data={rows}
        keyExtractor={(x)=>String(x.id)}
        renderItem={({item})=>(
          <View style={{ borderWidth:1,borderColor:'#eee',padding:8,borderRadius:8, marginBottom:8 }}>
            <Text style={{ fontWeight:'600' }}>{item.name}</Text>
            <Text>search: {item.search ?? '-'}</Text>
            <Text>category: {item.category ?? 'all'}</Text>
            <View style={{ flexDirection:'row', gap:8, marginTop:6 }}>
              <Button title="Apply" onPress={()=>navigation.navigate('Items', { preset: { search: item.search ?? '', category: item.category ?? 'all' }})} />
              <Button title="Delete" onPress={()=>removeFilter(item.id)} />
            </View>
          </View>
        )}
      />
    </View>
  );
}
