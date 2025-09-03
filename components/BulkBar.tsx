import React, { useState } from 'react';
import { View, Text, Button, TextInput, Alert } from 'react-native';
import { exportCsv } from '../lib/export';
import { upsertTag, addItemTag } from '../lib/tags';
import { supabase } from '../lib/supabase';

export default function BulkBar({ ids, reload }: { ids: string[]; reload: () => void }) {
  const [tag, setTag] = useState('');
  const disabled = ids.length === 0;

  async function applyTag() {
    try {
      if (!tag.trim()) return;
      const t = await upsertTag(tag.trim());
      for (const id of ids) {
        await addItemTag(id, t.id as any);
      }
      setTag('');
      reload();
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
  }

  async function archive() {
    try {
      const { error } = await supabase.from('items').update({ archived: true }).in('id', ids);
      if (error) throw error;
      reload();
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
  }

  async function remove() {
    try {
      const { error } = await supabase.from('items').delete().in('id', ids);
      if (error) throw error;
      reload();
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
  }

  async function restore() {
   try {
    const { error } = await supabase.from('items').update({ archived: false }).in('id', ids);
    if (error) throw error;
    reload();
  } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
}

  async function exportSel() {
    try {
      const { data, error } = await supabase.from('items_card').select('*').in('id', ids);
      if (error) throw error;
      await exportCsv(data ?? [], 'selected-items.csv');
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
  }

  return (
    <View style={{ borderTopWidth:1, borderColor:'#eee', padding:10, backgroundColor:'#fafafa', gap:8 }}>
      <Text style={{ fontWeight:'700' }}>Selected: {ids.length}</Text>
      <View style={{ flexDirection:'row', gap:8, alignItems:'center' }}>
        <TextInput
          value={tag}
          onChangeText={setTag}
          placeholder="add tag to selected"
          style={{ flex:1, borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }}
        />
        <Button title="Apply Tag" onPress={applyTag} disabled={disabled || !tag.trim()} />
      </View>
    <View style={{ flexDirection:'row', gap:8, justifyContent:'space-between' }}>
      <Button title="Export CSV" onPress={exportSel} disabled={disabled} />
      <Button title="Archive" onPress={archive} disabled={disabled} />
      <Button title="Restore" onPress={restore} disabled={disabled} />
      <Button title="Delete" color="#b00020" onPress={remove} disabled={disabled} />
     </View>
    </View>
  );
}
