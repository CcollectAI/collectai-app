import React, { useEffect, useState } from 'react';
import { View, Text, Switch, Button } from 'react-native';
import { get, put } from '../lib/store';

type Progress = {
  addedFirstItem: boolean;
  attachedPhoto: boolean;
  addedPrice: boolean;
  createdTag: boolean;
  createdAlert: boolean;
};

const DEFAULT: Progress = { addedFirstItem:false, attachedPhoto:false, addedPrice:false, createdTag:false, createdAlert:false };

export default function Onboarding({ navigation }: any) {
  const [p, setP] = useState<Progress>(DEFAULT);
  useEffect(()=>{ (async()=> setP(await get('onboarding', DEFAULT)))(); }, []);
  async function setFlag(k: keyof Progress, v: boolean){ const next = { ...p, [k]: v }; setP(next); await put('onboarding', next); }

  return (
    <View style={{ padding:16, gap:12 }}>
      <Text style={{ fontWeight:'800', fontSize:18 }}>Getting started</Text>

      {([
        ['addedFirstItem','Add your first item'],
        ['attachedPhoto','Attach a photo'],
        ['addedPrice','Add a price'],
        ['createdTag','Create a tag'],
        ['createdAlert','Create a price alert'],
      ] as [keyof Progress,string][]).map(([k,label])=>(
        <View key={k} style={{ flexDirection:'row', alignItems:'center', justifyContent:'space-between', paddingVertical:8 }}>
          <Text>{label}</Text><Switch value={p[k]} onValueChange={(v)=>setFlag(k,v)} />
        </View>
      ))}

      <Button title="Go to Items" onPress={()=>navigation.navigate('Home', { screen: 'Items' })} />
    </View>
  );
}
