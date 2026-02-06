import { useEffect, useState } from 'react';
import { supabase } from "@/lib/supabase";

export type Valuation = { id:number; item_id:string; user_id:string; estimated_value:number; confidence:number; as_of:string; created_at:string; };

export default function useValuations(itemId: string | null){
  const [rows,setRows]=useState<Valuation[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState<string|null>(null);

  const load = async ()=>{
    if(!itemId){ setRows([]); setLoading(false); return; }
    setLoading(true);
    const { data, error } = await supabase
      .from('valuations')
      .select('*')
      .eq('item_id', itemId)
      .order('as_of', { ascending:false })
      .limit(50);
    if(error) setError(error.message); else setRows(data||[]);
    setLoading(false);
  };

  useEffect(()=>{ load(); }, [itemId]);
  return { rows, loading, error, refresh: load };
}
