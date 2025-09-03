import { useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';

export type Portfolio = {
  user_id: string;
  total_items: number;
  total_spent: number;
  total_value: number;
};

export default function usePortfolio(){
  const [data, setData] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    const { data: { session } } = await supabase.auth.getSession();
    const uid = session?.user?.id;
    if (!uid) { setData(null); setLoading(false); return; }
    const { data, error } = await supabase
      .from('v_portfolio_summary')
      .select('*')
      .eq('user_id', uid)
      .maybeSingle();
    if (error) setError(error.message); else setData(data ?? { user_id: uid, total_items: 0, total_spent: 0, total_value: 0 });
    setLoading(false);
  };

  useEffect(()=>{ load(); },[]);
  return { data, loading, error, refresh: load };
}
