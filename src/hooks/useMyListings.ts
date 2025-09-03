import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
export default function useMyListings(){
  const [rows,setRows]=useState<any[]>([]);
  const [loading,setLoading]=useState(true);
  const load=async()=>{
    setLoading(true);
    const { data:{ session } } = await supabase.auth.getSession();
    const uid=session?.user?.id; if(!uid){ setRows([]); setLoading(false); return; }
    const { data } = await supabase.from('listings').select('*').eq('seller_id', uid).order('created_at',{ascending:false});
    setRows(data||[]); setLoading(false);
  };
  useEffect(()=>{ load(); },[]);
  return { rows, loading, refresh: load };
}
