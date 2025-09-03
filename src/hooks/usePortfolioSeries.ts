import { useEffect, useMemo, useState } from 'react';
import { supabase } from '../lib/supabase';

export default function usePortfolioSeries(){
  const [series, setSeries] = useState<{ value:number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(()=>{
    (async ()=>{
      setLoading(true);
      const { data: { session } } = await supabase.auth.getSession();
      const uid = session?.user?.id;
      if(!uid){ setSeries([]); setLoading(false); return; }
      const { data } = await supabase.from('items').select('created_at,purchase_price').eq('user_id', uid).order('created_at', { ascending: true });
      const values: number[] = [];
      let sum = 0;
      (data||[]).forEach((r:any)=>{ sum += Number(r.purchase_price||50); values.push(sum); });
      // if empty, seed placeholder series
      const arr = (values.length? values:[50,60,58,72,80,76,92,110]).map(v=>({ value: v }));
      setSeries(arr);
      setLoading(false);
    })();
  },[]);

  return { series, loading };
}
