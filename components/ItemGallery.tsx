import React, { useEffect, useState } from 'react';
import { View, Text, Image, Button, FlatList, Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system';
import { supabase } from '../lib/supabase';
import { getSignedUrl } from '../lib/storage';

async function listPaths(itemId: string) {
  const { data, error } = await supabase.storage.from('item-images').list(`${itemId}`, { limit: 100 });
  if (error) throw error;
  return (data || []).map(d => `${itemId}/${d.name}`);
}

async function uploadPath(path: string, bytes: string) {
  const { error } = await supabase.storage.from('item-images').upload(path, Buffer.from(bytes, 'base64'), { contentType: 'image/jpeg', upsert: false });
  if (error) throw error;
}

async function uploadFromUri(itemId: string, uri: string) {
  const base64 = await FileSystem.readAsStringAsync(uri, { encoding: FileSystem.EncodingType.Base64 });
  const path = `${itemId}/${Date.now()}.jpg`;
  await uploadPath(path, base64);
}

async function remove(path: string) {
  const { error } = await supabase.storage.from('item-images').remove([path]);
  if (error) throw error;
}

export default function ItemGallery({ itemId }: { itemId: string }) {
  const [paths, setPaths] = useState<string[]>([]);
  const [urls, setUrls] = useState<string[]>([]);

  async function refresh() {
    const p = await listPaths(itemId);
    setPaths(p);
    const u: string[] = [];
    for (const one of p) {
      const s = await getSignedUrl(one);
      u.push(s);
    }
    setUrls(u);
  }

  useEffect(()=>{ refresh(); }, [itemId]);

  return (
    <View style={{ marginTop:12 }}>
      <Text style={{ fontWeight:'700', marginBottom:6 }}>Gallery</Text>
      <View style={{ flexDirection:'row', gap:8, marginBottom:8 }}>
        <Button title="Add Photo" onPress={async()=>{ try {
          const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
          if (perm.status !== 'granted') return;
          const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.9 });
          if (!res.canceled && res.assets?.length) {
            await uploadFromUri(itemId, res.assets[0].uri);
            await refresh();
          }
        } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }}} />
        <Button title="Take Photo" onPress={async()=>{ try {
          const cam = await ImagePicker.requestCameraPermissionsAsync();
          if (cam.status !== 'granted') return;
          const res = await ImagePicker.launchCameraAsync({ quality: 0.85 });
          if (!res.canceled && res.assets?.length) {
            await uploadFromUri(itemId, res.assets[0].uri);
            await refresh();
          }
        } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); }}} />
        <Button title="Refresh" onPress={refresh} />
      </View>
      <FlatList
        horizontal
        data={urls}
        keyExtractor={(u, i)=>u+String(i)}
        renderItem={({item, index})=>(
          <View style={{ marginRight:8 }}>
            <Image source={{ uri: item }} style={{ width:160, height:160, borderRadius:12 }} />
            <Button title="Delete" onPress={async()=>{ try { await remove(paths[index]); await refresh(); } catch(e:any){ Alert.alert('Error', e.message ?? String(e)); } }} />
          </View>
        )}
      />
    </View>
  );
}
