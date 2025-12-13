import { useEffect, useState } from 'react';
import { getJSON } from '@/lib/storage';

type Saved = {
  id?: string;
  name: string;
  q: string;
  cat: string;
  type: string;
  sort: string;
  min?: string;
  max?: string;
  notes?: string;
  pinned?: boolean;
  notify?: boolean;
};

/** Mock alert: badge tab if any saved search has notify=true */
export function useSavedSearchAlert(pollMs: number = 30000){
  const [hasSavedSearchAlert, setFlag] = useState(false);
  useEffect(()=>{
    let stop = false;
    const load = async ()=>{
      try{
        const arr: Saved[] = await getJSON('@savedSearches', []);
        if (stop) return;
        setFlag(Array.isArray(arr) && arr.some(s => !!s?.notify));
      }catch{
        if (!stop) setFlag(false);
      }
    };
    load();
    const id = setInterval(load, Math.max(5000, pollMs));
    return ()=>{ stop = true; clearInterval(id); };
  },[pollMs]);
  return { hasSavedSearchAlert };
}
