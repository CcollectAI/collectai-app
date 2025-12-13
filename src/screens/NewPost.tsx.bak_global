import { useState } from 'react';
import { View, Image, Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import Button from '@/components/Button';
import Input from '@/components/Input';
import { supabase } from "@/lib/supabaseClient";
import { colors } from '../theme/tokens';
import { uploadFeedImage } from '../utils/uploadFeedImage';

export default function NewPost({ navigation }: any){
  const [content, setContent] = useState('');
  const [imgUri, setImgUri] = useState<string|undefined>();
  const [loading, setLoading] = useState(false);

  const pick = async ()=>{
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') { Alert.alert('Permission required','Enable photo library access.'); return; }
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality:0.85 });
    if (!res.canceled) setImgUri(res.assets[0].uri);
  };

  const post = async ()=>{
    try{
      setLoading(true);
      const { data:{ session } } = await supabase.auth.getSession();
      const uid = session?.user?.id; if(!uid) throw new Error('Not signed in');

      let image_url: string | null = null;
      if (imgUri) image_url = await uploadFeedImage(uid, imgUri);

      const { error } = await supabase.from('posts').insert({ user_id: uid, content, image_url });
      if (error) throw error;

      Alert.alert('Posted');
      setContent(''); setImgUri(undefined);
      navigation.goBack?.();
    }catch(e:any){ Alert.alert('Post error', e.message||String(e)); }
    finally{ setLoading(false); }
  };

  return (
    <View style={{ flex:1, backgroundColor: colors.bg, padding:24, gap:16 }}>
      <Input label="What's new?" value={content} onChangeText={setContent} placeholder="Share your latest pickup…" />
      {imgUri ? <Image source={{ uri: imgUri }} style={{ width:'100%', height:220, borderRadius:16 }} /> : null}
      <Button title="Pick Photo" onPress={pick} variant="ghost" />
      <Button title="Post" onPress={post} loading={loading} />
    </View>
  );
}
