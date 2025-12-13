import { useEffect, useMemo, useState } from 'react';
import { useItems } from '@/lib/items';
import { useWatchlist } from '@/lib/watchlist';

export function useWatchlistAlert(pollMs: number = 30000){
  const { items } = useItems();
  const { items: watch } = useWatchlist();
  const compute = () => {
    if (!items?.length || !watch?.length) return 0;
    let hits = 0;
    for (const w of watch){
      if (w?.targetEUR == null) continue;
      const name = (w.name ?? '').toLowerCase().trim();
      if (!name) continue;
      const match = items.find(i => (i.title ?? '').toLowerCase().includes(name));
      if (!match) continue;
      const price = Number(match.priceEUR || 0);
      if (price >= Number(w.targetEUR)) hits++;
    }
    return hits;
  };

  const [tick, setTick] = useState(0);
  useEffect(()=>{
    const id = setInterval(()=> setTick(t=>t+1), Math.max(5000, pollMs));
    return ()=> clearInterval(id);
  },[pollMs]);

  const hitCount = useMemo(compute, [items, watch, tick]);
  return { hitCount, hasAlert: hitCount > 0 };
}
