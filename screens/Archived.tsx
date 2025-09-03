import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, RefreshControl, Button, ActivityIndicator } from 'react-native';
import { supabase } from '../lib/supabase';
import ItemCard from '../components/ItemCard';
import BulkBar from '../components/BulkBar';

export default function Archived({ navigation }: any) {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  async function load() {
    setLoading(true);
    const { data, error } = await supabase.from('items_card_archived')
      .select('id,title,category,acquisition_price,latest_price,created_at,tag_names,thumb_path')
      .order('created_at', { ascending: false });
    if (!error) setRows(data||[]);
    setLoading(false);
  }

  useEffect(()=>{ load(); }, []);
  const toggle = (id:string)=> setSelected(s=>{const n=new Set(s); n.has(id)?n.delete(id):n.add(id); return n;});
  const restoreOne = async (id:string)=>{ await supabase.from('items').update({ archived:false }).eq('id', id); load(); };

  return (
    <View style={{ flex:1, paddingHorizontal:12 }}>
      <View style={{ paddingVertical:8 }}>
        <Button title="Reload" onPress={load} />
      </View>
      {loading ? <ActivityIndicator style={{ marginTop: 12 }} /> : null}
      {!loading && rows.length===0 ? <Text>No archived items.</Text> : null}
      <FlatList
        data={rows}
        keyExtractor={(x)=>x.id}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
        renderItem={({item})=>(
          <View>
            <ItemCard
              item={item}
              layout="list"
              onPress={()=>restoreOne(item.id)}
              selectable
              selected={selected.has(item.id)}
              onToggleSelect={toggle}
            />
            <View style={{ marginBottom:8, marginLeft:4 }}>
              <Button title="Restore" onPress={()=>restoreOne(item.id)} />
            </View>
          </View>
        )}
      />
      {selected.size ? <BulkBar ids={[...selected]} reload={load} /> : null}
    </View>
  );
}
