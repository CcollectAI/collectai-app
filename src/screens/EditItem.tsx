import { useLayoutEffect, useState } from 'react';
import { View, Image, Alert, ScrollView, Platform, KeyboardAvoidingView } from 'react-native';
import Button from '@/components/Button';
import Input from '@/components/Input';
import { colors, spacing } from '../theme/tokens';
import { supabase } from "@/lib/supabase";
import { uploadImageToBucket } from '../utils/uploadImage';

export default function EditItem({ navigation, route }: any){
  const { item } = route.params;

  const [title, setTitle] = useState(item.title || '');
  const [category, setCategory] = useState(item.category || 'pokemon');
  const [purchase, setPurchase] = useState(item.purchase_price!=null ? String(item.purchase_price) : '');
  const [condition, setCondition] = useState(item.condition || '');
  const [year, setYear] = useState(item.year ? String(item.year) : '');
  const [series, setSeries] = useState(item.series || '');
  const [brand, setBrand] = useState(item.brand || '');
  const [tags, setTags] = useState(item.tags?.join(', ') || '');
  const [description, setDescription] = useState(item.description || '');
  const [image_url, setImageUrl] = useState<string | null>(item.image_url || null);
  const [loading, setLoading] = useState(false);

  useLayoutEffect(()=>{
    navigation.setOptions({
      title: 'Edit Item',
    });
  },[navigation]);

  const pick = async ()=>{
    const { status } = await (await import('expo-image-picker')).requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') { Alert.alert('Permission required','Enable photo library access.'); return; }
    const res = await (await import('expo-image-picker')).launchImageLibraryAsync({ mediaTypes: (await import('expo-image-picker')).MediaTypeOptions.Images, quality:0.85 });
    if (!res.canceled) {
      const uri = res.assets[0].uri;
      try{
        const { data:{ session } } = await supabase.auth.getSession();
        const uid = session?.user?.id; if(!uid) throw new Error('Not signed in');
        const url = await uploadImageToBucket({ uid, uri });
        setImageUrl(url);
      }catch(e:any){ Alert.alert('Upload error', e.message||String(e)); }
    }
  };

  const save = async ()=>{
    try{
      setLoading(true);
      const priceNum = purchase ? Number(purchase) : null;
      const yearNum = year ? Number(year) : null;
      const tagsArr = tags ? tags.split(',').map((t)=>t.trim()).filter(Boolean) : null;

      const { error } = await supabase
        .from('items')
        .update({
          title, category, purchase_price: priceNum, condition: condition||null,
          year: yearNum, series: series||null, brand: brand||null, tags: tagsArr,
          description: description||null, image_url: image_url||null
        })
        .eq('id', item.id);
      if (error) throw error;

      Alert.alert('Saved');
      navigation.goBack();
    }catch(e:any){ Alert.alert('Save error', e.message||String(e)); }
    finally{ setLoading(false); }
  };

  const remove = async ()=>{
    Alert.alert('Delete item','This cannot be undone.',[
      { text:'Cancel', style:'cancel' },
      { text:'Delete', style:'destructive', onPress: async ()=>{
        try{
          setLoading(true);
          const { error } = await supabase.from('items').delete().eq('id', item.id);
          if (error) throw error;
          Alert.alert('Deleted');
          navigation.popToTop();
        }catch(e:any){ Alert.alert('Delete error', e.message||String(e)); }
        finally{ setLoading(false); }
      }}
    ]);
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS==='ios' ? 'padding' : undefined} style={{ flex:1 }}>
      <ScrollView style={{ flex:1, backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing(2), gap: spacing(2), paddingBottom: 40 }}>
        <Input label="Title" value={title} onChangeText={setTitle} />
        <Input label="Category" value={category} onChangeText={setCategory} />
        <Input label="Purchase price" value={purchase} onChangeText={setPurchase} />
        <Input label="Condition" value={condition} onChangeText={setCondition} />
        <Input label="Year" value={year} onChangeText={setYear} />
        <Input label="Series" value={series} onChangeText={setSeries} />
        <Input label="Brand" value={brand} onChangeText={setBrand} />
        <Input label="Tags (comma-separated)" value={tags} onChangeText={setTags} />
        <Input label="Description" value={description} onChangeText={setDescription} />
        {image_url ? <Image source={{ uri:image_url }} style={{ width:'100%', height:220, borderRadius:16 }} /> : null}
        <Button title="Change Photo" onPress={pick} variant="ghost" />
        <Button title="Save Changes" onPress={save} loading={loading} />
        <Button title="Delete Item" onPress={remove} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
