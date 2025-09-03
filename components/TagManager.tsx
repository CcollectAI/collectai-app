import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Button, Alert, Pressable } from 'react-native';
import { listTags, upsertTag, getItemTags, addItemTag, removeItemTag } from '../lib/tags';

export default function TagManager({ itemId }: { itemId: string }) {
  const [allTags, setAllTags] = useState<{id:number;name:string}[]>([]);
  const [itemTags, setItemTags] = useState<{id:number;name:string}[]>([]);
  const [newTag, setNewTag] = useState('');

  async function load() {
    const [a, i] = await Promise.all([listTags(), getItemTags(itemId)]);
    setAllTags(a as any);
    setItemTags(i as any);
  }

  useEffect(()=>{ load(); }, [itemId]);

  async function create() {
    try {
      const t = await upsertTag(newTag.trim());
      setNewTag('');
      setAllTags(prev => {
        if (prev.find(p => p.id === t.id)) return prev;
        return [...prev, t as any].sort((x,y)=>x.name.localeCompare(y.name));
      });
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
  }

  async function toggle(tag: {id:number;name:string}) {
    const has = itemTags.find(t=>t.id===tag.id);
    try {
      if (has) await removeItemTag(itemId, tag.id);
      else await addItemTag(itemId, tag.id);
      load();
    } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }
  }

  return (
    <View style={{ marginTop: 12 }}>
      <Text style={{ fontWeight:'700', marginBottom:6 }}>Tags</Text>

      <View style={{ flexDirection:'row', gap:8, alignItems:'center', marginBottom:8 }}>
        <TextInput
          value={newTag}
          onChangeText={setNewTag}
          placeholder="New tag (e.g., grail)"
          style={{ flex:1, borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8 }}
        />
        <Button title="Add" onPress={create} disabled={!newTag.trim()} />
      </View>

      <View style={{ flexDirection:'row', flexWrap:'wrap', gap:8 }}>
        {allTags.map(tag=>{
          const active = itemTags.some(t=>t.id===tag.id);
          return (
            <Pressable key={tag.id} onPress={()=>toggle(tag)}
              style={{ paddingHorizontal:12,paddingVertical:6,borderRadius:999,borderWidth:1,
                       borderColor: active?'#111':'#ddd', backgroundColor: active?'#eee':'#fff' }}>
              <Text>{tag.name}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
