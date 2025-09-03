import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';

export type Offer = { id:string; listing_id:string; buyer_id:string; amount:number; status:string; created_at:string };

export default function useOffers(listingId:string){
  const [rows,setRows]=useState<Offer[]>([]);
  const [loading,setLoading]=useState(true);

  const load=async()=>{
    setLoading(true);
    const { data } = await supabase.from('offers').select('*').eq('listing_id', listingId).order('created_at',{ascending:false});
    setRows(data||[]); setLoading(false);
  };

  useEffect(()=>{ load(); },[listingId]);

  const make = async (amount:number)=>{
    const { data:{ session } } = await supabase.auth.getSession();
    const uid=session?.user?.id; if(!uid) return;
    await supabase.from('offers').insert({ listing_id: listingId, buyer_id: uid, amount });
    await load();
  };

  const setStatus = async (offerId:string, status:'accepted'|'declined'|'withdrawn')=>{
    await supabase.from('offers').update({ status }).eq('id', offerId);
    await load();
  };

  return { rows, loading, make, setStatus, refresh: load };
}
