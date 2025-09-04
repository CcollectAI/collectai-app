import { useState } from 'react';
import { View, Text, Image, ScrollView, Alert } from 'react-native';
import Input from '../components/Input';
import Button from '../components/Button';
import { colors, fonts, spacing } from '../theme/tokens';
import { supabase } from "@/lib/supabaseClient";
import useOffers from '../hooks/useOffers';

export default function ListingDetail({ route }:any){
  const listing = route.params.listing;
  const { rows: offers, loading, make, setStatus, refresh } = useOffers(listing.id);
  const [offer, setOffer] = useState('');

  const submitOffer = async ()=>{
    try{
      const amt = Number(offer||0);
      if(!amt) throw new Error('Enter an offer amount');
      await make(amt);
      setOffer('');
      Alert.alert('Offer sent');
    }catch(e:any){ Alert.alert('Offer error', e.message||String(e)); }
  };

  const isSeller = async ()=>{
    const { data:{ session } } = await supabase.auth.getSession();
    return session?.user?.id === listing.seller_id;
  };

  return (
    <ScrollView style={{ flex:1, backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing(2), gap: spacing(2) }}>
      <Text style={fonts.h2}>{listing.title}</Text>
      {listing.image_url ? <Image source={{ uri: listing.image_url }} style={{ width:'100%', height:260, borderRadius:16 }} /> : null}
      <Text style={fonts.body}>Price: ${listing.price} {listing.currency}</Text>
      {listing.condition && <Text style={fonts.body}>Condition: {listing.condition}</Text>}
      {listing.description && <Text style={fonts.body}>{listing.description}</Text>}

      <View style={{ height:1, backgroundColor:'#E5E7EB', marginVertical:12 }} />

      <Text style={fonts.title}>Make an offer</Text>
      <Input label="Your offer" value={offer} onChangeText={setOffer} placeholder="e.g. 85.00" />
      <Button title="Send Offer" onPress={submitOffer} />

      <View style={{ height:1, backgroundColor:'#E5E7EB', marginVertical:12 }} />

      <Text style={fonts.title}>Offers</Text>
      {loading ? <Text style={fonts.small}>Loading…</Text> :
        (offers.length ? offers.map(o=>(
          <View key={o.id} style={{ flexDirection:'row', justifyContent:'space-between', paddingVertical:6 }}>
            <Text style={fonts.body}>${o.amount} • {o.status}</Text>
            {/* Seller actions */}
            <View style={{ flexDirection:'row', gap:8 }}>
              <Button title="Accept" onPress={async()=>{
                if(await isSeller()){ await setStatus(o.id,'accepted'); refresh(); }
              }} variant="ghost"/>
              <Button title="Decline" onPress={async()=>{
                if(await isSeller()){ await setStatus(o.id,'declined'); refresh(); }
              }} variant="ghost"/>
            </View>
          </View>
        )) : <Text style={fonts.small}>No offers yet.</Text>)
      }
    </ScrollView>
  );
}
