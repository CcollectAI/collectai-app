import React, { useMemo } from 'react';
import { View, Text, Switch, TextInput, Button, ScrollView, Pressable } from 'react-native';
import { useSettings } from '../src/settings/SettingsContext';
import { CategoryList, CategoryLabels } from '../types/category';

export default function SettingsScreen() {
  const { settings, setSettings } = useSettings();
  const pins = settings.pinnedCategories;
  const remaining = useMemo(()=>CategoryList.filter(c => !pins.includes(c)), [pins]);

  return (
    <ScrollView contentContainerStyle={{ padding:16, gap:16 }}>
      <Text style={{ fontWeight:'800', fontSize:18 }}>Appearance</Text>
      <View style={{ flexDirection:'row', gap:8 }}>
        {(['system','light','dark'] as const).map(mode=>(
          <Pressable key={mode} onPress={()=>setSettings({ theme: mode })} style={{ paddingHorizontal:12, paddingVertical:6, borderWidth:1, borderColor: settings.theme===mode?'#111':'#ddd', borderRadius:999 }}>
            <Text>{mode}</Text>
          </Pressable>
        ))}
      </View>

      <Text style={{ fontWeight:'800', fontSize:18 }}>Items Defaults</Text>
      <View style={{ flexDirection:'row', alignItems:'center', gap:12 }}>
        <Text>Grid by default</Text>
        <Switch value={settings.defaultGrid} onValueChange={(v)=>setSettings({ defaultGrid: v })} />
      </View>
      <View style={{ flexDirection:'row', gap:8, alignItems:'center' }}>
        <Text>Sort by</Text>
        <TextInput value={settings.defaultSortBy} onChangeText={(t)=>['created_at','latest_price','title'].includes(t) && setSettings({ defaultSortBy: t as any })}
          placeholder="created_at | latest_price | title" style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8, minWidth:160 }} />
        <Text>Dir</Text>
        <TextInput value={settings.defaultSortDir} onChangeText={(t)=>['asc','desc'].includes(t) && setSettings({ defaultSortDir: t as any })}
          placeholder="asc | desc" style={{ borderWidth:1,borderColor:'#ddd',padding:8,borderRadius:8, width:90 }} />
      </View>

      <Text style={{ fontWeight:'800', fontSize:18 }}>Pinned Categories</Text>
      <Text>Shown first on Items</Text>
      <View style={{ flexDirection:'row', flexWrap:'wrap', gap:8, marginTop:8 }}>
        {pins.map(c=>(
          <Pressable key={c} onPress={()=> setSettings({ pinnedCategories: pins.filter(p=>p!==c) })} style={{ paddingHorizontal:10,paddingVertical:6,borderRadius:999,borderWidth:1,borderColor:'#111' }}>
            <Text>★ {CategoryLabels[c]}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={{ marginTop:8 }}>Add:</Text>
      <View style={{ flexDirection:'row', flexWrap:'wrap', gap:8 }}>
        {remaining.map(c=>(
          <Pressable key={c} onPress={()=> setSettings({ pinnedCategories: [...pins, c] })} style={{ paddingHorizontal:10,paddingVertical:6,borderRadius:999,borderWidth:1,borderColor:'#ddd' }}>
            <Text>{CategoryLabels[c]}</Text>
          </Pressable>
        ))}
      </View>

      <View style={{ marginTop:16 }}>
        <Button title="Reset to defaults" onPress={()=>setSettings({
          theme: 'system', defaultGrid:false, defaultSortBy:'created_at', defaultSortDir:'desc', pinnedCategories:[]
        })} />
      </View>
    </ScrollView>
  );
}
