import { useState } from 'react';
import { View, Image, Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import Button from '@/components/Button';
import Input from '@/components/Input';
import { supabase } from "@/lib/supabaseClient";
import { colors } from '../theme/tokens';
import { uploadImageToBucket } from '../utils/uploadImage';
import { predictValue } from '../utils/predict';

export default function Add(){
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('pokemon');
  const [purchase, setPurchase] = useState<string>('');
  const [condition, setCondition] = useState('');
  const [year, setYear] = useState('');
  const [series, setSeries] = useState('');
  const [brand, setBrand] = useState('');
  const [tags, setTags] = useState(''); // comma separated
  const [description, setDescription] = useState('');
  const [imgUri, setImgUri] = useState<string | undefined>();
  const [suggested, setSuggested] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  const pick = async () => { /* keep as before */ };
  const capture = async ()=>{ /* keep if you added earlier */ };
  const suggest = async ()=>{ /* keep as before */ };

  const submit = async ()=>{
    try{
      setLoading(true);
      const { data:{ session } } = await supabase.auth.getSession();
      const uid = session?.user?.id; if(!uid) throw new Error('Not signed in');

      let image_url: string | null = null;
      if (imgUri) image_url = await uploadImageToBucket({ uid, uri: imgUri });

      const priceNum = purchase ? Number(purchase) : null;
      const yearNum = year ? Number(year) : null;
      const tagsArr = tags ? tags.split(',').map(s=>s.trim()).filter(Boolean) : null;

      const insert = {
        user_id: uid, title, category, image_url, purchase_price: priceNum,
        condition: condition || null, year: yearNum, series: series || null,
        brand: brand || null, tags: tagsArr, description: description || null
      };

      const { data: inserted, error } = await supabase
        .from('items')
        .insert(insert)
        .select('id')
        .single();
      if (error) throw error;

      if (suggested != null) {
        const { error: vErr } = await supabase
          .from('valuations')
          .insert({ item_id: inserted.id, user_id: uid, estimated_value: suggested, confidence: 72 });
        if (vErr) throw vErr;
      }

      Alert.alert('Item added');
      setTitle(''); setCategory('pokemon'); setPurchase(''); setCondition('');
      setYear(''); setSeries(''); setBrand(''); setTags(''); setDescription(''); setImgUri(undefined); setSuggested(null);
    }catch(e:any){ Alert.alert('Add item error', e.message||String(e)); }
    finally{ setLoading(false); }
  };

  return (
    <View style={{ flex:1, backgroundColor: colors.bg, padding:24, gap:16 }}>
      <Input label="Title" value={title} onChangeText={setTitle} placeholder="e.g. Pikachu VMAX" />
      <Input label="Category" value={category} onChangeText={setCategory} placeholder="pokemon / funko / diecast" />
      <Input label="Purchase price (optional)" value={purchase} onChangeText={setPurchase} placeholder="e.g. 49.99" />
      <Input label="Condition" value={condition} onChangeText={setCondition} placeholder="mint / near-mint / used" />
      <Input label="Year" value={year} onChangeText={setYear} placeholder="e.g. 2021" />
      <Input label="Series" value={series} onChangeText={setSeries} placeholder="e.g. Base Set" />
      <Input label="Brand" value={brand} onChangeText={setBrand} placeholder="e.g. Pokémon / Funko / Hot Wheels" />
      <Input label="Tags (comma-separated)" value={tags} onChangeText={setTags} placeholder="e.g. holo, first edition" />
      <Input label="Description" value={description} onChangeText={setDescription} placeholder="notes…" />
      {imgUri ? <Image source={{ uri: imgUri }} style={{ width:'100%', height:220, borderRadius:16 }} /> : null}
      {/* Optional: <Button title="Take Photo" onPress={capture} variant="ghost" /> */}
      <Button title="Suggest value" onPress={suggest} variant="ghost" />
      <Button title="Add Item" onPress={submit} loading={loading} />
    </View>
  );
}

