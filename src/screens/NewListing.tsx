import { useState } from 'react';
import { View, Image, Alert, ScrollView } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import Input from '@/components/Input';
import Button from '@/components/Button';
import { colors, spacing } from '../theme/tokens';
import { supabase } from "@/lib/supabaseClient";
import { uploadListingImage } from '../utils/uploadListingImage';

export default function NewListing({ route, navigation }: any){
  const item = route?.params?.item || null;

  const [title, setTitle] = useState(item?.title || '');
  const [price, setPrice] = useState(item?.purchase_price ? String(item.purchase_price) : '');
  const [currency, setCurrency] = useState('USD');
  const [quantity, setQuantity] = useState('1');
  const [condition, setCondition] = useState(item?.condition || '');
  const [description, setDescription] = useState(item?.description || '');
  const [imageUrl, setImageUrl] = useState<string | null>(item?.image_url || null);
  const [imgUri, setImgUri] = useState<string|undefined>();
  const [loading, setLoading] = useState(false);

  const pick = async ()=>{
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') { Alert.alert('Permission required','Enable photo library access.'); return; }
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality:0.85 });
    if (!res.canceled) setImgUri(res.assets[0].uri);
  };

  const uploadIfNeeded = async (uid:string)=>{
    if (imgUri) {
      const url = await uploadListingImage(uid, imgUri);
      return url;
    }
    return imageUrl;
  };

  const submit = async ()=>{
    try{
      setLoading(true);
      const { data:{ session } } = await supabase.auth.getSession();
      const uid=session?.user?.id; if(!uid) throw new Error('Not signed in');

      const img = await uploadIfNeeded(uid);
      const priceNum = Number(price||0);
      const qtyNum = Number(quantity||1);
      if(!title || !priceNum) throw new Error('Title and price are required');

      const { error } = await supabase.from('listings').insert({
        item_id: item?.id || null,
        seller_id: uid,
        title,
        description: description || null,
        price: priceNum,
        currency,
        quantity: qtyNum,
        condition: condition || null,
        image_url: img || null,
        status: 'active'
      });
      if (error) throw error;

      Alert.alert('Listing created');
      navigation.goBack();
    }catch(e:any){ Alert.alert('Listing error', e.message||String(e)); }
    finally{ setLoading(false); }
  };

  return (
    <ScrollView style={{ flex:1, backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing(2), gap: spacing(2) }}>
      <Input label="Title" value={title} onChangeText={setTitle} />
      <Input label="Price" value={price} onChangeText={setPrice} placeholder="e.g. 99.99" />
      <Input label="Currency" value={currency} onChangeText={setCurrency} placeholder="USD" />
      <Input label="Quantity" value={quantity} onChangeText={setQuantity} placeholder="1" />
      <Input label="Condition" value={condition} onChangeText={setCondition} placeholder="mint / near-mint / used" />
      <Input label="Description" value={description} onChangeText={setDescription} placeholder="details…" />
      { (imgUri || imageUrl) ? <Image source={{ uri: imgUri || imageUrl! }} style={{ width:'100%', height:220, borderRadius:16 }} /> : null }
      <Button title="Pick Photo" onPress={pick} variant="ghost" />
      <Button title="Create Listing" onPress={submit} />
    </ScrollView>
  );
}
