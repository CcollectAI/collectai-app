import { useCallback, useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';

export type Listing = {
  id:string; item_id:string; seller_id:string;
  title:string; description?:string|null;
  price:number; currency:string; quantity:number; condition?:string|null;
  image_url?:string|null; status:string; created_at:string;
};

export default function useMarketplace(q:{ search?:string; min?:number; max?:number; order?:'new'|'price_asc'|'price_desc' }){
  const [rows,setRows]=useState<Listing[]>([]);
  const [loading,setLoading]=useState(true);
  const [page,setPage]=useState(0);
  const [refreshing,setRefreshing]=useState(false);
  const pageSize=20;

  const load = useCallback(async (reset:boolean)=>{
    const from=(reset?0:page)*pageSize, to=from+pageSize-1;
    if(reset) setLoading(true); else setRefreshing(true);

    let query = supabase.from('listings').select('*').eq('status','active');
    if(q.search?.trim()) query = query.ilike('title', `%${q.search.trim()}%`);
    if(q.min!=null) query = query.gte('price', q.min);
    if(q.max!=null) query = query.lte('price', q.max);
    if(q.order==='price_asc') query = query.order('price', { ascending:true });
    else if(q.order==='price_desc') query = query.order('price', { ascending:false });
    else query = query.order('created_at', { ascending:false });

    const { data, error } = await query.range(from,to);
    if(!error){
      setRows(reset? (data||[]) : [...rows, ...(data||[])]);
      if(!reset) setPage(p=>p+1);
    }
    setLoading(false); setRefreshing(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.search, q.min, q.max, q.order, page, rows]);

  useEffect(()=>{ load(true); }, [q.search, q.min, q.max, q.order]);

  return { rows, loading, refreshing, refresh: ()=>load(true), loadMore: ()=>load(false) };
}
